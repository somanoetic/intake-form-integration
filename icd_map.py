"""Map free-text patient conditions to ICD-10 codes via the Claude API.

Patients free-text their conditions on the intake form (e.g. "anxiety",
"high blood pressure"). DrChrono's structured Problem List requires an
ICD-10 code on each entry — a name-only POST stays free-text and never
becomes a coded problem. This module resolves each term to its best
ICD-10 code so import_intake can post coded problems.

Low-confidence terms are returned with mapped=False so the caller can
route them to manual review instead of posting a wrong code.
"""

import json
import os

import config

# Model used for code mapping. Cheap + accurate enough for single-term
# ICD-10 lookups; bump to a larger model if coverage proves insufficient.
ICD_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are a clinical coding assistant. You are given patient-reported "
    "conditions exactly as typed on an intake form. Patients use lay phrasing "
    "and frequently cram MULTIPLE distinct conditions into one line, separated "
    "by commas, slashes, 'and', or just spaces (e.g. 'Depression/Anxiety' is "
    "TWO conditions; 'babesia anxiety' is TWO; 'high blood pressure, diabetes' "
    "is TWO). Split every input into its individual conditions and map each one "
    "to its single best-matching ICD-10-CM code.\n\n"
    "Rules:\n"
    "- One output mapping per distinct condition you identify (so one input "
    "line may produce several mappings).\n"
    "- Use the most specific code you are confident in; otherwise prefer the "
    "'unspecified' variant over guessing a subtype.\n"
    "- Set confidence to 'low' and leave icd_code empty when an item is too "
    "vague, ambiguous, or not a codable medical condition (e.g. 'stress', "
    "'feeling tired', 'NA', 'No', 'none').\n"
    "- Do NOT emit mappings for filler/negative answers like 'N/A', 'NA', "
    "'No', 'none', 'n/a' — skip them entirely.\n"
    "- 'source' must be the original input line the condition came from, verbatim."
)

_TOOL = {
    "name": "report_icd_mappings",
    "description": "Report ICD-10-CM mappings for the patient conditions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "The original input line this condition came from, verbatim.",
                        },
                        "condition": {
                            "type": "string",
                            "description": "The single condition identified (after splitting).",
                        },
                        "icd_code": {
                            "type": "string",
                            "description": "ICD-10-CM code, e.g. 'I10'. Empty if confidence is low.",
                        },
                        "name": {
                            "type": "string",
                            "description": "Canonical ICD-10 description for the code.",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["source", "condition", "icd_code", "name", "confidence"],
                },
            }
        },
        "required": ["mappings"],
    },
}


def map_conditions(terms):
    """Map free-text condition lines to ICD-10 codes, splitting multi-condition lines.

    Claude splits inputs that contain several conditions and codes each one,
    so the result is NOT aligned 1:1 with `terms` — one input line can yield
    several mappings (or, for filler like "N/A", none).

    Returns a flat list of dicts, each:
        {
          "input": str,            # the condition text to use (Claude's split condition)
          "source": str,           # the original line it came from
          "mapped": bool,          # True if there's a code to post
          "icd_code": str,         # "" when not mapped
          "name": str,             # canonical name, falls back to the condition
          "confidence": str,       # high | medium | low
        }

    A condition is `mapped` only when confidence is high/medium AND a code
    came back; otherwise the caller routes it to manual review.
    """
    terms = [t.strip() for t in terms if t and t.strip()]
    if not terms:
        return []

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set — required for ICD-10 mapping. "
            "Add it to the .env / ENV_FILE secret."
        )

    # Imported lazily so the rest of the importer runs without anthropic
    # installed (e.g. dry runs that skip mapping).
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    user_msg = (
        "Split and map these patient-reported condition lines to ICD-10-CM "
        "codes. Remember a single line may contain multiple conditions:\n\n"
        + "\n".join(f"- {t}" for t in terms)
    )

    resp = client.messages.create(
        model=ICD_MODEL,
        max_tokens=2048,
        system=_SYSTEM,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "report_icd_mappings"},
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = []
    for block in resp.content:
        if block.type == "tool_use" and block.name == "report_icd_mappings":
            raw = block.input.get("mappings", [])
            break

    results = []
    for m in raw:
        condition = str(m.get("condition", "")).strip()
        if not condition:
            continue
        code = str(m.get("icd_code", "")).strip()
        conf = str(m.get("confidence", "low")).strip().lower()
        name = str(m.get("name", "")).strip() or condition
        mapped = bool(code) and conf in ("high", "medium")
        results.append({
            "input": condition,
            "source": str(m.get("source", "")).strip() or condition,
            "mapped": mapped,
            "icd_code": code,
            "name": name,
            "confidence": conf or "low",
        })

    return results
