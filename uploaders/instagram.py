"""Instagram Reels uploader using Facebook Login for Business.

Uses Facebook Login for Business to get a token, then publishes Reels.
Local files use the resumable upload API (rupload.facebook.com).
Public URLs use the video_url approach.
"""

import os
import json
import shutil
import subprocess
import tempfile
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


def _response_details(response):
    try:
        return response.json()
    except ValueError:
        return response.text


def _create_reel_container(ig_user_id, caption, token, video_url=None, resumable=False):
    data = {
        "media_type": "REELS",
        "caption": caption,
        "access_token": token,
    }
    if resumable:
        data["upload_type"] = "resumable"
    else:
        data["video_url"] = video_url

    r = requests.post(f"{GRAPH_URL}/{ig_user_id}/media", data=data, timeout=60)
    if not r.ok:
        raise Exception(f"Container creation failed: {_response_details(r)}")
    return r.json()["id"]


def _upload_resumable_video(container_id, local_path, token):
    file_size = os.path.getsize(local_path)
    headers = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(file_size),
    }
    upload_url = f"https://rupload.facebook.com/ig-api-upload/{container_id}"

    print("  Uploading video binary to Meta...")
    with open(local_path, "rb") as f:
        r = requests.post(upload_url, headers=headers, data=f, timeout=(30, 900))

    if not r.ok:
        raise Exception(f"Video upload failed: {_response_details(r)}")

    details = _response_details(r)
    if isinstance(details, dict) and details.get("success") is False:
        raise Exception(f"Video upload failed: {details}")

    print("  Video upload complete")


def _wait_for_container(container_id, token):
    for _ in range(60):
        time.sleep(5)
        r = requests.get(f"{GRAPH_URL}/{container_id}", params={
            "fields": "status_code,status",
            "access_token": token,
        }, timeout=60)
        r.raise_for_status()
        status = r.json()
        code = status.get("status_code", "UNKNOWN")
        print(f"  Processing... {code}")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise Exception(f"Processing failed: {status}")

    raise Exception("Processing timed out (5 min)")


def _publish_container(ig_user_id, container_id, token):
    r = requests.post(f"{GRAPH_URL}/{ig_user_id}/media_publish", data={
        "creation_id": container_id,
        "access_token": token,
    }, timeout=60)
    r.raise_for_status()
    media_id = r.json()["id"]
    print(f"  Published! Media ID: {media_id}")
    return media_id


def _probe_video(local_path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None

    result = subprocess.run([
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,pix_fmt,color_range,color_space",
        "-of", "json",
        local_path,
    ], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return None

    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError:
        return None
    return streams[0] if streams else None


def _needs_instagram_normalization(local_path):
    stream = _probe_video(local_path)
    if not stream:
        return False

    return (
        stream.get("codec_name") != "h264"
        or stream.get("pix_fmt") != "yuv420p"
        or stream.get("color_range") == "pc"
        or stream.get("color_space") not in (None, "bt709")
    )


def _prepare_local_video(local_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not _needs_instagram_normalization(local_path):
        return local_path, None

    fd, normalized_path = tempfile.mkstemp(suffix="_instagram.mp4")
    os.close(fd)

    print("  Normalizing MP4 for Instagram processing...")
    result = subprocess.run([
        ffmpeg,
        "-y",
        "-i", local_path,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-vf", "scale=out_range=tv,format=yuv420p",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-b:v", "8M",
        "-maxrate", "12M",
        "-bufsize", "16M",
        "-color_range", "tv",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        normalized_path,
    ], check=False, capture_output=True, text=True)

    if result.returncode != 0:
        try:
            os.remove(normalized_path)
        except OSError:
            pass
        raise Exception(f"Instagram video normalization failed: {result.stderr.strip()}")

    normalized_size = os.path.getsize(normalized_path)
    print(f"  Normalized file: {normalized_size / 1024 / 1024:.1f} MB")
    return normalized_path, normalized_path


def upload_reel(video_url, caption="", token=None):
    """Upload a Reel to Instagram.
    
    Args:
        video_url: Local file path or public URL of the video.
        caption: Post caption.
        token: Optional access token override. If provided, skips saved token lookup.
    """
    if token:
        ig_user_id = _resolve_ig_user_id(token)
        token_data = {"access_token": token, "ig_user_id": ig_user_id}
        _save_token({**token_data, "token_type": "fb_login_for_business"})
        print(f"  Using provided token (Instagram account: {ig_user_id})")
    else:
        token_data = authenticate()
        token = token_data["access_token"]
    ig_user_id = token_data["ig_user_id"]

    is_local = os.path.isfile(video_url)
    cleanup_path = None

    try:
        if is_local:
            file_size = os.path.getsize(video_url)
            print(f"  Local file: {video_url} ({file_size / 1024 / 1024:.1f} MB)")
            upload_path, cleanup_path = _prepare_local_video(video_url)
            print("  Creating resumable upload container...")
            container_id = _create_reel_container(ig_user_id, caption, token, resumable=True)
            print(f"  Container: {container_id}")
            _upload_resumable_video(container_id, upload_path, token)
        else:
            print("  Creating container from public video URL...")
            container_id = _create_reel_container(ig_user_id, caption, token, video_url=video_url)
            print(f"  Container: {container_id}")

        _wait_for_container(container_id, token)
        return _publish_container(ig_user_id, container_id, token)
    finally:
        if cleanup_path:
            try:
                os.remove(cleanup_path)
            except OSError:
                pass
