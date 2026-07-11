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
    "pages_manage_metadata,"
    "pages_show_list"
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


def _resolve_ig_account(token):
    """Get the linked Instagram Business account and Page token."""
    # /me/accounts is broken with New Pages Experience — query token debug instead
    r = requests.get(f"{GRAPH_URL}/debug_token", params={
        "input_token": token,
        "access_token": token,
    }, timeout=60)
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
            "fields": "id,name,access_token,instagram_business_account{id,username}",
            "access_token": token,
        }, timeout=60)
        if r.status_code != 200:
            continue
        data = r.json()
        ig_account = data.get("instagram_business_account")
        if ig_account:
            print(f"  Found Page: {data.get('name', page_id)}")
            print(f"  IG Account: @{ig_account.get('username', '?')} ({ig_account['id']})")
            return {
                "ig_user_id": ig_account["id"],
                "page_id": page_id,
                "page_name": data.get("name"),
                "page_access_token": data.get("access_token"),
            }

    raise Exception(
        "No Page has a linked Instagram Business account. "
        "Link your Instagram to a Facebook Page first."
    )


def _resolve_ig_user_id(token):
    return _resolve_ig_account(token)["ig_user_id"]


def _refresh_page_token(token_data):
    user_token = token_data.get("user_access_token") or token_data.get("access_token")
    account = _resolve_ig_account(user_token)
    refreshed = {
        **token_data,
        **account,
        "user_access_token": user_token,
    }
    _save_token(refreshed)
    return refreshed


def _publishing_token(token_data, require_page_token=False):
    page_token = token_data.get("page_access_token")
    if page_token:
        print("  Using Page access token for Instagram publishing")
        return page_token

    if require_page_token:
        raise Exception(
            "No Facebook Page access token found for Instagram publishing. "
            "Run `python3.10 poster.py setup instagram` and grant the Page permissions again."
        )

    print("  [warn] Page access token unavailable; using saved access token")
    return token_data["access_token"]


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
            user_token = token_data.get("user_access_token") or token_data["access_token"]
            r = requests.get(f"{GRAPH_URL}/me", params={
                "access_token": user_token
            }, timeout=60)
            if r.status_code == 200:
                if not token_data.get("page_access_token"):
                    token_data = _refresh_page_token(token_data)
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
    }, timeout=60)
    if r.status_code == 200 and "access_token" in r.json():
        token = r.json()["access_token"]
        print(f"  Exchanged for long-lived token (60 days)")
    else:
        token = short_token
        print(f"  Using token as-is (couldn't exchange: {r.status_code})")

    # Resolve linked Page, IG user ID, and Page token for publishing.
    account = _resolve_ig_account(token)

    token_data = {
        "access_token": token,
        "user_access_token": token,
        **account,
        "token_type": "fb_login_for_business",
    }
    _save_token(token_data)
    print(f"  Long-lived token saved (expires in ~60 days)")
    print(f"  Instagram Business Account ID: {account['ig_user_id']}")
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
    if isinstance(details, dict):
        if details.get("success") is False or details.get("debug_info"):
            raise Exception(f"Video upload failed: {details}")

    print("  Video upload complete")


def _upload_resumable_video_with_curl(container_id, local_path, token):
    curl = shutil.which("curl")
    if not curl:
        raise Exception("curl is not installed")

    file_size = os.path.getsize(local_path)
    upload_url = f"https://rupload.facebook.com/ig-api-upload/{container_id}"

    print("  Uploading video binary to Meta with curl...")
    result = subprocess.run([
        curl,
        "-sS",
        "-X", "POST",
        upload_url,
        "-H", f"Authorization: OAuth {token}",
        "-H", "offset: 0",
        "-H", f"file_size: {file_size}",
        "--data-binary", f"@{local_path}",
    ], check=False, capture_output=True, text=True)

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        raise Exception(f"curl upload failed: {stderr or stdout}")

    try:
        details = json.loads(stdout) if stdout else {}
    except ValueError:
        details = stdout

    if isinstance(details, dict):
        if details.get("success") is False or details.get("debug_info"):
            raise Exception(f"curl video upload failed: {details}")

    print("  Curl video upload complete")


def _upload_resumable_file_url(container_id, file_url, token):
    headers = {
        "Authorization": f"OAuth {token}",
        "file_url": file_url,
    }
    upload_url = f"https://rupload.facebook.com/ig-api-upload/{container_id}"

    print("  Asking Meta to fetch hosted video...")
    r = requests.post(upload_url, headers=headers, timeout=(30, 300))
    if not r.ok:
        raise Exception(f"Hosted video upload failed: {_response_details(r)}")

    details = _response_details(r)
    if isinstance(details, dict):
        if details.get("success") is False or details.get("debug_info"):
            raise Exception(f"Hosted video upload failed: {details}")

    print("  Hosted video upload complete")


def _validate_hosted_video_url(file_url):
    try:
        r = requests.get(
            file_url,
            headers={"Range": "bytes=0-0"},
            stream=True,
            allow_redirects=True,
            timeout=(15, 60),
        )
        try:
            if not r.ok:
                return False, f"HTTP {r.status_code}"
            content_type = r.headers.get("Content-Type", "").strip()
            if not content_type.lower().startswith("video/"):
                return False, f"content type {content_type or 'unknown'}"
            return True, content_type
        finally:
            r.close()
    except Exception as e:
        return False, str(e)


