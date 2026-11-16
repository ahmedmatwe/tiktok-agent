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


RUN_STARTED = time.time()
LAST_POST_KEY = "__last_new_post__"


class Wait(Exception):
    """A new video is ready but the previous one went out less than POST_GAP_MINUTES ago."""


def gap_minutes_left():
    gap = float(os.getenv("POST_GAP_MINUTES", "30"))
    last = (state._load().get(LAST_POST_KEY) or {}).get("at", 0)
    # Measured run-start to run-start, with 2 minutes of slack for GitHub's scheduler jitter.
    return gap - 2 - (RUN_STARTED - last) / 60


def process(video, cookies, targets=None, spaced=False):
    selected = {n: p for n, p in enabled_publishers().items() if targets is None or n in targets}
    pubs = {n: p for n, p in selected.items() if not state.done(video.id, n)}
    if not pubs:
        return
    # Retries of a video that is already partly out go straight away; only brand-new videos wait their turn.
    if spaced and len(pubs) == len(selected):
        left = gap_minutes_left()
        if left > 0:
            raise Wait(f"{video.id} waits ~{round(left) + 2} min (one new video per half hour)")
        state.mark(LAST_POST_KEY, "at", RUN_STARTED)
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
    pending = []  # (video, targets, username) from every account, posted oldest first
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
            for v in videos:
                if not state.done(v.id, "_skipped_on_first_run"):
                    pending.append((v, None if primary else {"youtube", "instagram"}, username))
        except Exception:
            failures.append(f"@{username}")
            log(f"  ❌ account @{username} failed:\n{traceback.format_exc()}")

    # TikTok ids grow with upload time, so this posts the oldest waiting video first, across all accounts.
    for v, targets, username in sorted(pending, key=lambda p: int(p[0].id)):
        try:
            process(v, cookies, targets, spaced=True)
        except Wait as w:
            log(f"  ⏳ {w}")
        except Exception:
            failures.append(f"@{username}/{v.id}")
            log(f"  ❌ video {v.id} failed:\n{traceback.format_exc()}")
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
