"""Remembers which videos were already posted to which platform (per platform, so failures retry)."""
import json
import os
import threading

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state.json")
_lock = threading.Lock()


def _load():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)



def known(video_id):
    return video_id in _load()


def done(video_id, platform):
    return bool(_load().get(video_id, {}).get(platform))


def mark(video_id, platform, result):
    with _lock:
        data = _load()
        data.setdefault(video_id, {})[platform] = result
        _save(data)


def get_meta(video_id):
    return _load().get(video_id, {}).get("_meta")
