"""Uploads a vertical video to YouTube as a Short (YouTube Data API v3, free quota)."""
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "data", "youtube_token.json")


def _credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    elif os.getenv("YOUTUBE_TOKEN_JSON"):  # on GitHub Actions the saved login comes from a secret
        creds = Credentials.from_authorized_user_info(json.loads(os.environ["YOUTUBE_TOKEN_JSON"]), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if os.getenv("CI"):
            raise RuntimeError("YouTube login missing or revoked: run `agent.py --youtube-login` on a computer "
                               "and update the YOUTUBE_TOKEN_JSON secret")
        secret = os.path.join(ROOT, os.getenv("YOUTUBE_CLIENT_SECRET", "client_secret.json"))
        creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    return creds


def login():
    _credentials()


def publish(path, meta):
    yt = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
    body = {
        "snippet": {
            "title": meta["youtube_title"],
            "description": meta["youtube_description"],
            "tags": meta.get("youtube_tags", [])[:15],
            "categoryId": "22",
        },
        "status": {"privacyStatus": os.getenv("YOUTUBE_PRIVACY", "public"), "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, chunksize=-1, resumable=True, mimetype="video/mp4"))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtube.com/shorts/{resp['id']}"
