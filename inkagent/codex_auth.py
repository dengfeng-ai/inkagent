"""OpenAI Codex OAuth 2.0 + PKCE authentication.

Authenticates against OpenAI's Codex endpoint using a ChatGPT subscription.
Tokens are stored at ~/.inkagent/codex-auth.json.

Usage:
    python -m agent.codex_auth          # interactive login
    python -m agent.codex_auth status   # check login status
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import logging
import os
import secrets
import sys
import time
import urllib.parse
import webbrowser

import httpx

logger = logging.getLogger(__name__)

AUTH_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPES = "openid profile email offline_access"
TOKEN_FILE = os.path.expanduser("~/.inkagent/codex-auth.json")

# Refresh proactively when within this many seconds of expiry.
_REFRESH_MARGIN = 300


class CodexAuth:
    """Manages OAuth tokens for the OpenAI Codex endpoint."""

    def __init__(self) -> None:
        self._tokens: dict | None = self._load_tokens()

    # ── Token persistence ────────────────────────────────────────────

    def _load_tokens(self) -> dict | None:
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load token file: %s", e)
        return None

    def _save_tokens(self, tokens: dict) -> None:
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            json.dump(tokens, f, indent=2)
        self._tokens = tokens

    # ── Public API ───────────────────────────────────────────────────

    def is_logged_in(self) -> bool:
        return self._tokens is not None and "refresh_token" in self._tokens

    def login(self) -> None:
        """Run the full OAuth PKCE flow (opens browser, waits for callback)."""
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)

        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "codex_cli_simplified_flow": "true",
        }
        auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

        print(f"\nOpen this URL to authorize inkagent:\n\n  {auth_url}\n")
        webbrowser.open(auth_url)

        code = self._wait_for_callback(state)
        self._exchange_code(code, verifier)
        print("Login successful!")

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing automatically if needed."""
        if not self._tokens:
            raise RuntimeError(
                "Codex not authenticated. Run `python -m agent.codex_auth` to log in."
            )
        if time.time() > self._tokens.get("expires_at", 0) - _REFRESH_MARGIN:
            self._refresh()
        return self._tokens["access_token"]

    def get_account_id(self) -> str:
        if not self._tokens:
            raise RuntimeError("Codex not authenticated.")
        return self._tokens.get("account_id", "")

    # ── OAuth flow helpers ───────────────────────────────────────────

    def _wait_for_callback(self, expected_state: str) -> str:
        """Start a temporary HTTP server on port 1455 to capture the OAuth callback.

        Loops over individual requests so stray hits (favicon, browser
        preconnect/probes) don't consume the one chance to read the code.
        """
        result: dict[str, str | None] = {"code": None, "error": None}

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)

                # Ignore anything that isn't the OAuth callback (favicon, probes).
                if parsed.path != "/auth/callback":
                    self.send_response(404)
                    self.end_headers()
                    return

                if params.get("error"):
                    result["error"] = params.get(
                        "error_description", params.get("error")
                    )[0]
                elif params.get("state", [None])[0] == expected_state:
                    result["code"] = params.get("code", [None])[0]

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authorization successful!</h1>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                    b"</body></html>"
                )

            def log_message(self, format: str, *args: object) -> None:
                pass  # suppress server logs

        print("Waiting for authorization (listening on localhost:1455)...")
        server = http.server.HTTPServer(("localhost", 1455), _Handler)
        server.timeout = 5  # poll interval; overall deadline enforced below
        deadline = time.time() + 300
        while result["code"] is None and result["error"] is None and time.time() < deadline:
            server.handle_request()
        server.server_close()

        if result["error"]:
            raise RuntimeError(f"OAuth provider returned an error: {result['error']}")
        if not result["code"]:
            raise RuntimeError(
                "OAuth callback did not receive an authorization code (timed out "
                "after 5 minutes). Make sure you completed the browser consent."
            )
        return result["code"]  # type: ignore[return-value]

    def _exchange_code(self, code: str, verifier: str) -> None:
        """Exchange the authorization code for access + refresh tokens."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
        }
        resp = httpx.post(TOKEN_URL, data=data, timeout=30)
        resp.raise_for_status()
        tokens = resp.json()

        tokens["account_id"] = self._extract_account_id(tokens.get("access_token", ""))
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        self._save_tokens(tokens)

    def _refresh(self) -> None:
        """Refresh the access token using the stored refresh token."""
        if not self._tokens or "refresh_token" not in self._tokens:
            raise RuntimeError("No refresh token available. Re-run login.")

        logger.info("Refreshing Codex access token...")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._tokens["refresh_token"],
            "client_id": CLIENT_ID,
        }
        resp = httpx.post(TOKEN_URL, data=data, timeout=30)
        resp.raise_for_status()
        new_tokens = resp.json()

        # Preserve account_id; update expiry.
        new_tokens["account_id"] = self._tokens.get("account_id", "")
        new_tokens["expires_at"] = time.time() + new_tokens.get("expires_in", 3600)
        self._save_tokens(new_tokens)

    @staticmethod
    def _extract_account_id(jwt_token: str) -> str:
        """Decode a JWT payload (without verification) to extract chatgpt_account_id."""
        try:
            payload_b64 = jwt_token.split(".")[1]
            # Add base64 padding.
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("https://api.openai.com/auth", {}).get(
                "chatgpt_account_id", ""
            )
        except Exception:
            logger.warning("Could not extract account_id from JWT.")
            return ""


# ── Singleton ────────────────────────────────────────────────────────

_auth: CodexAuth | None = None


def get_codex_auth() -> CodexAuth:
    """Return the singleton CodexAuth instance."""
    global _auth
    if _auth is None:
        _auth = CodexAuth()
    return _auth


# ── CLI entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    # Windows console defaults to cp1252 / charmap. Force UTF-8 so any
    # non-ASCII content (URLs, error messages) doesn't crash print().
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO)
    auth = CodexAuth()

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        if auth.is_logged_in():
            print("Logged in.")
            print(f"  Token file: {TOKEN_FILE}")
            expires = auth._tokens.get("expires_at", 0) if auth._tokens else 0
            remaining = max(0, expires - time.time())
            print(f"  Token expires in: {int(remaining)}s")
        else:
            print("Not logged in.")
        sys.exit(0)

    if auth.is_logged_in():
        print("Already logged in. Re-authenticating...")
    auth.login()
