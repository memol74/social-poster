"""TikTok video uploader using Content Posting API."""

import os
import json
import time
import ssl
import base64
import hashlib
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
import requests
from urllib.parse import urlparse, parse_qs, urlencode

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
TOKEN_FILE = os.path.join(ROOT, "tokens", "tiktok_token.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")
CALLBACK_CERT_FILE = os.path.join(ROOT, "tokens", "_cert.pem")
CALLBACK_KEY_FILE = os.path.join(ROOT, "tokens", "_key.pem")
API_URL = "https://open.tiktokapis.com/v2"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
DEFAULT_REDIRECT_URI = "https://noborta.ai/tiktok-callback"
SCOPES = "user.info.basic,video.publish,video.upload"
LOCAL_REDIRECT_HOSTS = {"localhost", "127.0.0.1"}
AUTH_CALLBACK_TIMEOUT_SECONDS = 180
REQUEST_TIMEOUT_SECONDS = 120
TIKTOK_MIN_UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024
TIKTOK_TARGET_UPLOAD_CHUNK_SIZE = 10 * 1024 * 1024
ALLOWED_PRIVACY_LEVELS = {
    "SELF_ONLY",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "PUBLIC_TO_EVERYONE",
}


def _load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)["tiktok"]


def _load_token():
    with open(TOKEN_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_token(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _mask_value(value, prefix=6, suffix=4):
    if not value:
        return ""
    if len(value) <= prefix + suffix:
        return value
    return f"{value[:prefix]}...{value[-suffix:]}"


def _get_redirect_uri(cfg):
    configured = cfg.get("redirect_uri", "").strip()
    return configured or DEFAULT_REDIRECT_URI


def _get_redirect_capture_mode(redirect_uri):
    parsed = urlparse(redirect_uri)
    if parsed.scheme in {"http", "https"} and parsed.hostname in LOCAL_REDIRECT_HOSTS:
        return "localhost"
    return "manual"


def _get_local_callback_details(redirect_uri):
    parsed = urlparse(redirect_uri)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported redirect URI scheme for localhost callback: {parsed.scheme}")
    if parsed.hostname not in LOCAL_REDIRECT_HOSTS:
        raise ValueError("Redirect URI is not a localhost callback")

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    path = parsed.path or "/"
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": port,
        "path": path,
    }


def _extract_auth_code_from_input(user_input):
    raw = user_input.strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        query = parse_qs(parsed.query)
        return query.get("code", [None])[0]

    if "=" in raw:
        query = parse_qs(raw.lstrip("?"))
        return query.get("code", [None])[0]

    return raw


def _token_matches_client(token_data, client_key):
    if not token_data:
        return False
    token_client_key = token_data.get("client_key")
    return bool(token_client_key) and token_client_key == client_key


def _plan_upload_chunks(file_size):
    if file_size <= 0:
        raise ValueError("Video file is empty")

    if file_size <= TIKTOK_TARGET_UPLOAD_CHUNK_SIZE:
        return file_size, 1

    total_chunk_count = (file_size + TIKTOK_TARGET_UPLOAD_CHUNK_SIZE - 1) // TIKTOK_TARGET_UPLOAD_CHUNK_SIZE
    while total_chunk_count > 1:
        chunk_size = (file_size + total_chunk_count - 1) // total_chunk_count
        last_chunk_size = file_size - (chunk_size * (total_chunk_count - 1))
        if last_chunk_size >= TIKTOK_MIN_UPLOAD_CHUNK_SIZE:
            return chunk_size, total_chunk_count
        total_chunk_count -= 1

    return file_size, 1


def _tiktok_error_code(response_json):
    return response_json.get("error", {}).get("code")


def _init_upload(headers, description, privacy, file_size, chunk_size, total_chunk_count):
    init_body = {
        "post_info": {
            "title": description[:150],  # TikTok max 150 chars
            "privacy_level": privacy,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }

    r = requests.post(
        f"{API_URL}/post/publish/video/init/",
        headers=headers,
        json=init_body,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not r.ok:
        raise Exception(f"Init failed ({r.status_code}): {r.text}")

    resp = r.json()
    if _tiktok_error_code(resp) != "ok":
        raise Exception(f"Init failed: {resp.get('error', resp)}")

    return resp


def _capture_auth_code_locally(redirect_uri, state, timeout_seconds=AUTH_CALLBACK_TIMEOUT_SECONDS):
    details = _get_local_callback_details(redirect_uri)
    auth_result = {"code": None, "error": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            request = urlparse(self.path)
            if request.path != details["path"]:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"TikTok callback path not found.")
                return

            query = parse_qs(request.query)
            received_state = query.get("state", [None])[0]
            if received_state != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch.")
                return

            error = query.get("error", [None])[0]
            if error:
                description = query.get("error_description", [error])[0]
                auth_result["error"] = description
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>TikTok authorization failed. You can close this tab.</h2>")
                return

            auth_result["code"] = query.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>TikTok authorized! You can close this tab.</h2>")

    try:
        server = HTTPServer((details["host"], details["port"]), Handler)
    except OSError as exc:
        raise RuntimeError(
            f"Could not start local TikTok callback server on {details['host']}:{details['port']}: {exc}"
        ) from exc

    try:
        if details["scheme"] == "https":
            if not os.path.exists(CALLBACK_CERT_FILE) or not os.path.exists(CALLBACK_KEY_FILE):
                raise RuntimeError(
                    "HTTPS localhost callback requires tokens/_cert.pem and tokens/_key.pem"
                )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(CALLBACK_CERT_FILE, CALLBACK_KEY_FILE)
            server.socket = context.wrap_socket(server.socket, server_side=True)

        server.timeout = timeout_seconds
        print(
            f"  Waiting for TikTok callback on {details['scheme']}://{details['host']}:{details['port']}{details['path']}"
        )
        if details["scheme"] == "https":
            print("  Your browser may show a localhost certificate warning before redirect completes.")
        server.handle_request()
    finally:
        server.server_close()

    if auth_result["error"]:
        raise RuntimeError(f"TikTok authorization failed: {auth_result['error']}")
    if not auth_result["code"]:
        raise RuntimeError("No authorization code received from TikTok localhost callback")
    return auth_result["code"]


def get_setup_status():
    """Inspect local TikTok setup without making network calls."""
    status = {
        "config_file": CONFIG_FILE,
        "token_file": TOKEN_FILE,
        "redirect_uri": DEFAULT_REDIRECT_URI,
        "redirect_uri_configured": False,
        "auth_capture": "manual",
        "scopes": SCOPES.split(","),
        "privacy_control": "manifest",
        "client_key": "",
        "token_present": os.path.exists(TOKEN_FILE),
        "access_token_present": False,
        "refresh_token_present": False,
        "open_id_present": False,
        "ready": False,
        "issues": [],
    }

    if not os.path.exists(CONFIG_FILE):
        status["issues"].append(f"Missing config file: {CONFIG_FILE}")
        return status

    try:
        cfg = _load_config()
    except (OSError, KeyError, ValueError) as exc:
        status["issues"].append(f"Could not read TikTok config: {exc}")
        return status

    client_key = cfg.get("client_key", "")
    client_secret = cfg.get("client_secret", "")
    status["redirect_uri"] = _get_redirect_uri(cfg)
    status["redirect_uri_configured"] = bool(cfg.get("redirect_uri", "").strip())
    status["auth_capture"] = _get_redirect_capture_mode(status["redirect_uri"])
    status["client_key"] = _mask_value(client_key)

    if not client_key or client_key.startswith("YOUR_"):
        status["issues"].append("TikTok client_key is missing in config.json")
    if not client_secret or client_secret.startswith("YOUR_"):
        status["issues"].append("TikTok client_secret is missing in config.json")
    if not status["redirect_uri_configured"]:
        status["issues"].append(
            "TikTok redirect_uri is not set in config.json; add it and register the exact same value in the TikTok developer portal"
        )

    if status["token_present"]:
        try:
            token_data = _load_token()
        except (OSError, ValueError) as exc:
            status["issues"].append(f"Could not read TikTok token file: {exc}")
        else:
            status["access_token_present"] = bool(token_data.get("access_token"))
            status["refresh_token_present"] = bool(token_data.get("refresh_token"))
            status["open_id_present"] = bool(token_data.get("open_id"))
            if not status["access_token_present"]:
                status["issues"].append("TikTok token file is missing access_token")
            if not status["refresh_token_present"]:
                status["issues"].append("TikTok token file is missing refresh_token for automatic renewal")
    else:
        status["issues"].append("TikTok OAuth token is missing; run `py poster.py setup tiktok`")

    status["ready"] = not status["issues"]
    return status


def print_setup_status():
    status = get_setup_status()
    print("TikTok setup status:")
    print(f"  Config file: {'OK' if os.path.exists(CONFIG_FILE) else 'MISSING'}")
    if status["client_key"]:
        print(f"  Client key: {status['client_key']}")
    print(f"  Token file: {'OK' if status['token_present'] else 'MISSING'}")
    if status["token_present"]:
        print(f"  Access token: {'OK' if status['access_token_present'] else 'MISSING'}")
        print(f"  Refresh token: {'OK' if status['refresh_token_present'] else 'MISSING'}")
    print(f"  Redirect URI: {status['redirect_uri']}")
    print(f"  Redirect URI configured: {'YES' if status['redirect_uri_configured'] else 'NO'}")
    print(f"  Auth capture: {'localhost callback server' if status['auth_capture'] == 'localhost' else 'manual pasteback'}")
    print(f"  Scopes: {', '.join(status['scopes'])}")
    print("  Privacy control: manifest value is sent to TikTok")
    print("  Register this exact Redirect URI in the TikTok developer portal")

    if status["issues"]:
        print("  Ready: NO")
        print("  Issues:")
        for issue in status["issues"]:
            print(f"    - {issue}")
    else:
        print("  Ready: YES")

    return status["ready"]


def authenticate():
    """OAuth2 flow for TikTok. Opens browser for login."""
    cfg = _load_config()
    client_key = cfg["client_key"]
    client_secret = cfg["client_secret"]
    redirect_uri = _get_redirect_uri(cfg)
    print(f"  Config loaded from: {CONFIG_FILE}")
    print(f"  client_key: {_mask_value(client_key)}")
    print(f"  redirect_uri: {redirect_uri}")

    # Check for existing valid token
    if os.path.exists(TOKEN_FILE):
        token_data = _load_token()
        if token_data.get("access_token") and _token_matches_client(token_data, client_key):
            # Try refreshing if we have a refresh token
            if token_data.get("refresh_token"):
                try:
                    return _refresh_token(client_key, client_secret, token_data["refresh_token"])
                except Exception:
                    pass  # Fall through to re-auth
        elif token_data.get("access_token"):
            print("  Existing TikTok token belongs to a different app key; re-authenticating with current config.")

    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    auth_params = "?" + urlencode({
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })

    auth_code = None
    auth_url = AUTH_URL + auth_params
    capture_mode = _get_redirect_capture_mode(redirect_uri)

    print("  Opening browser for TikTok login...")
    print("  If TikTok rejects the login with a redirect_uri error, the value above does not exactly match the one registered in the TikTok developer portal.")
    if capture_mode == "localhost":
        webbrowser.open(auth_url)
        auth_code = _capture_auth_code_locally(redirect_uri, state)
    else:
        print(f"  Auth URL: {auth_url}")
        webbrowser.open(auth_url)
        print("  After logging in, the browser will redirect to a page that won't load.")
        print("  Copy either the FULL redirect URL or just the code value from your browser's address bar.\n")
        redirect_input = input("  Paste redirect URL or code: ").strip()
        auth_code = _extract_auth_code_from_input(redirect_input)

    if not auth_code:
        raise Exception("No authorization code found in URL")

    # Exchange code for token
    r = requests.post(f"{API_URL}/oauth/token/", data={
        "client_key": client_key,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
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
        "client_key": client_key,
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
        "client_key": client_key,
    }
    _save_token(token_data)
    return token_data


def upload(video_path, description="", privacy="SELF_ONLY"):
    """Upload a video to TikTok.
    
    privacy: SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR, PUBLIC_TO_EVERYONE
    The caller controls privacy; TikTok app permissions still apply.
    """
    token_data = authenticate()
    token = token_data["access_token"]
    file_size = os.path.getsize(video_path)
    chunk_size, total_chunk_count = _plan_upload_chunks(file_size)

    if privacy not in ALLOWED_PRIVACY_LEVELS:
        allowed = ", ".join(sorted(ALLOWED_PRIVACY_LEVELS))
        raise ValueError(f"Invalid TikTok privacy '{privacy}'. Expected one of: {allowed}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Step 1: Initialize upload
    try:
        resp = _init_upload(headers, description, privacy, file_size, chunk_size, total_chunk_count)
    except Exception as exc:
        error_text = str(exc)
        if "unaudited_client_can_only_post_to_private_accounts" in error_text and privacy != "SELF_ONLY":
            print("  TikTok app is unaudited for public posting; retrying as SELF_ONLY.")
            privacy = "SELF_ONLY"
            resp = _init_upload(headers, description, privacy, file_size, chunk_size, total_chunk_count)
        else:
            raise

    publish_id = resp["data"]["publish_id"]
    upload_url = resp["data"]["upload_url"]
    print(f"  Publish ID: {publish_id}")
    print(f"  Privacy used: {privacy}")
    print(f"  Upload plan: {total_chunk_count} chunk(s) of up to {chunk_size // (1024 * 1024)} MB")

    # Step 2: Upload video binary in chunks
    uploaded_bytes = 0
    with open(video_path, "rb") as f:
        for chunk_index in range(total_chunk_count):
            bytes_remaining = file_size - uploaded_bytes
            expected_chunk_size = chunk_size
            if chunk_index == total_chunk_count - 1:
                expected_chunk_size = bytes_remaining

            chunk = f.read(expected_chunk_size)
            if not chunk:
                raise RuntimeError("Unexpected end of file while preparing TikTok upload chunks")
            if len(chunk) != expected_chunk_size:
                raise RuntimeError(
                    f"Prepared TikTok chunk size {len(chunk)} does not match expected {expected_chunk_size}"
                )

            chunk_start = uploaded_bytes
            chunk_end = uploaded_bytes + len(chunk) - 1
            uploaded_bytes += len(chunk)

            r = requests.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {chunk_start}-{chunk_end}/{file_size}",
                },
                data=chunk,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            r.raise_for_status()
            print(
                f"  Uploaded chunk {chunk_index + 1}/{total_chunk_count} "
                f"({len(chunk) // (1024 * 1024)} MB)"
            )

    print(f"  Video uploaded ({file_size // (1024 * 1024)} MB)")

    # Step 3: Check status
    for i in range(18):  # 3 minutes max
        time.sleep(10)
        r = requests.post(
            f"{API_URL}/post/publish/status/fetch/",
            headers=headers,
            json={"publish_id": publish_id},
            timeout=REQUEST_TIMEOUT_SECONDS,
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
