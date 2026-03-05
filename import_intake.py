"""Import patient intake form responses from Google Sheets into DrChrono.

Reads unprocessed rows from the linked Google Form responses sheet,
matches or creates patients in DrChrono, and writes demographics,
medications, allergies, and medical problems.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

import config
import drchrono_client
import intake_pdf
import notify

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_sheets_client():
    """Authenticate and return a gspread client."""
    creds = None
    if os.path.exists(config.GOOGLE_SHEETS_TOKEN):
        creds = Credentials.from_authorized_user_file(
            config.GOOGLE_SHEETS_TOKEN, SCOPES
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_SHEETS_CREDENTIALS, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.GOOGLE_SHEETS_TOKEN, "w") as f:
            f.write(creds.to_json())

    return gspread.authorize(creds)


def get_unprocessed_rows(sheet):
    """Return rows that haven't been marked as processed.

    Returns list of (row_number, row_dict) tuples.
    """
    records = sheet.get_all_records()
    headers = sheet.row_values(1)

    # Add "Processed" column if it doesn't exist
    if config.PROCESSED_COLUMN not in headers:
        next_col = len(headers) + 1
        sheet.update_cell(1, next_col, config.PROCESSED_COLUMN)

    unprocessed = []
    for i, row in enumerate(records):
        if not row.get(config.PROCESSED_COLUMN):
            unprocessed.append((i + 2, row))  # +2: 1-indexed + header row

    return unprocessed


def mark_processed(sheet, row_number, status="Done"):
    """Mark a row as processed in the spreadsheet."""
    headers = sheet.row_values(1)
    col = headers.index(config.PROCESSED_COLUMN) + 1
    sheet.update_cell(row_number, col, f"{status} {datetime.now():%Y-%m-%d %H:%M}")


def parse_list_field(text):
    """Parse a paragraph field that contains a list (one item per line or comma-separated).

    Returns empty list for N/A or blank.
    """
    if not text or text.strip().upper() == "N/A":
        return []
    # Split on newlines first, then commas if single line
    items = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if len(items) == 1 and "," in items[0]:
        items = [i.strip() for i in items[0].split(",") if i.strip()]
    return items


def parse_pipe_entries(text):
    """Parse pipe-delimited entries written by the Apps Script form.

    Each line is like: Lisinopril | Dose: 10mg | Freq: daily
    or: Lisinopril | Dose: 10mg | Freq: daily | Reason stopped: side effects
    Returns list of dicts with the raw key-value pairs.
    """
    if not text or text.strip().upper() == "N/A":
        return []
    entries = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        entry = {"name": parts[0]}
        for part in parts[1:]:
            if ":" in part:
                key, val = part.split(":", 1)
                entry[key.strip().lower()] = val.strip()
            else:
                entry["name"] += " " + part
        entries.append(entry)
    return entries


def clean_phone(phone):
    """Strip non-digit characters and format as (XXX) XXX-XXXX for DrChrono."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def clean_zip(zip_code):
    """Validate as a 5 or 9 digit US zip code."""
    if not zip_code:
        return ""
    digits = re.sub(r"[^\d-]", "", str(zip_code)).strip()
    if re.match(r"^\d{5}(-\d{4})?$", digits):
        return digits
    # Try extracting just 5 digits
    match = re.search(r"\d{5}", str(zip_code))
    return match.group(0) if match else ""


def clean_email(email):
    """Basic email validation."""
    if not email:
        return ""
    email = str(email).strip()
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return email
    return ""


def map_gender(sex_at_birth, gender_identity):
    """Map form gender values to DrChrono gender codes."""
    sex = (sex_at_birth or "").lower()
    if "male" in sex and "female" not in sex:
        return "Male"
    elif "female" in sex:
        return "Female"
    else:
        return "Other"


def build_patient_data(row):
    """Extract patient demographics from a form row."""
    data = {
        "doctor": int(config.DRCHRONO_DOCTOR_ID),
        "first_name": row.get("Patient First Name", ""),
        "last_name": row.get("Patient Last Name", ""),
        "date_of_birth": format_date(row.get("Date of Birth", "")),
        "gender": map_gender(
            row.get("Sex at Birth", ""),
            row.get("Gender", ""),
        ),
        "email": clean_email(row.get("Patient Email", "")),
        "cell_phone": clean_phone(row.get("Patient Phone Number", "")),
        "address": row.get("Patient Street Address", ""),
        "city": row.get("Patient City", ""),
        "state": row.get("Patient State", ""),
        "zip_code": clean_zip(row.get("Patient Zip Code", "")),
        "preferred_language": "eng",
    }

    # Emergency contact
    ec_first = row.get("Emergency Contact First Name", "")
    ec_last = row.get("Emergency Contact Last Name", "")
    if ec_first or ec_last:
        data["emergency_contact_name"] = f"{ec_first} {ec_last}".strip()
        data["emergency_contact_phone"] = clean_phone(row.get("Emergency Contact Phone Number", ""))
        data["emergency_contact_relation"] = row.get("Relationship to Patient", "")

    # Preferred name as nickname
    preferred = row.get("Preferred Name", "")
    if preferred:
        data["nick_name"] = preferred

    # Clean empty strings
    return {k: v for k, v in data.items() if v}


