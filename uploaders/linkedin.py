"""LinkedIn poster using Posts API (REST)."""

import os
import json
import time
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
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
ORGANIZATION_SCOPES = "w_organization_social"
MEMBER_SCOPES = "openid profile w_member_social"
LINKEDIN_VERSION = "202604"
CALLBACK_TIMEOUT_SECONDS = 600


LINKEDIN_CONFIG_SNIPPET = '''
    "linkedin": {
        "client_id": "YOUR_LINKEDIN_CLIENT_ID",
        "client_secret": "YOUR_LINKEDIN_CLIENT_SECRET",
        "post_as": "member",
        "scopes": "openid profile w_member_social",
        "redirect_uri": "http://localhost:8585/callback"
    }
'''.strip()


def _is_configured(value):
    if not value or not isinstance(value, str):
        return False
    return not value.startswith(("YOUR_", "OPTIONAL_"))


def _config_error(message):
    raise RuntimeError(
        f"LinkedIn config error: {message}\n\n"
        "Add or update this block in config.json:\n"
        f"{LINKEDIN_CONFIG_SNIPPET}\n\n"
        "Then run:\n"
        "  python3.10 poster.py setup linkedin\n"
        "  python3.10 poster.py verify linkedin"
    )


def _load_config():
    if not os.path.exists(CONFIG_FILE):
        _config_error("config.json was not found. Copy config.example.json to config.json first.")

    with open(CONFIG_FILE, encoding="utf-8-sig") as f:
        config = json.load(f)

    if "linkedin" not in config:
        _config_error("missing 'linkedin' section.")

    cfg = config["linkedin"]
    if not isinstance(cfg, dict):
        _config_error("'linkedin' section must be a JSON object.")

    missing = [key for key in ("client_id", "client_secret") if not _is_configured(cfg.get(key))]
    post_as = _post_as(cfg)
    if post_as not in {"member", "organization"}:
        _config_error("'post_as' must be either 'member' or 'organization'.")
    if post_as == "organization" and not _is_configured(cfg.get("organization_id")):
        missing.append("organization_id")
    if missing:
        _config_error("missing required key(s): " + ", ".join(missing))

    return cfg


def _load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8-sig") as f:
            return json.load(f)
    return None


def _save_token(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _token_valid(token_data):
    if not token_data or not token_data.get("access_token"):
        return False
    expires_at = token_data.get("expires_at", 0)
    return time.time() < expires_at - 300  # 5min buffer


def _post_as(cfg):
    return (cfg.get("post_as") or "organization").strip().lower()


def _scopes_for_config(cfg):
    configured = cfg.get("scopes")
    if configured:
        return configured.strip()
    return MEMBER_SCOPES if _post_as(cfg) == "member" else ORGANIZATION_SCOPES


def _token_matches_config(token_data, cfg):
    if not _token_valid(token_data):
        return False
    return (
        token_data.get("post_as") == _post_as(cfg)
        and token_data.get("scopes") == _scopes_for_config(cfg)
    )


def _linkedin_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_VERSION,
    }


def _resolve_member_author_urn(access_token, cfg):
    person_id = cfg.get("person_id") or cfg.get("member_id")
    if person_id:
        return f"urn:li:person:{person_id}"

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        r = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if data.get("sub"):
                return f"urn:li:person:{data['sub']}"
    except requests.RequestException:
        pass

    try:
        r = requests.get("https://api.linkedin.com/v2/me", headers=_linkedin_headers(access_token), timeout=20)
        if r.status_code == 200:
            data = r.json()
            if data.get("id"):
                return f"urn:li:person:{data['id']}"
    except requests.RequestException:
        pass

    raise Exception(
        "Could not resolve your LinkedIn member id. Add 'person_id' to config.json under linkedin, "
        "or enable OpenID Connect and use scopes: 'openid profile w_member_social'."
    )


