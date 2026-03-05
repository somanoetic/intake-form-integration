import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── DrChrono (reused from gcal-drchrono-sync) ────────────────────────
DRCHRONO_CLIENT_ID = os.getenv("DRCHRONO_CLIENT_ID", "")
DRCHRONO_CLIENT_SECRET = os.getenv("DRCHRONO_CLIENT_SECRET", "")
DRCHRONO_REDIRECT_URI = os.getenv("DRCHRONO_REDIRECT_URI", "http://localhost:8080/callback")
DRCHRONO_DOCTOR_ID = os.getenv("DRCHRONO_DOCTOR_ID", "")
DRCHRONO_API_BASE = "https://app.drchrono.com/api"
DRCHRONO_TOKEN_URL = "https://drchrono.com/o/token/"
DRCHRONO_AUTH_URL = "https://drchrono.com/o/authorize/"

# Token file — separate from gcal-drchrono-sync
DRCHRONO_TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".drchrono_token.json")

# ── Google Sheets ─────────────────────────────────────────────────────
GOOGLE_SHEETS_CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials.json")
GOOGLE_SHEETS_TOKEN = os.path.join(os.path.dirname(__file__), "token.json")
SPREADSHEET_ID = os.getenv("INTAKE_SPREADSHEET_ID", "")

# Worksheet name where form responses land
RESPONSES_SHEET = os.getenv("INTAKE_RESPONSES_SHEET", "Form Responses 1")

# Column name used to mark rows as processed
PROCESSED_COLUMN = "Processed"

# ── Notifications ────────────────────────────────────────────────────
_notify = os.getenv("NOTIFY_EMAILS", "")
NOTIFY_EMAILS = [e.strip() for e in _notify.split(",") if e.strip()]

# ── State ─────────────────────────────────────────────────────────────
STATE_FILE = os.path.join(os.path.dirname(__file__), "intake_state.json")
