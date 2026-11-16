"""Lists the latest videos on a TikTok profile and downloads them without the watermark (yt-dlp)."""
import os
import re
from dataclasses import dataclass
from typing import List, Optional

import requests
import yt_dlp

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "videos")


@dataclass
class Video:
    id: str
    url: str
    description: str = ""
    path: str = ""


def _base_opts(cookies_file: Optional[str]):
    opts = {"quiet": True, "no_warnings": True, "noprogress": True}
    if cookies_file:
        opts["cookiefile"] = cookies_file
    return opts


def latest_videos(username: str, cookies_file: Optional[str] = None, limit: int = 10,
                  sec_uid: Optional[str] = None) -> List[Video]:
    """Newest first. sec_uid (TikTok's internal profile id) is more reliable than the username page."""
    opts = _base_opts(cookies_file)
    opts.update({"extract_flat": True, "playlistend": limit})
    source = f"tiktokuser:{sec_uid}" if sec_uid else f"https://www.tiktok.com/@{username.lstrip('@')}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source, download=False)
    except yt_dlp.utils.DownloadError:
        # TikTok often refuses its profile API from cloud servers; the public embed page still works.
        return _embed_videos(username, limit)
    videos = []
    for e in info.get("entries") or []:
        vid = str(e.get("id"))
        url = e.get("url") or f"https://www.tiktok.com/@{username}/video/{vid}"
        videos.append(Video(id=vid, url=url, description=e.get("description") or e.get("title") or ""))
    return videos


def _embed_videos(username: str, limit: int) -> List[Video]:
    """Newest first, from TikTok's public profile embed (ids only; download() fills the description)."""
    username = username.lstrip("@")
    r = requests.get(f"https://www.tiktok.com/embed/@{username}", timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"})
    r.raise_for_status()
    ids = list(dict.fromkeys(re.findall(r"/video/(\d{15,})", r.text)))
    if not ids:
        raise RuntimeError("TikTok embed page returned no videos")
    return [Video(id=i, url=f"https://www.tiktok.com/@{username}/video/{i}") for i in ids[:limit]]


def download(video: Video, cookies_file: Optional[str] = None) -> Video:
    """Downloads the clean (non-watermarked) stream. Returns the video with full description filled in."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    opts = _base_opts(cookies_file)
    opts.update({
        # TikTok exposes a watermarked "download" format and clean "play" formats: skip the watermarked one,
        # then take the highest resolution, and at equal resolution the highest bitrate.
        "format": "b[format_note!*=atermark]/bv*[format_note!*=atermark]+ba/b",
        "format_sort": ["res", "tbr", "br"],
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "overwrites": True,
    })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video.url, download=True)
            path = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError:
        # TikTok blocks video downloads from cloud servers; Apify fetches through home-type connections.
        if not os.getenv("APIFY_TOKEN"):
            raise
        return _apify_download(video)
    if not os.path.exists(path):
        path = os.path.splitext(path)[0] + ".mp4"
    print(f"  📐 quality: {info.get('width')}x{info.get('height')} {info.get('vcodec')} "
          f"{round(info.get('tbr') or 0)}kbps (direct from TikTok)", flush=True)
    video.description = info.get("description") or video.description
    video.path = path
    return video


def _apify_download(video: Video) -> Video:
    """Clean (no watermark) copy via Apify's TikTok scraper. Called only for new videos, to stay in the free credit."""
    headers = {"Authorization": f"Bearer {os.environ['APIFY_TOKEN']}"}
    r = requests.post("https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items",
                      headers=headers, timeout=300, json={
                          "postURLs": [video.url],
                          "shouldDownloadVideos": True,
                          "shouldDownloadCovers": False,
                      })
    r.raise_for_status()
    items = [i for i in r.json() if i.get("mediaUrls")]
    if not items:
        raise RuntimeError(f"Apify returned no video for {video.url}")
    item = items[0]
    path = os.path.join(DOWNLOAD_DIR, f"{video.id}.mp4")
    with requests.get(item["mediaUrls"][0], headers=headers, timeout=300, stream=True) as v:
        v.raise_for_status()
        with open(path, "wb") as f:
            for chunk in v.iter_content(1 << 20):
                f.write(chunk)
    meta = item.get("videoMeta") or {}
    print(f"  📐 quality: {meta.get('width')}x{meta.get('height')} (via Apify)", flush=True)
    video.description = item.get("text") or video.description
    video.path = path
    return video
