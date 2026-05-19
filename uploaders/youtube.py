"""YouTube Shorts uploader using YouTube Data API v3."""

import os
import json
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
TOKEN_FILE = os.path.join(ROOT, "tokens", "youtube_token.json")
CLIENT_SECRET = os.path.join(ROOT, "client_secret.json")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",  # needed for thumbnails
]


def authenticate():
    """Authenticate with YouTube. Opens browser on first run."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=8080)
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(video_path, title, description="", tags=None, privacy="public", thumbnail=None):
    """Upload a video as YouTube Short, optionally with a custom thumbnail."""
    youtube = authenticate()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    media = MediaFileUpload(video_path, chunksize=256 * 1024, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Uploading... {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"  Done: https://youtube.com/shorts/{video_id}")

    # Set custom thumbnail if provided
    if thumbnail and os.path.exists(thumbnail):
        try:
            thumb_media = MediaFileUpload(thumbnail, mimetype="image/png")
            youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
            print(f"  Thumbnail set: {thumbnail}")
        except Exception as e:
            print(f"  [warn] Thumbnail upload failed: {e}")

    return video_id
