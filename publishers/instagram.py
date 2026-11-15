"""
Publishes a Reel on an Instagram Business/Creator account (free).

Two ways to authenticate:
  - IG_ACCESS_TOKEN set  → "Instagram API with Instagram Login" (graph.instagram.com). No Facebook Page needed.
  - otherwise            → Facebook Page token (graph.facebook.com) with IG_USER_ID linked to that Page.
"""
import json
import os
import subprocess
import time

import requests

from . import meta_common
from .meta_common import check, upload_binary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IG_TOKEN_FILE = os.path.join(ROOT, "data", "ig_token.json")
REFRESH_EVERY = 7 * 24 * 3600  # Instagram Login tokens last 60 days; refresh weekly


def _instagram_login_token():
    saved = {}
    if os.path.exists(IG_TOKEN_FILE):
        with open(IG_TOKEN_FILE) as f:
            saved = json.load(f)
    # A new token in .env wins over the saved one.
    if saved.get("seed") != os.environ["IG_ACCESS_TOKEN"]:
        saved = {"seed": os.environ["IG_ACCESS_TOKEN"], "token": os.environ["IG_ACCESS_TOKEN"], "at": time.time()}
    if time.time() - saved.get("refreshed", saved["at"]) > REFRESH_EVERY:
        r = check(requests.get("https://graph.instagram.com/refresh_access_token", timeout=30,
                               params={"grant_type": "ig_refresh_token", "access_token": saved["token"]}))
        saved["token"], saved["refreshed"] = r["access_token"], time.time()
    os.makedirs(os.path.dirname(IG_TOKEN_FILE), exist_ok=True)
    with open(IG_TOKEN_FILE, "w") as f:
        json.dump(saved, f)
    return saved["token"]


def _api():
    """Returns (base_url, account_id, token)."""
    if os.getenv("IG_ACCESS_TOKEN"):
        base = f"https://graph.instagram.com/{os.getenv('META_GRAPH_VERSION', 'v23.0')}"
        return base, os.getenv("IG_USER_ID") or "me", _instagram_login_token()
    return meta_common.graph(), os.environ["IG_USER_ID"], meta_common.token()


def _publish_once(path, meta):
    base, ig, tok = _api()
    container = check(requests.post(f"{base}/{ig}/media", timeout=60, data={
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": meta["instagram_caption"],
        "share_to_feed": "true",
        "access_token": tok,
    }))
    upload_binary(container["uri"], path, tok)

    # Instagram processes the video before it can be published.
    for _ in range(60):
        status = check(requests.get(f"{base}/{container['id']}", timeout=30,
                                    params={"fields": "status_code,status", "access_token": tok}))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {status}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram processing timed out")

    media = check(requests.post(f"{base}/{ig}/media_publish", timeout=60,
                                data={"creation_id": container["id"], "access_token": tok}))
    link = check(requests.get(f"{base}/{media['id']}", timeout=30,
                              params={"fields": "permalink", "access_token": tok}))
    return link.get("permalink", media["id"])


def _to_h264(path):
    """Re-encodes to the plain H.264/AAC MP4 Instagram always accepts (TikTok often serves HEVC)."""
    out = os.path.splitext(path)[0] + ".ig.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", path,
        "-vf", "scale='min(1080,iw)':-2,fps=30", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "21", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", out,
    ], check=True, timeout=600)
    return out


def publish(path, meta):
    try:
        permalink = _publish_once(path, meta)
    except Exception as e:
        print(f"  ↻ Instagram rejected the original file ({e}); retrying as H.264", flush=True)
        fixed = _to_h264(path)
        try:
            permalink = _publish_once(fixed, meta)
        finally:
            try:
                os.remove(fixed)
            except OSError:
                pass
    return permalink
