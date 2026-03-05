# Google Form Setup — Patient History Intake

Recreates the Jotform (251467238707059) as a Google Form.
Google Forms doesn't support conditional logic natively, so we use "Go to section based on answer" for branching.

## Create the Form

Go to https://forms.google.com and create a new form titled **"Patient History"**.

---

## Section 1: Basic Information

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 1 | Are you the patient or completing this form on behalf of the patient? | Multiple choice | Yes | Options: "I am the patient" / "I am completing this form on behalf of the patient". Use "Go to section" to route: "I am the patient" -> Section 3 (Patient Info), "on behalf" -> Section 2 (Respondent Info) |

---

## Section 2: Respondent Information
*(Only shown if completing on behalf of patient)*

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 2 | Respondent First Name | Short text | Yes | |
| 3 | Respondent Last Name | Short text | Yes | |
| 4 | Respondent Email | Short text | Yes | Email validation |
| 5 | Respondent Phone Number | Short text | Yes | |
| 6 | Respondent Address | Paragraph | Yes | Street, City, State, Zip |

After this section -> Go to Section 3

---

## Section 3: Patient Information

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 7 | Patient First Name | Short text | Yes | |
| 8 | Patient Last Name | Short text | Yes | |
| 9 | Preferred Name | Short text | No | "Leave blank if same as first name" |
| 10 | Former Name | Short text | No | "Leave blank if none" |
| 11 | Sex at Birth | Dropdown | Yes | Male, Female, Intersex |
| 12 | Gender | Dropdown | Yes | Male, Female, Transgender Male, Transgender Female, Non-binary, Other |
| 13 | Preferred Pronouns | Dropdown | Yes | He/Him, She/Her, They/Them, Other |
| 14 | Date of Birth | Date | Yes | |
| 15 | Patient Email | Short text | Yes | Email validation |
| 16 | Patient Phone Number | Short text | Yes | |
| 17 | Patient Street Address | Short text | Yes | |
| 18 | Patient City | Short text | Yes | |
| 19 | Patient State | Dropdown | Yes | All 50 states + DC |
| 20 | Patient Zip Code | Short text | Yes | |

---

## Section 4: Emergency Contact

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 21 | Emergency Contact First Name | Short text | Yes | |
| 22 | Emergency Contact Last Name | Short text | Yes | |
| 23 | Emergency Contact Email | Short text | Yes | |
| 24 | Emergency Contact Phone Number | Short text | Yes | |
| 25 | Relationship to Patient | Short text | Yes | |

---

## Section 5: Healthcare Practitioners

Description: *"Please list all current healthcare practitioners including name, practice, phone, and fax if known."*

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 26 | Do you have a current therapist? | Multiple choice | Yes | Yes / No |
| 27 | Therapist(s) — Name, Practice, Phone, Fax | Paragraph | No | "List each therapist on a new line" |
| 28 | Do you have a current psychiatrist? | Multiple choice | Yes | Yes / No |
| 29 | Psychiatrist(s) — Name, Practice, Phone, Fax | Paragraph | No | "List each on a new line" |
| 30 | Do you have a current PCP? | Multiple choice | Yes | Yes / No |
| 31 | PCP(s) — Name, Practice, Phone, Fax | Paragraph | No | |
| 32 | Do you see any other healthcare practitioners? | Multiple choice | Yes | Yes / No |
| 33 | Other practitioners — Name, Practice, Phone, Fax | Paragraph | No | "Specialists, coaches, alternative medicine, etc." |

---

## Section 6: Health History

Description: *"Please list all medical conditions, psychiatric conditions, surgeries, and hospitalizations. Write N/A if none."*

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 34 | Medical Conditions | Paragraph | Yes | "Include past serious illnesses, chronic conditions. Write N/A if none." |
| 35 | Psychiatric Conditions | Paragraph | Yes | "Include past and current diagnoses. Write N/A if none." |
| 36 | Surgeries | Paragraph | Yes | "List all surgeries with approximate dates. Write N/A if none." |
| 37 | Hospitalizations (medical, not psychiatric) | Paragraph | Yes | "Include dates, location, and reason. Write N/A if none." |
| 38 | Additional Health Information | Paragraph | No | "Anything else health-related you'd like us to know." |

---

## Section 7: Substance Use History

Description: *"Please give as much detail as possible regarding past substance use: age of first use, frequency, amount, last use, any treatment."*

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 39 | Alcohol | Paragraph | No | |
| 40 | Tobacco | Paragraph | No | |
| 41 | Cannabis | Paragraph | No | |
| 42 | Opiates | Paragraph | No | |
| 43 | Cocaine or other Stimulants | Paragraph | No | |
| 44 | Hallucinogens | Paragraph | No | |
| 45 | Benzodiazepines and other Sedatives | Paragraph | No | |
| 46 | Other Substances | Paragraph | No | |

---

## Section 8: Medications

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 47 | Current Medications | Paragraph | Yes | "List all current medications, OTC meds, and supplements. Include name, dose, and frequency. Write N/A if none." |
| 48 | Past Medications | Paragraph | Yes | "List all past psychiatric and relevant medications. Write N/A if none." |

---

## Section 9: Allergies

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 49 | Allergies | Paragraph | Yes | "Include environmental and medication allergies with reactions. Write N/A if none." |

---

## Section 10: Past Psychiatric Treatments

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 50 | Psychiatric Hospitalizations | Paragraph | Yes | "Include hospital, date, duration, reason for admission. Write N/A if none." |
| 51 | Ketamine Treatments | Paragraph | Yes | "Location, number of treatments, route (IV/IM/nasal/sublingual), your experience. Write N/A if none." |
| 52 | Past Therapy | Paragraph | Yes | "Modality, relationship with therapist, what was helpful/unhelpful. Write N/A if none." |
| 53 | Other Treatments | Paragraph | Yes | "ECT, TMS, Neurofeedback, other psychedelics, etc. Write N/A if none." |

---

## Section 11: Non-Medical

Description: *"These questions help us understand you as a whole person beyond your medical history."*

| # | Field | Type | Required | Notes |
|---|-------|------|----------|-------|
| 54 | Avocations | Paragraph | No | "Activities you do for joy and fulfillment" |
| 55 | Exercise | Paragraph | No | "Type and frequency of exercise" |
| 56 | Vocations | Paragraph | No | "Current and past professions, meaningful work" |
| 57 | Social | Paragraph | No | "Social network, important relationships" |
| 58 | Education | Paragraph | No | "Educational experience, highest level attained" |
| 59 | Spirituality | Paragraph | No | "Religious or spiritual beliefs and practices" |
| 60 | Goals for Treatment | Paragraph | No | "What does successful treatment look like for you?" |

---

## After Creating the Form

1. Go to **Responses** tab -> click the Google Sheets icon to create a linked spreadsheet
2. Copy the spreadsheet ID from the URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
3. Paste it into your `.env` as `INTAKE_SPREADSHEET_ID`
4. The sheet tab name defaults to "Form Responses 1" — update `INTAKE_RESPONSES_SHEET` in `.env` if different

## Google Forms Limitations vs Jotform

- **No configurable list widgets** — Jotform lets you add rows dynamically (e.g., multiple therapists). Google Forms doesn't. We use Paragraph fields with "list each on a new line" instructions instead.
- **No auto-calculated age** — We'll calculate age from DOB in the Python script.
- **Limited conditional logic** — Google Forms only supports "go to section based on answer", not showing/hiding individual fields. The respondent info section uses this.
- **No HIPAA BAA by default** — You need Google Workspace (paid) with a signed BAA to be HIPAA-compliant. Jotform had HIPAA built in.