def _upload_to_temp_hosts(local_path):
    file_name = os.path.basename(local_path)

    try:
        print("  Uploading normalized video to 0x0.st...")
        with open(local_path, "rb") as f:
            r = requests.post(
                "https://0x0.st",
                files={"file": (file_name, f, "video/mp4")},
                timeout=180,
            )
        if r.status_code == 200 and r.text.strip().startswith("http"):
            yield "0x0.st", r.text.strip()
        else:
            print(f"  0x0.st failed: {_response_details(r)}")
    except Exception as e:
        print(f"  0x0.st failed: {e}")

    try:
        print("  Uploading normalized video to litterbox.catbox.moe...")
        with open(local_path, "rb") as f:
            r = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "72h"},
                files={"fileToUpload": (file_name, f, "video/mp4")},
                timeout=180,
            )
        if r.status_code == 200 and r.text.strip().startswith("http"):
            yield "litterbox", r.text.strip()
        else:
            print(f"  litterbox failed: {_response_details(r)}")
    except Exception as e:
        print(f"  litterbox failed: {e}")

    try:
        print("  Uploading normalized video to tmpfiles.org...")
        with open(local_path, "rb") as f:
            r = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": (file_name, f, "video/mp4")},
                timeout=180,
            )
        if r.status_code == 200:
            tmp_url = r.json().get("data", {}).get("url", "")
            if tmp_url:
                yield "tmpfiles.org", tmp_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            else:
                print(f"  tmpfiles.org failed: {_response_details(r)}")
        else:
            print(f"  tmpfiles.org failed: {_response_details(r)}")
    except Exception as e:
        print(f"  tmpfiles.org failed: {e}")


def _upload_resumable_with_fallback(ig_user_id, caption, local_path, token):
    print("  Creating resumable upload container...")
    container_id = _create_reel_container(ig_user_id, caption, token, resumable=True)
    print(f"  Container: {container_id}")

    try:
        _upload_resumable_video(container_id, local_path, token)
        return container_id
    except Exception as direct_error:
        print(f"  Direct binary upload failed: {direct_error}")

    try:
        print("  Trying curl binary upload with a fresh container...")
        curl_container_id = _create_reel_container(ig_user_id, caption, token, resumable=True)
        print(f"  Container: {curl_container_id}")
        _upload_resumable_video_with_curl(curl_container_id, local_path, token)
        return curl_container_id
    except Exception as curl_error:
        print(f"  Curl binary upload failed: {curl_error}")
        print("  Trying hosted resumable upload fallback...")

    last_error = None
    for host_name, file_url in _upload_to_temp_hosts(local_path):
        print(f"  Hosted URL ({host_name}): {file_url}")
        is_valid, validation = _validate_hosted_video_url(file_url)
        if not is_valid:
            print(f"  {host_name} skipped: hosted URL returned {validation}")
            last_error = validation
            continue

        print(f"  Hosted URL content type: {validation}")
        print("  Creating fallback resumable upload container...")
        fallback_container_id = _create_reel_container(ig_user_id, caption, token, resumable=True)
        print(f"  Container: {fallback_container_id}")
        try:
            _upload_resumable_file_url(fallback_container_id, file_url, token)
            return fallback_container_id
        except Exception as hosted_error:
            print(f"  {host_name} fallback failed: {hosted_error}")
            last_error = hosted_error

    raise Exception(f"Hosted fallback failed for all temp hosts. Last error: {last_error}")


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


def _prepare_local_video(local_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise Exception(
            "ffmpeg is required for Instagram local video uploads. "
            "Install ffmpeg so the MP4 can be normalized before Meta processing."
        )

    fd, normalized_path = tempfile.mkstemp(suffix="_instagram.mp4")
    os.close(fd)

    print("  Normalizing MP4 for Instagram processing...")
    result = subprocess.run([
        ffmpeg,
        "-y",
        "-i", local_path,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-vf", "scale=1080:1920:flags=lanczos:in_range=pc:out_range=tv,format=yuv420p",
        "-c:v", "libx264",
        "-profile:v", "main",
        "-level", "4.0",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-bf", "0",
        "-refs", "1",
        "-b:v", "5M",
        "-maxrate", "8M",
        "-bufsize", "10M",
        "-color_range", "tv",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        "-brand", "mp42",
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
        account = _resolve_ig_account(token)
        token_data = {"access_token": token, "user_access_token": token, **account}
        _save_token({**token_data, "token_type": "fb_login_for_business"})
        print(f"  Using provided token (Instagram account: {account['ig_user_id']})")
    else:
        token_data = authenticate()
    ig_user_id = token_data["ig_user_id"]

    is_local = os.path.isfile(video_url)
    token = _publishing_token(token_data, require_page_token=is_local)
    cleanup_path = None

    try:
        if is_local:
            file_size = os.path.getsize(video_url)
            print(f"  Local file: {video_url} ({file_size / 1024 / 1024:.1f} MB)")
            upload_path, cleanup_path = _prepare_local_video(video_url)
            container_id = _upload_resumable_with_fallback(
                ig_user_id, caption, upload_path, token
            )
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
