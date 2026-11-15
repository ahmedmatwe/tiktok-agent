import os

import requests


def graph():
    return f"https://graph.facebook.com/{os.getenv('META_GRAPH_VERSION', 'v23.0')}"


def token():
    return os.environ["FB_PAGE_TOKEN"]


def check(resp):
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400 or "error" in data:
        raise RuntimeError(data.get("error", data) or resp.text)
    return data


def upload_binary(upload_url, path, access_token=None):
    """Meta's resumable upload host (rupload.facebook.com): one-shot upload of a local file."""
    with open(path, "rb") as f:
        r = requests.post(upload_url, data=f, timeout=900, headers={
            "Authorization": f"OAuth {access_token or token()}",
            "offset": "0",
            "file_size": str(os.path.getsize(path)),
        })
    return check(r)
