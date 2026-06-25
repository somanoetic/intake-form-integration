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


def send_review_email(pending):
    """Send an email listing intake rows awaiting a manual patient match."""
    if not pending:
        return

    sections = []
    for p in pending:
        lines = [
            f"  Row {p['row_number']}: {p['patient_name']}",
            f"    DOB: {p['dob']}   Email: {p['email']}   Phone: {p['phone']}",
            f"    Reason: {p['reason']}",
        ]
        if p["candidates"]:
            lines.append("    Candidates:")
            for c in p["candidates"]:
                lines.append(
                    f"      - ID {c.get('id')}: "
                    f"{c.get('first_name', '')} {c.get('last_name', '')} "
                    f"(DOB {c.get('date_of_birth', '')}, "
                    f"{c.get('email', '') or 'no email'}, "
                    f"{c.get('cell_phone', '') or c.get('home_phone', '') or 'no phone'})"
                )
        else:
            lines.append("    Candidates: (none returned)")
        sections.append("\n".join(lines))

    body_text = (
        f"Patient Intake Import: {len(pending)} submission(s) need a manual match\n"
        f"{'=' * 40}\n\n"
        + "\n\n".join(sections)
        + f"\n\nTo resolve each row, open the spreadsheet and fill the "
          f"'{config.MATCH_COLUMN}' column with one of:\n"
          f"  - a DrChrono patient ID (to link to that existing chart)\n"
          f"  - 'new' (to force-create a new patient)\n"
          f"  - 'skip' (to discard this submission)\n"
        + f"\nSpreadsheet: https://docs.google.com/spreadsheets/d/{config.SPREADSHEET_ID}/edit"
    )

    _send_email(
        config.NOTIFY_EMAILS,
        f"Intake Import: {len(pending)} submission(s) need manual match",
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
