"""DrChrono API client for patient intake — reuses token from gcal-drchrono-sync."""

import base64
import json
import os
import re
import time
import requests
from nacl import encoding, public

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
    _sync_token_to_secret(new_token)
    print("  DrChrono token refreshed.")
    return new_token


def _sync_token_to_secret(token):
    """Update the DRCHRONO_TOKEN GitHub secret so the fallback stays current."""
    gh_token = os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not gh_token or not repo:
        return
    try:
        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # Get the repo public key for secret encryption
        key_resp = requests.get(
            f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
            headers=headers,
        )
        key_resp.raise_for_status()
        key_data = key_resp.json()

        # Encrypt the token value
        public_key = public.PublicKey(
            key_data["key"].encode("utf-8"), encoding.Base64Encoder
        )
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(json.dumps(token).encode("utf-8"))
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

        # Update the secret
        requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/DRCHRONO_TOKEN",
            headers=headers,
            json={
                "encrypted_value": encrypted_b64,
                "key_id": key_data["key_id"],
            },
        ).raise_for_status()
        print("  GitHub secret DRCHRONO_TOKEN updated.")
    except Exception as e:
        print(f"  Warning: could not update GitHub secret: {e}")


def _request_with_retry(session, method, url, max_retries=3, **kwargs):
    for attempt in range(max_retries + 1):
        resp = getattr(session, method)(url, **kwargs)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"    Rate limited, waiting {wait}s...")
            time.sleep(wait)
        elif resp.status_code >= 500 and attempt < max_retries:
            wait = 2 ** attempt
            print(f"    Server error ({resp.status_code}), retrying in {wait}s...")
            time.sleep(wait)
        else:
            return resp
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


def normalize_lastname(name):
    """Lowercase + strip whitespace, hyphens, apostrophes, periods.

    Used for conservative fuzzy matching: "Smith-Jones", "Smith Jones",
    "SmithJones", "smith jones" all normalize to "smithjones".
    """
    return re.sub(r"[\s\-'’.]", "", name or "").lower()


def _search_patients(last_name, date_of_birth=None):
    session = _get_session()
    # DrChrono's /patients search excludes Inactive and Inactive-Deceased
    # patients by default. Passing patient_status disables that filter so
    # we can still match (and route to manual review) against records
    # staff have inactivated.
    params = {"last_name": last_name, "patient_status": "A,I,D"}
    if date_of_birth:
        params["date_of_birth"] = date_of_birth
    resp = _request_with_retry(session, "get",
                               f"{config.DRCHRONO_API_BASE}/patients",
                               params=params)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _digits_only(s):
    return re.sub(r"\D", "", s or "")


def _search_patients_by_email(email):
    """DrChrono /patients supports `email` as a case-insensitive exact filter."""
    session = _get_session()
    params = {"email": email, "patient_status": "A,I,D"}
    resp = _request_with_retry(session, "get",
                               f"{config.DRCHRONO_API_BASE}/patients",
                               params=params)
    resp.raise_for_status()
    return resp.json().get("results", [])


