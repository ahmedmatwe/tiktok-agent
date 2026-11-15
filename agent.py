"""
TikTok → YouTube / Instagram auto-repost agent.

  python agent.py            # runs forever, checks every CHECK_EVERY_MINUTES
  python agent.py --once     # one check then exit (good for cron/launchd)
  python agent.py --url URL  # repost one specific TikTok video now
  python agent.py --youtube-login   # one-time YouTube sign-in
"""
import argparse
import os
import sys
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
# Unset GitHub secrets arrive as empty strings; drop them so code defaults apply.
for _k in [k for k, v in os.environ.items() if v == ""]:
    del os.environ[_k]

import captioner  # noqa: E402
import state  # noqa: E402
import sources  # noqa: E402
import tiktok  # noqa: E402
from publishers import instagram, youtube  # noqa: E402


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def enabled_publishers():
    # Only YouTube and Instagram are published to.
    pubs = {"youtube": youtube, "instagram": instagram}
    return {name: mod for name, mod in pubs.items()
            if os.getenv(f"ENABLE_{name.upper()}", "true").lower() == "true"}


def process(video, cookies, targets=None):
    selected = {n: p for n, p in enabled_publishers().items() if targets is None or n in targets}
    pubs = {n: p for n, p in selected.items() if not state.done(video.id, n)}
    if not pubs:
        return
    log(f"🎬 New video {video.id} → {', '.join(pubs)}")
    tiktok.download(video, cookies)
    log(f"  ⬇️  downloaded without watermark: {video.path}")

    # Reuse the captions from a previous attempt so every platform gets the same post.
    meta = state.get_meta(video.id)
    if not meta:
        meta = captioner.generate(video.description)
        state.mark(video.id, "_meta", meta)
    log(f"  ✍️  title: {meta['youtube_title']}")

    failed = []
    for name, pub in pubs.items():
        try:
            link = pub.publish(video.path, meta)
            state.mark(video.id, name, link)
            log(f"  ✅ {name}: {link}")
        except Exception as e:
            failed.append(name)
            log(f"  ❌ {name} failed (will retry next round): {e}")

    if all(state.done(video.id, n) for n in selected):
        try:
            os.remove(video.path)
        except OSError:
            pass
    if failed:
        raise RuntimeError("Publishing failed: " + ", ".join(failed))


def check_once():
    cookies = os.getenv("TIKTOK_COOKIES_FILE") or None
    failures = []
    for username, sec_uid, primary in sources.accounts():
        try:
            videos = tiktok.latest_videos(username, cookies, sec_uid=sec_uid)
            marker = f"__initialized__:{username}"
            initialized = state.known(marker) or (primary and state.known("__initialized__"))
            if not initialized and os.getenv("BACKFILL", "false").lower() != "true":
                for v in videos:
                    if not state.known(v.id):
                        state.mark(v.id, "_skipped_on_first_run", True)
                state.mark(marker, "done", True)
                log(f"@{username}: initialized; existing videos skipped, watching new uploads.")
                continue
            state.mark(marker, "done", True)
            log(f"Checking @{username}: {len(videos)} videos")
            for v in reversed(videos):
                if state.done(v.id, "_skipped_on_first_run"):
                    continue
                try:
                    targets = None if primary else {"youtube", "instagram"}
                    process(v, cookies, targets)
                except Exception:
                    failures.append(f"@{username}/{v.id}")
                    log(f"  ❌ video {v.id} failed:\n{traceback.format_exc()}")
        except Exception:
            failures.append(f"@{username}")
            log(f"  ❌ account @{username} failed:\n{traceback.format_exc()}")
    if failures:
        raise RuntimeError("Failed checks: " + ", ".join(failures))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--url")
    ap.add_argument("--youtube-login", action="store_true")
    ap.add_argument("--probe", action="store_true", help="list + download the newest video only, publish nothing")
    args = ap.parse_args()

    if args.probe:
        vids = tiktok.latest_videos(os.environ["TIKTOK_USERNAME"], sec_uid=os.getenv("TIKTOK_SEC_UID") or None)
        log(f"Found {len(vids)} videos, newest {vids[0].id}")
        v = tiktok.download(vids[0])
        log(f"Downloaded {os.path.getsize(v.path) // 1024} KB without watermark: {v.description[:60]}")
        os.remove(v.path)
        return
    if args.youtube_login:
        youtube.login()
        log("YouTube login saved.")
        return
    if args.url:
        vid = args.url.rstrip("/").split("/")[-1].split("?")[0]
        process(tiktok.Video(id=vid, url=args.url), os.getenv("TIKTOK_COOKIES_FILE") or None)
        return

    every = int(os.getenv("CHECK_EVERY_MINUTES", "15"))
    while True:
        try:
            check_once()
        except Exception:
            log(f"Check failed:\n{traceback.format_exc()}")
            if args.once:
                sys.exit(1)
        if args.once:
            break
        time.sleep(every * 60)


if __name__ == "__main__":
    main()
