"""TikTok source accounts; all sources use the configured publisher accounts."""
import os
import re


def accounts():
    primary = os.getenv("TIKTOK_USERNAME", "").strip().lstrip("@").lower()
    raw = os.getenv("TIKTOK_USERNAMES") or primary
    names = list(dict.fromkeys(n.lstrip("@").lower() for n in re.split(r"[,\s]+", raw.strip()) if n))
    if not names:
        raise ValueError("Set TIKTOK_USERNAME or TIKTOK_USERNAMES")
    if any(not re.fullmatch(r"[a-z0-9._]{1,24}", n) for n in names):
        raise ValueError("TIKTOK_USERNAMES must contain usernames, not URLs")
    if not primary:
        primary = names[0]
    return [(name, os.getenv("TIKTOK_SEC_UID") or None if name == primary else None,
             name == primary) for name in names]
