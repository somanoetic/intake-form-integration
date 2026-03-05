"""One-time DrChrono OAuth setup for the intake form project."""

import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

import config
import drchrono_client

REDIRECT_PORT = 8080
auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Authorization complete!</h2><p>You can close this tab.</p>")

    def log_message(self, format, *args):
        pass


def run():
    if not config.DRCHRONO_CLIENT_ID or not config.DRCHRONO_CLIENT_SECRET:
        print("ERROR: Set DRCHRONO_CLIENT_ID and DRCHRONO_CLIENT_SECRET in .env first.")
        return

    auth_url = (
        f"{config.DRCHRONO_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={config.DRCHRONO_CLIENT_ID}"
        f"&redirect_uri={config.DRCHRONO_REDIRECT_URI}"
    )
    print("Opening browser for DrChrono authorization...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
    print(f"Waiting for callback on http://localhost:{REDIRECT_PORT}/callback ...")
    while auth_code is None:
        server.handle_request()

    print("Got authorization code.")

    resp = requests.post(config.DRCHRONO_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": config.DRCHRONO_CLIENT_ID,
        "client_secret": config.DRCHRONO_CLIENT_SECRET,
        "redirect_uri": config.DRCHRONO_REDIRECT_URI,
    })
    resp.raise_for_status()
    token = resp.json()
    token["expires_at"] = time.time() + token.get("expires_in", 7200)
    drchrono_client._save_token(token)
    print("Tokens saved.")

    # Test the connection
    session = drchrono_client._get_session()
    resp = session.get(f"{config.DRCHRONO_API_BASE}/users/current")
    resp.raise_for_status()
    doctor_id = resp.json().get("doctor")
    print(f"\nConnected! Doctor ID: {doctor_id}")
    print(f"Make sure DRCHRONO_DOCTOR_ID={doctor_id} is in your .env")


if __name__ == "__main__":
    run()
