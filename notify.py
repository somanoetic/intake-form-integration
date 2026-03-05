"""Send email notifications via Gmail API for intake import errors."""

import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]


def _build_gmail_service():
    creds = Credentials.from_authorized_user_file(config.GOOGLE_SHEETS_TOKEN, SCOPES)
    return build("gmail", "v1", credentials=creds)


def _send_email(to_emails, subject, body_text):
    """Send an email to one or more recipients."""
    if not to_emails:
        print("  WARNING: No NOTIFY_EMAILS configured, skipping notification")
        return

    msg = MIMEText(body_text)
    msg["To"] = ", ".join(to_emails)
    msg["From"] = "me"
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service = _build_gmail_service()
    service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    print(f"  Notification sent to {', '.join(to_emails)}")


def send_error_email(errors):
    """Send an email listing intake import errors."""
    if not errors:
        return

    lines = []
    for e in errors:
        lines.append(f"  Row {e['row_number']}: {e['patient_name']}\n    Error: {e['error']}")

    body_text = (
        f"Patient Intake Import: {len(errors)} error(s)\n"
        f"{'=' * 40}\n\n"
        + "\n\n".join(lines)
        + f"\n\nSpreadsheet: https://docs.google.com/spreadsheets/d/{config.SPREADSHEET_ID}/edit"
        + "\n\nCheck the 'Processed' column for error details."
    )

    _send_email(
        config.NOTIFY_EMAILS,
        f"Intake Import: {len(errors)} error(s) need attention",
        body_text,
    )


def send_success_email(count):
    """Send a summary email after successful import."""
    body_text = (
        f"Patient Intake Import: {count} submission(s) processed successfully.\n\n"
        f"Spreadsheet: https://docs.google.com/spreadsheets/d/{config.SPREADSHEET_ID}/edit"
    )

    _send_email(
        config.NOTIFY_EMAILS,
        f"Intake Import: {count} submission(s) processed",
        body_text,
    )
