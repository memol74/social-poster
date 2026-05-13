"""Run a post from a posts/ folder.

Usage:
    py run_post.py posts/my_post/           # post to all platforms
    py run_post.py posts/my_post/ --only instagram
    py run_post.py posts/my_post/ --only youtube,instagram

Workflow:
  1. Reads post.json from the folder
  2. For Instagram: uploads video to Google Drive, gets public URL, posts reel
  3. For YouTube: uploads video directly via API
  4. Cleans up the Drive file after Instagram is done
"""

import argparse
import json
import os
import sys
import time

# truststore for corporate SSL — harmless on personal laptop
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

ROOT = os.path.dirname(os.path.abspath(__file__))
DRIVE_TOKEN = os.path.join(ROOT, "tokens", "drive_token.json")
CLIENT_SECRET = os.path.join(ROOT, "client_secret.json")
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """Authenticate with Google Drive (reuses YouTube's OAuth client)."""
    creds = None
    if os.path.exists(DRIVE_TOKEN):
        creds = Credentials.from_authorized_user_file(DRIVE_TOKEN, DRIVE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, DRIVE_SCOPES)
            creds = flow.run_local_server(port=8083)
        os.makedirs(os.path.dirname(DRIVE_TOKEN), exist_ok=True)
        with open(DRIVE_TOKEN, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def upload_to_drive(video_path):
    """Upload video to Google Drive and return a public direct URL."""
    drive = get_drive_service()
    name = os.path.basename(video_path)

    print(f"  Uploading {name} to Google Drive...")
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    file = drive.files().create(
        body={"name": name, "mimeType": "video/mp4"},
        media_body=media,
        fields="id",
    ).execute()
    file_id = file["id"]

    # Make it publicly readable
    drive.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    print(f"  Drive URL: {url}")
    return file_id, url


def delete_from_drive(file_id):
    """Delete a file from Google Drive."""
    drive = get_drive_service()
    drive.files().delete(fileId=file_id).execute()
    print(f"  Cleaned up Drive file {file_id}")


def main():
    parser = argparse.ArgumentParser(description="Run a post from a posts/ folder")
    parser.add_argument("folder", help="Path to the post folder (e.g. posts/my_post/)")
    parser.add_argument("--only", help="Comma-separated platforms (default: all)")
    args = parser.parse_args()

    # Load post.json
    post_file = os.path.join(args.folder, "post.json")
    if not os.path.exists(post_file):
        print(f"Error: {post_file} not found")
        sys.exit(1)

    with open(post_file) as f:
        post = json.load(f)

    video_path = os.path.join(args.folder, post["video"])
    if not os.path.exists(video_path):
        print(f"Error: video not found: {video_path}")
        sys.exit(1)

    platforms = post.get("platforms", {})
    if args.only:
        selected = [p.strip() for p in args.only.split(",")]
        platforms = {k: v for k, v in platforms.items() if k in selected}

    if not platforms:
        print("No platforms to post to.")
        sys.exit(1)

    # Resolve thumbnail path if present
    thumbnail = post.get("thumbnail")
    if thumbnail:
        thumbnail = os.path.join(args.folder, thumbnail)
        if not os.path.exists(thumbnail):
            print(f"  [warn] Thumbnail not found: {thumbnail}")
            thumbnail = None

    # If Instagram is in the list, upload to Drive first
    drive_file_id = None
    drive_url = None
    if "instagram" in platforms:
        drive_file_id, drive_url = upload_to_drive(video_path)

    results = {}
    for platform, config in platforms.items():
        print(f"\n>> Posting to {platform}...")
        try:
            if platform == "youtube":
                from uploaders.youtube import upload
                vid = upload(
                    video_path,
                    title=config["title"],
                    description=config.get("description", ""),
                    tags=config.get("tags", []),
                    privacy=config.get("privacy", "public"),
                    thumbnail=thumbnail,
                )
                results[platform] = {"success": True, "id": vid}

            elif platform == "instagram":
                from uploaders.instagram import upload_reel
                mid = upload_reel(drive_url, caption=config.get("caption", ""))
                results[platform] = {"success": True, "id": mid}

            elif platform == "tiktok":
                from uploaders.tiktok import upload
                tid = upload(
                    video_path,
                    description=config.get("description", ""),
                    privacy=config.get("privacy", "PUBLIC_TO_EVERYONE"),
                )
                results[platform] = {"success": True, "id": tid}

            else:
                print(f"  Skipping unknown platform: {platform}")
                results[platform] = {"success": False, "error": "unknown"}

        except Exception as e:
            print(f"  FAILED: {e}")
            results[platform] = {"success": False, "error": str(e)}

    # Cleanup Drive file
    if drive_file_id:
        try:
            delete_from_drive(drive_file_id)
        except Exception as e:
            print(f"  Warning: couldn't delete Drive file: {e}")

    # Summary
    print("\n" + "=" * 50)
    print("Results:")
    for p, r in results.items():
        mark = "OK" if r["success"] else "FAIL"
        print(f"  [{mark}] {p}: {r.get('id', r.get('error', ''))}")


if __name__ == "__main__":
    main()
