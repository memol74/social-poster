"""TikTok video uploader using Content Posting API."""

import os
import json
import time
import base64
import hashlib
import secrets
import webbrowser
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
import requests
from urllib.parse import urlparse, parse_qs

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
TOKEN_FILE = os.path.join(ROOT, "tokens", "tiktok_token.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")
API_URL = "https://open.tiktokapis.com/v2"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
REDIRECT_URI = "https://noborta.ai/tiktok-callback"
SCOPES = "user.info.basic,video.publish,video.upload"


def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)["tiktok"]


def _load_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)


def _save_token(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def authenticate():
    """OAuth2 flow for TikTok. Opens browser for login."""
    cfg = _load_config()
    client_key = cfg["client_key"]
    client_secret = cfg["client_secret"]
    print(f"  Config loaded from: {CONFIG_FILE}")
    print(f"  client_key: {client_key[:6]}...{client_key[-4:]}")

    # Check for existing valid token
    if os.path.exists(TOKEN_FILE):
        token_data = _load_token()
        if token_data.get("access_token"):
            # Try refreshing if we have a refresh token
            if token_data.get("refresh_token"):
                try:
                    return _refresh_token(client_key, client_secret, token_data["refresh_token"])
                except Exception:
                    pass  # Fall through to re-auth

    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    auth_params = (
        f"?client_key={client_key}"
        f"&scope={SCOPES}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    auth_code = None

    print(f"  Opening browser for TikTok login...")
    webbrowser.open(AUTH_URL + auth_params)

    print("  After logging in, the browser will redirect to a page that won't load.")
    print("  Copy the FULL URL from your browser's address bar.\n")
    redirect_url = input("  Paste redirect URL: ").strip()

    # Extract code from URL
    parsed = parse_qs(urlparse(redirect_url).query)
    auth_code = parsed.get("code", [None])[0]

    if not auth_code:
        raise Exception("No authorization code found in URL")

    # Exchange code for token
    r = requests.post(f"{API_URL}/oauth/token/", data={
        "client_key": client_key,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    })
    r.raise_for_status()
    data = r.json()

    if "error" in data and data["error"]:
        raise Exception(f"Token error: {data.get('error_description', data['error'])}")

    token_data = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "open_id": data.get("open_id", ""),
        "expires_in": data.get("expires_in"),
    }
    _save_token(token_data)
    print(f"  TikTok authenticated! open_id: {token_data['open_id']}")
    return token_data


def _refresh_token(client_key, client_secret, refresh_token):
    """Refresh an expired access token."""
    r = requests.post(f"{API_URL}/oauth/token/", data={
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    r.raise_for_status()
    data = r.json()
    if "error" in data and data["error"]:
        raise Exception(f"Refresh failed: {data.get('error_description', data['error'])}")

    token_data = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "open_id": data.get("open_id", ""),
        "expires_in": data.get("expires_in"),
    }
    _save_token(token_data)
    return token_data


def upload(video_path, description="", privacy="SELF_ONLY"):
    """Upload a video to TikTok.
    
    privacy: SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR, PUBLIC_TO_EVERYONE
    In sandbox mode, only SELF_ONLY works.
    """
    token_data = authenticate()
    token = token_data["access_token"]
    file_size = os.path.getsize(video_path)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Step 1: Initialize upload
    init_body = {
        "post_info": {
            "title": description[:150],  # TikTok max 150 chars
            "privacy_level": privacy,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }

    r = requests.post(
        f"{API_URL}/post/publish/video/init/",
        headers=headers,
        json=init_body,
    )
    if not r.ok:
        raise Exception(f"Init failed ({r.status_code}): {r.text}")
    resp = r.json()

    if resp.get("error", {}).get("code") != "ok":
        raise Exception(f"Init failed: {resp.get('error', resp)}")

    publish_id = resp["data"]["publish_id"]
    upload_url = resp["data"]["upload_url"]
    print(f"  Publish ID: {publish_id}")

    # Step 2: Upload video binary
    with open(video_path, "rb") as f:
        video_data = f.read()

    r = requests.put(upload_url, headers={
        "Content-Type": "video/mp4",
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
    }, data=video_data)
    r.raise_for_status()
    print(f"  Video uploaded ({file_size // (1024*1024)} MB)")

    # Step 3: Check status
    for i in range(18):  # 3 minutes max
        time.sleep(10)
        r = requests.post(
            f"{API_URL}/post/publish/status/fetch/",
            headers=headers,
            json={"publish_id": publish_id},
        )
        r.raise_for_status()
        status = r.json()
        state = status.get("data", {}).get("status", "UNKNOWN")
        print(f"  Processing... {state}")
        if state == "PUBLISH_COMPLETE":
            print(f"  Done: TikTok video published!")
            return publish_id
        elif state in ("FAILED", "PUBLISH_FAILED"):
            raise Exception(f"Publish failed: {status}")

    raise Exception("Processing timed out (3 min)")