def format_date(date_str):
    """Try to parse a date string into YYYY-MM-DD."""
    if not date_str:
        return ""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(date_str)


def process_row(row_number, row, dry_run=False):
    """Process a single intake form submission."""
    first_name = row.get("Patient First Name", "")
    last_name = row.get("Patient Last Name", "")
    dob = format_date(row.get("Date of Birth", ""))
    prefix = "[DRY RUN] " if dry_run else ""

    print(f"\n{'='*60}")
    print(f"{prefix}Processing: {first_name} {last_name} (DOB: {dob})")
    print(f"{'='*60}")

    if not last_name or not dob:
        print(f"  {prefix}SKIP: Missing last name or date of birth")
        return "Skipped - missing name/DOB"

    # 1. Patient demographics
    demo_data = build_patient_data(row)
    print(f"  {prefix}Patient demographics:")
    for k, v in demo_data.items():
        print(f"    {k}: {v}")

    if not dry_run:
        patient = drchrono_client.find_patient(last_name, dob, first_name)
        if patient:
            patient_id = patient["id"]
            print(f"  Found existing patient: ID {patient_id}")
        else:
            patient = drchrono_client.create_patient(demo_data)
            patient_id = patient["id"]
            print(f"  Created new patient: ID {patient_id}")

        patch_data = {k: v for k, v in demo_data.items() if k != "doctor"}
        drchrono_client.update_patient(patient_id, patch_data)
        print("  Updated demographics")

    # Fetch existing data for deduplication
    existing_med_names = set()
    existing_allergy_names = set()
    existing_problem_names = set()
    if not dry_run:
        for m in drchrono_client.get_existing_medications(patient_id):
            existing_med_names.add(m.get("name", "").lower().strip())
        for a in drchrono_client.get_existing_allergies(patient_id):
            existing_allergy_names.add(a.get("description", "").lower().strip())
        for p in drchrono_client.get_existing_problems(patient_id):
            existing_problem_names.add(p.get("name", "").lower().strip())
        print(f"  Existing: {len(existing_med_names)} meds, {len(existing_allergy_names)} allergies, {len(existing_problem_names)} problems")

    # 2. Current medications
    meds = parse_pipe_entries(row.get("Current Medications", ""))
    if meds:
        print(f"  {prefix}Current medications ({len(meds)}):")
    for med in meds:
        kwargs = {"status": "active"}
        if med.get("dose"):
            kwargs["dosage_quantity"] = med["dose"]
        if med.get("freq"):
            kwargs["frequency"] = med["freq"]
        if med.get("route"):
            kwargs["route"] = med["route"]
        if med.get("reason"):
            kwargs["indication"] = med["reason"]
        if med["name"].lower().strip() in existing_med_names:
            print(f"    {med['name']} (already exists, skipped)")
            continue
        print(f"    {med['name']} | {' | '.join(f'{k}={v}' for k, v in kwargs.items())}")
        if not dry_run:
            drchrono_client.add_medication(patient_id, med["name"], **kwargs)

    # 3. Allergies
    allergy_entries = parse_pipe_entries(row.get("Allergies", ""))
    if allergy_entries:
        print(f"  {prefix}Allergies ({len(allergy_entries)}):")
    for a in allergy_entries:
        kwargs = {}
        if a.get("reaction"):
            kwargs["reaction"] = a["reaction"]
        if a.get("severity"):
            kwargs["severity"] = a["severity"]
        if a["name"].lower().strip() in existing_allergy_names:
            print(f"    {a['name']} (already exists, skipped)")
            continue
        detail = f" | {' | '.join(f'{k}={v}' for k, v in kwargs.items())}" if kwargs else ""
        print(f"    {a['name']}{detail}")
        if not dry_run:
            drchrono_client.add_allergy(patient_id, a["name"], **kwargs)

    # 4. Medical conditions
    conditions = parse_list_field(row.get("Medical Conditions", ""))
    if conditions:
        print(f"  {prefix}Medical conditions ({len(conditions)}):")
        for c in conditions:
            if c.lower().strip() in existing_problem_names:
                print(f"    {c} (already exists, skipped)")
            else:
                print(f"    {c}")
    if not dry_run:
        for condition in conditions:
            if condition.lower().strip() not in existing_problem_names:
                drchrono_client.add_problem(patient_id, condition)

    psych_conditions = parse_list_field(row.get("Psychiatric Conditions", ""))
    if psych_conditions:
        print(f"  {prefix}Psychiatric conditions ({len(psych_conditions)}):")
        for c in psych_conditions:
            if c.lower().strip() in existing_problem_names:
                print(f"    {c} (already exists, skipped)")
            else:
                print(f"    {c}")
    if not dry_run:
        for condition in psych_conditions:
            if condition.lower().strip() not in existing_problem_names:
                drchrono_client.add_problem(patient_id, condition)

    # 5. Build intake document from all narrative/unmapped fields
    doc_sections = []

    # Additional patient info (no DrChrono field)
    unmapped_lines = []
    gender_id = row.get("Gender", "").strip()
    if gender_id:
        unmapped_lines.append(f"Gender Identity: {gender_id}")
    pronouns = row.get("Preferred Pronouns", "").strip()
    if pronouns:
        unmapped_lines.append(f"Pronouns: {pronouns}")
    former = row.get("Former Name", "").strip()
    if former:
        unmapped_lines.append(f"Former Name: {former}")
    completing_for = row.get("Completing For", "").strip()
    if completing_for and completing_for != "self":
        resp_first = row.get("Respondent First Name", "").strip()
        resp_last = row.get("Respondent Last Name", "").strip()
        if resp_first or resp_last:
            unmapped_lines.append(f"Form completed by: {resp_first} {resp_last}".strip())
        resp_email = row.get("Respondent Email", "").strip()
        if resp_email:
            unmapped_lines.append(f"Respondent Email: {resp_email}")
        resp_phone = row.get("Respondent Phone", "").strip()
        if resp_phone:
            unmapped_lines.append(f"Respondent Phone: {resp_phone}")
        resp_addr = row.get("Respondent Address", "").strip()
        if resp_addr:
            unmapped_lines.append(f"Respondent Address: {resp_addr}")
    if unmapped_lines:
        doc_sections.append(("Additional Patient Info", "\n".join(unmapped_lines)))

    # Healthcare practitioners
    practitioner_lines = []
    for field, label in [
        ("Therapists", "Therapist(s)"),
        ("Psychiatrists", "Psychiatrist(s)"),
        ("PCPs", "PCP(s)"),
        ("Other Practitioners", "Other Practitioners"),
    ]:
        val = row.get(field, "").strip()
        if val and val.upper() != "N/A":
            practitioner_lines.append(f"{label}: {val}")
    if practitioner_lines:
        doc_sections.append(("Healthcare Practitioners", "\n".join(practitioner_lines)))

    # Health history
    history_lines = []
    for field, label in [
        ("Surgeries", "Surgeries"),
        ("Hospitalizations", "Hospitalizations"),
        ("Additional Health Information", "Additional Health Info"),
    ]:
        val = row.get(field, "").strip()
        if val and val.upper() != "N/A":
            history_lines.append(f"{label}: {val}")
    if history_lines:
        doc_sections.append(("Health History", "\n".join(history_lines)))

    # Substance use
    substance_lines = []
    for substance in ["Alcohol", "Tobacco", "Cannabis", "Opiates",
                      "Cocaine or other Stimulants", "Hallucinogens",
                      "Benzodiazepines and other Sedatives", "Other Substances"]:
        val = row.get(substance, "").strip()
        if val and val.upper() != "N/A":
            substance_lines.append(f"{substance}: {val}")
    if substance_lines:
        doc_sections.append(("Substance Use History", "\n".join(substance_lines)))

    # Past psychiatric treatments
    psych_tx_lines = []
    for field, label in [
        ("Psychiatric Hospitalizations", "Psychiatric Hospitalizations"),
        ("Ketamine Treatments", "Ketamine Treatments"),
        ("Past Therapy", "Past Therapy"),
        ("Other Treatments", "Other Treatments"),
    ]:
        val = row.get(field, "").strip()
        if val and val.upper() != "N/A":
            psych_tx_lines.append(f"{label}: {val}")
    if psych_tx_lines:
        doc_sections.append(("Past Psychiatric Treatments", "\n".join(psych_tx_lines)))

    # Past medications
    past_med_entries = parse_pipe_entries(row.get("Past Medications", ""))
    if past_med_entries:
        past_med_lines = []
        print(f"  {prefix}Past medications ({len(past_med_entries)}):")
        for pm in past_med_entries:
            line = pm["name"]
            if pm.get("dose"):
                line += f" {pm['dose']}"
            if pm.get("freq"):
                line += f" ({pm['freq']})"
            if pm.get("reason stopped"):
                line += f" — stopped: {pm['reason stopped']}"
            past_med_lines.append(f"- {line}")
            if pm["name"].lower().strip() in existing_med_names:
                print(f"    {line} (already exists, skipped)")
            else:
                print(f"    {line}")
                if not dry_run:
                    kwargs = {"status": "inactive"}
                    if pm.get("dose"):
                        kwargs["dosage_quantity"] = pm["dose"]
                    if pm.get("freq"):
                        kwargs["frequency"] = pm["freq"]
                    if pm.get("reason stopped"):
                        kwargs["notes"] = f"Reason stopped: {pm['reason stopped']}"
                    drchrono_client.add_medication(patient_id, pm["name"], **kwargs)
        doc_sections.append(("Past Medications", "\n".join(past_med_lines)))

    # Non-medical
    nonmed_lines = []
    for field in ["Avocations", "Exercise", "Vocations", "Social",
                  "Education", "Spirituality", "Goals for Treatment"]:
        val = row.get(field, "").strip()
        if val:
            nonmed_lines.append(f"{field}: {val}")
    if nonmed_lines:
        doc_sections.append(("Non-Medical", "\n".join(nonmed_lines)))

    # Generate and upload PDF
    if doc_sections:
        patient_name = f"{first_name} {last_name}"
        print(f"  {prefix}Intake document ({len(doc_sections)} sections)")
        if dry_run:
            print(f"  --- Document preview ---")
            for title, content in doc_sections:
                print(f"  [{title}]")
                for line in content.split("\n"):
                    print(f"    {line}")
            print(f"  --- End document ---")
        else:
            pdf_path = intake_pdf.generate_intake_pdf(patient_name, doc_sections)
            drchrono_client.upload_document(
                patient_id,
                f"Patient Intake Form — {patient_name}",
                pdf_path,
            )
            os.unlink(pdf_path)
            print(f"  Uploaded intake document to patient chart")

    print(f"  {prefix}Done.")
    return "Done" if not dry_run else "Dry run OK"


