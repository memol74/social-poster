"""Instagram Reels uploader using Facebook Login for Business.

Uses Facebook Login for Business to get a token, then publishes Reels.
Local files use the resumable upload API (rupload.facebook.com).
Public URLs use the video_url approach.
"""

import os
import json
import time
import webbrowser
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
import requests

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
TOKEN_FILE = os.path.join(ROOT, "tokens", "instagram_token.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")
GRAPH_URL = "https://graph.facebook.com/v22.0"
REDIRECT_URI = "https://localhost:8082/"

# Scopes needed for Instagram content publishing via FB Login for Business
FB_SCOPES = (
    "instagram_basic,"
    "instagram_content_publish,"
    "pages_read_engagement,"
    "pages_manage_metadata"
)


def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)["instagram"]


def _load_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)


def _save_token(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _resolve_ig_user_id(token):
    """Get the Instagram Business Account ID linked to the user's Facebook Page."""
    # /me/accounts is broken with New Pages Experience — query token debug instead
    r = requests.get(f"{GRAPH_URL}/debug_token", params={
        "input_token": token,
        "access_token": token,
    })
    r.raise_for_status()
    debug = r.json().get("data", {})
    granular = debug.get("granular_scopes", [])

    # Find page IDs from the token's scoped permissions
    page_ids = []
    for scope in granular:
        if scope.get("scope") == "pages_read_engagement":
            page_ids = scope.get("target_ids", [])
            break

    if not page_ids:
        raise Exception(
            "No Facebook Pages in token scope. Re-authenticate and select your Page."
        )

    # Check each page for a linked IG business account
    for page_id in page_ids:
        r = requests.get(f"{GRAPH_URL}/{page_id}", params={
            "fields": "id,name,instagram_business_account{id,username}",
            "access_token": token,
        })
        if r.status_code != 200:
            continue
        data = r.json()
        ig_account = data.get("instagram_business_account")
        if ig_account:
            print(f"  Found Page: {data.get('name', page_id)}")
            print(f"  IG Account: @{ig_account.get('username', '?')} ({ig_account['id']})")
            return ig_account["id"]

    raise Exception(
        "No Page has a linked Instagram Business account. "
        "Link your Instagram to a Facebook Page first."
    )


def authenticate():
    """Facebook Login for Business OAuth2 flow.
    
    Opens browser, user logs in, copies redirect URL with code.
    Exchanges for long-lived token.
    """
    cfg = _load_config()
    app_id = cfg["fb_app_id"]
    app_secret = cfg["fb_app_secret"]

    # Check for existing valid token
    if os.path.exists(TOKEN_FILE):
        token_data = _load_token()
        if token_data.get("access_token") and token_data.get("ig_user_id"):
            # Verify token still works
            r = requests.get(f"{GRAPH_URL}/me", params={
                "access_token": token_data["access_token"]
            })
            if r.status_code == 200:
                return token_data
            print("  Existing token expired, re-authenticating...")

    auth_url = (
        f"https://www.facebook.com/v22.0/dialog/oauth"
        f"?client_id={app_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=token"
        f"&scope={FB_SCOPES}"
    )
    print(f"\n  Opening browser for Facebook Login...")
    print(f"  URL: {auth_url}\n")
    webbrowser.open(auth_url)
    print("  After logging in, the browser will redirect to a page that won't load.")
    print("  Copy the ACCESS TOKEN from the URL (after 'access_token=' and before '&').\n")
    short_token = input("  Paste access token: ").strip()

    # Try to exchange for long-lived token (60 days)
    r = requests.get(f"{GRAPH_URL}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    })
    if r.status_code == 200 and "access_token" in r.json():
        token = r.json()["access_token"]
        print(f"  Exchanged for long-lived token (60 days)")
    else:
        token = short_token
        print(f"  Using token as-is (couldn't exchange: {r.status_code})")

    # Resolve IG user ID from linked Page
    ig_user_id = _resolve_ig_user_id(token)

    token_data = {
        "access_token": token,
        "ig_user_id": ig_user_id,
        "token_type": "fb_login_for_business",
    }
    _save_token(token_data)
    print(f"  Long-lived token saved (expires in ~60 days)")
    print(f"  Instagram Business Account ID: {ig_user_id}")
    return token_data


def _upload_to_gdrive(local_path):
    """Upload a file to Google Drive and return a public direct-download URL."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request as GRequest
    from google.oauth2.credentials import Credentials as GCredentials
    from googleapiclient.discovery import build as gbuild
    from googleapiclient.http import MediaFileUpload

    GDRIVE_TOKEN = os.path.join(ROOT, "tokens", "gdrive_token.json")
    CLIENT_SECRET = os.path.join(ROOT, "client_secret.json")
    GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    creds = None
    if os.path.exists(GDRIVE_TOKEN):
        creds = GCredentials.from_authorized_user_file(GDRIVE_TOKEN, GDRIVE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, GDRIVE_SCOPES)
            creds = flow.run_local_server(port=8083)
        os.makedirs(os.path.dirname(GDRIVE_TOKEN), exist_ok=True)
        with open(GDRIVE_TOKEN, "w") as f:
            f.write(creds.to_json())

    service = gbuild("drive", "v3", credentials=creds)
    fname = os.path.basename(local_path)
    media = MediaFileUpload(local_path, mimetype="video/mp4", resumable=True)
    file_meta = {"name": fname}
    gfile = service.files().create(body=file_meta, media_body=media, fields="id").execute()
    file_id = gfile["id"]

    # Make it publicly readable
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    public_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    print(f"  Google Drive file ID: {file_id}")
    return public_url


def upload_reel(video_url, caption=""):
    """Upload a Reel to Instagram.
    
    Args:
        video_url: Local file path or public URL of the video.
        caption: Post caption.
    """
    token_data = authenticate()
    token = token_data["access_token"]
    ig_user_id = token_data["ig_user_id"]

    is_local = os.path.isfile(video_url)

    if is_local:
        file_size = os.path.getsize(video_url)
        print(f"  Local file: {video_url} ({file_size / 1024 / 1024:.1f} MB)")

        public_url = None

        # Try litterbox first (10s timeout)
        try:
            print(f"  Uploading to temp host (litterbox.catbox.moe)...")
            with open(video_url, "rb") as f:
                r = requests.post(
                    "https://litterbox.catbox.moe/resources/internals/api.php",
                    data={"reqtype": "fileupload", "time": "72h"},
                    files={"fileToUpload": (os.path.basename(video_url), f, "video/mp4")},
                    timeout=10,
                )
            if r.status_code == 200 and r.text.startswith("http"):
                public_url = r.text.strip()
        except Exception as e:
            print(f"  Litterbox failed: {e}")

        # Fallback: 0x0.st (10s timeout)
        if not public_url:
            try:
                print(f"  Trying fallback (0x0.st)...")
                with open(video_url, "rb") as f:
                    r = requests.post(
                        "https://0x0.st",
                        files={"file": (os.path.basename(video_url), f, "video/mp4")},
                        timeout=10,
                    )
                if r.status_code == 200 and r.text.strip().startswith("http"):
                    public_url = r.text.strip()
            except Exception as e:
                print(f"  0x0.st failed: {e}")

        # Fallback: tmpfiles.org
        if not public_url:
            try:
                print(f"  Trying fallback (tmpfiles.org)...")
                with open(video_url, "rb") as f:
                    r = requests.post(
                        "https://tmpfiles.org/api/v1/upload",
                        files={"file": (os.path.basename(video_url), f, "video/mp4")},
                        timeout=120,
                    )
                if r.status_code == 200:
                    data = r.json()
                    tmp_url = data.get("data", {}).get("url", "")
                    if tmp_url:
                        # Convert view URL to direct download URL
                        public_url = tmp_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            except Exception as e:
                print(f"  tmpfiles.org failed: {e}")

        # Fallback: uguu.se
        if not public_url:
            try:
                print(f"  Trying fallback (uguu.se)...")
                with open(video_url, "rb") as f:
                    r = requests.post(
                        "https://uguu.se/upload",
                        files={"files[]": (os.path.basename(video_url), f, "video/mp4")},
                        timeout=120,
                    )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and data:
                        public_url = data[0].get("url", "")
                    elif isinstance(data, dict):
                        public_url = data.get("url", "")
            except Exception as e:
                print(f"  uguu.se failed: {e}")

        # Last resort: Google Drive
        if not public_url:
            try:
                print(f"  Trying Google Drive upload...")
                public_url = _upload_to_gdrive(video_url)
            except Exception as e:
                print(f"  Google Drive failed: {e}")

        if not public_url:
            raise Exception("All temp hosts failed. Try again later or upload manually.")

        print(f"  Temp URL: {public_url}")
        video_url = public_url

    # Create container with public video URL
    print(f"  Creating container...")
    r = requests.post(f"{GRAPH_URL}/{ig_user_id}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": token,
    })
    r.raise_for_status()
    container_id = r.json()["id"]
    print(f"  Container: {container_id}")

    # Step 2: Wait for processing
    for i in range(60):
        time.sleep(5)
        r = requests.get(f"{GRAPH_URL}/{container_id}", params={
            "fields": "status_code,status",
            "access_token": token,
        })
        r.raise_for_status()
        status = r.json()
        code = status.get("status_code", "UNKNOWN")
        print(f"  Processing... {code}")
        if code == "FINISHED":
            break
        elif code == "ERROR":
            raise Exception(f"Processing failed: {status}")
    else:
        raise Exception("Processing timed out (5 min)")

    # Step 3: Publish
    r = requests.post(f"{GRAPH_URL}/{ig_user_id}/media_publish", data={
        "creation_id": container_id,
        "access_token": token,
    })
    r.raise_for_status()
    media_id = r.json()["id"]
    print(f"  Published! Media ID: {media_id}")
    return media_id
