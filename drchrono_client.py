"""DrChrono API client for patient intake — reuses token from gcal-drchrono-sync."""

import json
import os
import time
import requests

import config

TOKEN_STORE = config.DRCHRONO_TOKEN_FILE


def _load_token():
    if os.path.exists(TOKEN_STORE):
        with open(TOKEN_STORE) as f:
            return json.load(f)
    return None


def _save_token(token):
    with open(TOKEN_STORE, "w") as f:
        json.dump(token, f)


def _get_session():
    """Return a requests session with a valid DrChrono access token."""
    token = _load_token()
    if not token:
        raise RuntimeError(
            "No DrChrono token found. Run auth_drchrono.py in gcal-drchrono-sync first."
        )
    expires_at = token.get("expires_at", 0)
    if time.time() > expires_at - 60:
        token = _refresh_token(token)

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json",
    })
    return session


def _refresh_token(token):
    resp = requests.post(config.DRCHRONO_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "client_id": config.DRCHRONO_CLIENT_ID,
        "client_secret": config.DRCHRONO_CLIENT_SECRET,
    })
    resp.raise_for_status()
    new_token = resp.json()
    new_token["expires_at"] = time.time() + new_token.get("expires_in", 7200)
    if "refresh_token" not in new_token:
        new_token["refresh_token"] = token["refresh_token"]
    _save_token(new_token)
    print("  DrChrono token refreshed.")
    return new_token


def _request_with_retry(session, method, url, max_retries=3, **kwargs):
    for attempt in range(max_retries + 1):
        resp = getattr(session, method)(url, **kwargs)
        if resp.status_code != 429:
            return resp
        wait = int(resp.headers.get("Retry-After", 2 ** attempt))
        print(f"    Rate limited, waiting {wait}s...")
        time.sleep(wait)
    return resp


# ── Patient lookup / create ───────────────────────────────────────────

def find_patient(last_name, date_of_birth, first_name=None):
    """Search for a patient by last_name + date_of_birth.

    Returns the patient dict if found, None otherwise.
    """
    session = _get_session()
    params = {"last_name": last_name, "date_of_birth": date_of_birth}
    resp = _request_with_retry(session, "get",
                               f"{config.DRCHRONO_API_BASE}/patients",
                               params=params)
    resp.raise_for_status()
    results = resp.json().get("results", [])

    if first_name and results:
        for p in results:
            if p.get("first_name", "").lower() == first_name.lower():
                return p
        # Fall back to first result if no exact first name match
        return results[0] if results else None

    return results[0] if results else None


def create_patient(data):
    """Create a new patient. data must include doctor, first_name, last_name, gender."""
    session = _get_session()
    resp = _request_with_retry(session, "post",
                               f"{config.DRCHRONO_API_BASE}/patients",
                               json=data)
    resp.raise_for_status()
    return resp.json()


def update_patient(patient_id, data):
    """Update patient demographics."""
    session = _get_session()
    resp = _request_with_retry(session, "patch",
                               f"{config.DRCHRONO_API_BASE}/patients/{patient_id}",
                               json=data)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


# ── Medications ───────────────────────────────────────────────────────

def add_medication(patient_id, name, **kwargs):
    session = _get_session()
    payload = {
        "patient": patient_id,
        "doctor": int(config.DRCHRONO_DOCTOR_ID),
        "name": name,
        **kwargs,
    }
    resp = _request_with_retry(session, "post",
                               f"{config.DRCHRONO_API_BASE}/medications",
                               json=payload)
    resp.raise_for_status()
    return resp.json()


def list_medications(patient_id):
    session = _get_session()
    resp = _request_with_retry(session, "get",
                               f"{config.DRCHRONO_API_BASE}/medications",
                               params={"patient": patient_id})
    resp.raise_for_status()
    return resp.json().get("results", [])


# ── Deduplication helpers ──────────────────────────────────────────────

def _paginate(session, url, params=None):
    """Fetch all pages from a paginated DrChrono endpoint."""
    results = []
    if params is None:
        params = {}
    while url:
        resp = _request_with_retry(session, "get", url, params=params)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        url = data.get("next")
        params = {}  # next URL includes params already
    return results


def get_existing_medications(patient_id):
    session = _get_session()
    return _paginate(session, f"{config.DRCHRONO_API_BASE}/medications",
                     params={"patient": patient_id})


def get_existing_allergies(patient_id):
    session = _get_session()
    return _paginate(session, f"{config.DRCHRONO_API_BASE}/allergies",
                     params={"patient": patient_id})


def get_existing_problems(patient_id):
    session = _get_session()
    return _paginate(session, f"{config.DRCHRONO_API_BASE}/problems",
                     params={"patient": patient_id})


# ── Allergies ─────────────────────────────────────────────────────────

def add_allergy(patient_id, description, **kwargs):
    session = _get_session()
    payload = {
        "patient": patient_id,
        "doctor": int(config.DRCHRONO_DOCTOR_ID),
        "description": description,
        **kwargs,
    }
    resp = _request_with_retry(session, "post",
                               f"{config.DRCHRONO_API_BASE}/allergies",
                               json=payload)
    resp.raise_for_status()
    return resp.json()


# ── Problems / Conditions ────────────────────────────────────────────

def add_problem(patient_id, name, **kwargs):
    session = _get_session()
    payload = {
        "patient": patient_id,
        "doctor": int(config.DRCHRONO_DOCTOR_ID),
        "name": name,
        **kwargs,
    }
    resp = _request_with_retry(session, "post",
                               f"{config.DRCHRONO_API_BASE}/problems",
                               json=payload)
    resp.raise_for_status()
    return resp.json()


# ── Documents ─────────────────────────────────────────────────────────

def upload_document(patient_id, description, file_path, date=None):
    """Upload a document (PDF) to a patient's chart."""
    from datetime import date as date_type
    session = _get_session()
    # Documents endpoint uses multipart form, not JSON
    session.headers.pop("Content-Type", None)
    if date is None:
        date = date_type.today().isoformat()
    with open(file_path, "rb") as f:
        resp = _request_with_retry(
            session, "post",
            f"{config.DRCHRONO_API_BASE}/documents",
            data={
                "patient": patient_id,
                "doctor": int(config.DRCHRONO_DOCTOR_ID),
                "description": description,
                "date": date,
            },
            files={"document": (os.path.basename(file_path), f, "application/pdf")},
        )
    resp.raise_for_status()
    return resp.json() if resp.text else {}
