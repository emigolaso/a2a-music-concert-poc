from __future__ import annotations

import base64
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8787/callback"
SCOPES = "user-top-read user-read-recently-played"


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def upsert_env_values(path: Path, updates: dict[str, str]) -> None:
    existing_lines = path.read_text().splitlines() if path.exists() else []
    touched: set[str] = set()
    new_lines: list[str] = []
    for line in existing_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            new_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            touched.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in touched:
            new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n")


class CallbackServer(BaseHTTPRequestHandler):
    auth_code: str | None = None
    auth_error: str | None = None
    expected_state: str | None = None
    finished = threading.Event()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        returned_state = params.get("state", [None])[0]
        if returned_state != self.expected_state:
            self._respond(400, "State mismatch. You can close this tab.")
            self.auth_error = "State mismatch from Spotify callback."
            self.finished.set()
            return

        error = params.get("error", [None])[0]
        code = params.get("code", [None])[0]
        if error:
            self._respond(400, f"Spotify returned an error: {error}")
            self.auth_error = f"Spotify returned an error: {error}"
        elif code:
            self._respond(200, "Spotify auth complete. You can close this tab and return to the terminal.")
            self.auth_code = code
        else:
            self._respond(400, "No code found in callback. You can close this tab.")
            self.auth_error = "No authorization code found in callback."
        self.finished.set()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _respond(self, status: int, body: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def exchange_code_for_refresh_token(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> str:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = httpx.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Spotify did not return a refresh_token.")
    return refresh_token


def main() -> None:
    if not ENV_PATH.exists():
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text())

    env = load_env_file(ENV_PATH)
    client_id = env.get("SPOTIFY_CLIENT_ID", "")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET", "")
    redirect_uri = env.get("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI)

    if not client_id or not client_secret:
        raise SystemExit(
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env before running this script."
        )

    parsed = urlparse(redirect_uri)
    if parsed.hostname != "127.0.0.1":
        raise SystemExit("SPOTIFY_REDIRECT_URI must point to 127.0.0.1 for this helper.")

    state = secrets.token_urlsafe(16)
    CallbackServer.expected_state = state
    CallbackServer.auth_code = None
    CallbackServer.auth_error = None
    CallbackServer.finished.clear()

    server = HTTPServer((parsed.hostname, parsed.port or 8787), CallbackServer)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    auth_url = "https://accounts.spotify.com/authorize?" + urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
            "show_dialog": "true",
        }
    )
    print("Opening Spotify authorization flow in your browser...")
    print(auth_url)
    webbrowser.open(auth_url)

    print("Waiting for Spotify callback on http://127.0.0.1:8787/callback ...")
    CallbackServer.finished.wait(timeout=1800)
    server.server_close()

    if CallbackServer.auth_error:
        raise SystemExit(CallbackServer.auth_error)
    if not CallbackServer.auth_code:
        raise SystemExit("Timed out waiting for Spotify callback.")

    refresh_token = exchange_code_for_refresh_token(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        code=CallbackServer.auth_code,
    )
    upsert_env_values(
        ENV_PATH,
        {
            "SPOTIFY_REDIRECT_URI": redirect_uri,
            "SPOTIFY_REFRESH_TOKEN": refresh_token,
        },
    )
    print("Updated .env with SPOTIFY_REFRESH_TOKEN.")


if __name__ == "__main__":
    main()