def main():
    parser = argparse.ArgumentParser(description="Import patient intake forms into DrChrono")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and print all data without calling DrChrono or marking rows processed")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"Patient Intake Form Importer [{mode}]")
    print("=" * 40)

    if not config.SPREADSHEET_ID:
        print("ERROR: Set INTAKE_SPREADSHEET_ID in .env")
        sys.exit(1)

    # Connect to Google Sheets
    print("Connecting to Google Sheets...")
    gc = get_sheets_client()
    spreadsheet = gc.open_by_key(config.SPREADSHEET_ID)
    sheet = spreadsheet.worksheet(config.RESPONSES_SHEET)

    # Get unprocessed rows
    rows = get_unprocessed_rows(sheet)
    print(f"Found {len(rows)} unprocessed submission(s)")

    if not rows:
        print("Nothing to process.")
        return

    errors = []
    success_count = 0

    for row_number, row in rows:
        patient_name = f"{row.get('Patient First Name', '')} {row.get('Patient Last Name', '')}".strip()
        try:
            status = process_row(row_number, row, dry_run=args.dry_run)
            if not args.dry_run:
                mark_processed(sheet, row_number, status)
            success_count += 1
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" | {e.response.text}"
            print(f"  ERROR processing row {row_number}: {error_msg}")
            errors.append({
                "row_number": row_number,
                "patient_name": patient_name or f"Row {row_number}",
                "error": error_msg,
            })
            if not args.dry_run:
                mark_processed(sheet, row_number, f"Error: {e}")

    print(f"\nFinished processing {len(rows)} submission(s): {success_count} OK, {len(errors)} error(s).")

    # Send notifications (only in live mode)
    if not args.dry_run:
        if errors:
            try:
                notify.send_error_email(errors)
            except Exception as e:
                print(f"  WARNING: Failed to send error notification: {e}")
        elif success_count > 0:
            try:
                notify.send_success_email(success_count)
            except Exception as e:
                print(f"  WARNING: Failed to send success notification: {e}")


if __name__ == "__main__":
    main()