def authenticate():
    """OAuth2 3-legged flow for LinkedIn. Opens browser for consent."""
    cfg = _load_config()
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    redirect_uri = cfg.get("redirect_uri", REDIRECT_URI)
    post_as = _post_as(cfg)
    scopes = _scopes_for_config(cfg)

    # Check existing token
    token_data = _load_token()
    if _token_matches_config(token_data, cfg):
        print("  LinkedIn: existing token still valid.")
        return token_data

    state = secrets.token_urlsafe(16)
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scopes,
        }
    )

    # Capture the auth code via local HTTP server
    auth_code = [None]
    auth_error = [None]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            received_state = qs.get("state", [None])[0]
            if received_state != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch - possible CSRF attack.")
                return
            if qs.get("error"):
                error = qs.get("error", ["unknown"])[0]
                description = qs.get("error_description", [""])[0]
                auth_error[0] = f"{error}: {description}".strip()
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<h2>LinkedIn authorization failed</h2><p>{auth_error[0]}</p>".encode("utf-8")
                )
                return
            auth_code[0] = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>LinkedIn authorized! You can close this tab.</h2>")

        def log_message(self, format, *args):
            pass  # suppress noisy logs

    print("  Opening browser for LinkedIn login...")
    print(f"  Posting mode: {post_as}")
    print(f"  Requested scopes: {scopes}")
    print(f"  Redirect URI must be registered in LinkedIn: {redirect_uri}")
    print(f"  If the browser does not open, visit this URL:\n  {auth_url}")
    webbrowser.open(auth_url)

    parsed_redirect = urlparse(redirect_uri)
    can_capture_localhost = parsed_redirect.hostname in {"localhost", "127.0.0.1"}
    if can_capture_localhost:
        port = parsed_redirect.port or 80
        server = HTTPServer((parsed_redirect.hostname, port), Handler)
        server.timeout = CALLBACK_TIMEOUT_SECONDS
        server.handle_request()

    if not auth_code[0] and auth_error[0]:
        raise Exception(f"LinkedIn authorization failed: {auth_error[0]}")

    if not auth_code[0]:
        manual = input("  Paste final redirect URL or code here (Enter to cancel): ").strip()
        if manual:
            if manual.startswith("http"):
                qs = parse_qs(urlparse(manual).query)
                if qs.get("state", [state])[0] != state:
                    raise Exception("State mismatch in pasted LinkedIn redirect URL")
                if qs.get("error"):
                    error = qs.get("error", ["unknown"])[0]
                    description = qs.get("error_description", [""])[0]
                    raise Exception(f"LinkedIn authorization failed: {error}: {description}")
                auth_code[0] = qs.get("code", [None])[0]
            else:
                auth_code[0] = manual

    if not auth_code[0]:
        raise Exception("No authorization code received from LinkedIn")

    # Exchange code for token
    r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "authorization_code",
        "code": auth_code[0],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    r.raise_for_status()
    data = r.json()

    if "access_token" not in data:
        raise Exception(f"Token exchange failed: {data}")

    token_data = {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 5184000),
        "expires_at": time.time() + data.get("expires_in", 5184000),
        "post_as": post_as,
        "scopes": scopes,
    }
    if post_as == "member":
        token_data["author_urn"] = _resolve_member_author_urn(data["access_token"], cfg)
    _save_token(token_data)
    print("  LinkedIn authenticated!")
    return token_data


def post(text):
    """Post a text update to LinkedIn."""
    cfg = _load_config()
    post_as = _post_as(cfg)

    token_data = _load_token()
    if not _token_matches_config(token_data, cfg):
        token_data = authenticate()

    access_token = token_data["access_token"]
    if post_as == "member":
        author = token_data.get("author_urn") or _resolve_member_author_urn(access_token, cfg)
    else:
        org_id = cfg["organization_id"]
        author = f"urn:li:organization:{org_id}"

    payload = {
        "author": author,
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


def print_setup_status():
    cfg = _load_config()
    post_as = _post_as(cfg)
    scopes = _scopes_for_config(cfg)
    token_data = _load_token()
    ready = _token_matches_config(token_data, cfg)

    print("LinkedIn setup status")
    print(f"  post_as: {post_as}")
    print(f"  scopes: {scopes}")
    print(f"  redirect_uri: {cfg.get('redirect_uri', REDIRECT_URI)}")
    print(f"  token_file: {os.path.exists(TOKEN_FILE)}")
    print(f"  token_valid_for_config: {ready}")
    if post_as == "organization":
        print(f"  organization_id_present: {bool(cfg.get('organization_id'))}")
    else:
        print(f"  person_id_present: {bool(cfg.get('person_id') or cfg.get('member_id'))}")
    return ready