def find_patient_candidates(last_name, date_of_birth, first_name=None,
                            email=None, cell_phone=None):
    """Decide whether to auto-match, auto-create, or queue for review.

    Returns a dict with:
      - decision: "match" | "create" | "review"
      - patient: the matched patient dict (when decision == "match")
      - reason: human-readable reason (when decision == "review")
      - candidates: list of candidate patient dicts (when decision == "review")
    """
    results = _search_patients(last_name, date_of_birth)

    # Active patients auto-match. Inactive/Deceased route to review so
    # staff confirm before reviving an intentionally-inactivated record.
    def _matchable(p):
        return (p.get("patient_status") or "A") == "A"

    if len(results) == 1:
        p = results[0]
        first_ok = not first_name or p.get("first_name", "").lower() == first_name.lower()
        if first_ok and _matchable(p):
            return {"decision": "match", "patient": p}
        if first_ok and not _matchable(p):
            return {
                "decision": "review",
                "reason": (
                    f"Only match is a non-active patient "
                    f"(chart {p.get('chart_id')}, status {p.get('patient_status')}). "
                    "Reactivate and use this record, or force 'new'."
                ),
                "candidates": results,
            }
        return {
            "decision": "review",
            "reason": (
                f"Last name + DOB matched one patient, but first name "
                f"differs (form: '{first_name}', DrChrono: '{p.get('first_name', '')}')."
            ),
            "candidates": results,
        }

    if len(results) > 1:
        matchable = [p for p in results if _matchable(p)]
        if first_name:
            exact = [p for p in matchable
                     if p.get("first_name", "").lower() == first_name.lower()]
            if len(exact) == 1:
                return {"decision": "match", "patient": exact[0]}
        return {
            "decision": "review",
            "reason": (
                f"Last name + DOB matched {len(results)} patients "
                f"({len(matchable)} active/prospective, "
                f"{len(results) - len(matchable)} inactive/deceased)."
            ),
            "candidates": results,
        }

    # Zero exact hits — try conservative last-name variants.
    target = normalize_lastname(last_name)
    tried = {last_name.lower()}
    variants = [
        last_name.replace("-", " "),
        last_name.replace("-", ""),
        last_name.replace("'", "").replace("’", ""),
        last_name.replace(" ", ""),
    ]
    fuzzy_hits = []
    for v in variants:
        if not v or v.lower() in tried:
            continue
        tried.add(v.lower())
        for p in _search_patients(v, date_of_birth):
            if normalize_lastname(p.get("last_name", "")) == target:
                if not any(c.get("id") == p.get("id") for c in fuzzy_hits):
                    fuzzy_hits.append(p)

    if fuzzy_hits:
        return {
            "decision": "review",
            "reason": (
                f"No exact last-name match, but {len(fuzzy_hits)} patient(s) "
                f"share DOB with a similar last name (hyphen/space/apostrophe variant)."
            ),
            "candidates": fuzzy_hits,
        }

    # Last resort: search by last_name alone, and separately by email.
    # This catches phone-booked patients whose DOB wasn't entered yet
    # (which would otherwise silently create a duplicate — the Lisa
    # Valentine 2026-04-22 bug), as well as name changes (maiden/married)
    # where email or phone still line up.
    suspects = []
    seen_ids = set()

    def _add(p):
        if p.get("id") and p.get("id") not in seen_ids:
            seen_ids.add(p["id"])
            suspects.append(p)

    # Flag any last-name match with a blank DOB, matching first name,
    # matching email, or matching phone number.
    email_norm = (email or "").strip().lower()
    phone_digits = _digits_only(cell_phone)
    for p in _search_patients(last_name):
        p_dob = (p.get("date_of_birth") or "").strip()
        p_first = (p.get("first_name") or "").lower()
        p_email = (p.get("email") or "").strip().lower()
        p_phone = _digits_only(p.get("cell_phone") or "")
        if not p_dob:
            _add(p)
        elif first_name and p_first == first_name.lower():
            _add(p)
        elif email_norm and p_email == email_norm:
            _add(p)
        elif phone_digits and p_phone and p_phone == phone_digits:
            _add(p)

    # Also look up by email directly (catches last-name changes).
    if email_norm:
        for p in _search_patients_by_email(email_norm):
            _add(p)

    if suspects:
        return {
            "decision": "review",
            "reason": (
                f"No DOB match, but {len(suspects)} patient(s) share "
                "last name, email, or phone with the submission. "
                "Likely a phone-booked account or a name change."
            ),
            "candidates": suspects,
        }

    return {"decision": "create"}


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

def add_problem(patient_id, name, icd_code=None, **kwargs):
    """Add a problem to the patient's chart.

    DrChrono's structured Problem List requires an ICD-10 code AND its
    code-set version: `icd_code` must be accompanied by `icd_version=10`,
    otherwise DrChrono can't resolve the code and the entry stays free-text
    instead of becoming a coded diagnosis. Defaults status to "active" so it
    lands as an active problem.
    """
    session = _get_session()
    payload = {
        "patient": patient_id,
        "doctor": int(config.DRCHRONO_DOCTOR_ID),
        "name": name,
        "status": kwargs.pop("status", "active"),
        **kwargs,
    }
    if icd_code:
        payload["icd_code"] = icd_code
        payload.setdefault("icd_version", 10)
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
