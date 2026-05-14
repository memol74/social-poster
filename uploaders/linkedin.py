"""LinkedIn company page poster using Posts API (REST)."""

import os
import json
import time
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
import requests

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
TOKEN_FILE = os.path.join(ROOT, "tokens", "linkedin_token.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")
REDIRECT_URI = "http://localhost:8585/callback"
SCOPES = "w_organization_social"
LINKEDIN_VERSION = "202604"


def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)["linkedin"]


def _load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def _save_token(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _token_valid(token_data):
    if not token_data or not token_data.get("access_token"):
        return False
    expires_at = token_data.get("expires_at", 0)
    return time.time() < expires_at - 300  # 5min buffer


def authenticate():
    """OAuth2 3-legged flow for LinkedIn. Opens browser for consent."""
    cfg = _load_config()
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]

    # Check existing token
    token_data = _load_token()
    if _token_valid(token_data):
        print("  LinkedIn: existing token still valid.")
        return token_data

    state = secrets.token_urlsafe(16)
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&scope={SCOPES}"
    )

    # Capture the auth code via local HTTP server
    auth_code = [None]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            received_state = qs.get("state", [None])[0]
            if received_state != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch - possible CSRF attack.")
                return
            auth_code[0] = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>LinkedIn authorized! You can close this tab.</h2>")

        def log_message(self, format, *args):
            pass  # suppress noisy logs

    print("  Opening browser for LinkedIn login...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8585), Handler)
    server.timeout = 120
    server.handle_request()

    if not auth_code[0]:
        raise Exception("No authorization code received from LinkedIn")

    # Exchange code for token
    r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "authorization_code",
        "code": auth_code[0],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    r.raise_for_status()
    data = r.json()

    if "access_token" not in data:
        raise Exception(f"Token exchange failed: {data}")

    token_data = {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 5184000),
        "expires_at": time.time() + data.get("expires_in", 5184000),
    }
    _save_token(token_data)
    print("  LinkedIn authenticated!")
    return token_data


def post(text):
    """Post a text update to the company page."""
    cfg = _load_config()
    org_id = cfg["organization_id"]

    token_data = _load_token()
    if not _token_valid(token_data):
        token_data = authenticate()

    access_token = token_data["access_token"]

    payload = {
        "author": f"urn:li:organization:{org_id}",
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    r = requests.post(
        "https://api.linkedin.com/rest/posts",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "Content-Type": "application/json",
        },
    )

    if r.status_code == 201:
        post_id = r.headers.get("x-restli-id", "unknown")
        print(f"  LinkedIn post published! ID: {post_id}")
        return post_id
    else:
        raise Exception(f"LinkedIn post failed ({r.status_code}): {r.text}")
