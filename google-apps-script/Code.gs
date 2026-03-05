/**
 * Patient History Intake Form — Google Apps Script backend.
 *
 * Deploy as a web app:
 *   1. Open this script in the Apps Script editor (bound to your spreadsheet)
 *   2. Deploy > New deployment > Web app
 *   3. Execute as: Me / Anyone with the link
 *   4. Copy the URL and share with patients
 */

const SHEET_NAME = "Form Responses 1";

function doGet() {
  return HtmlService.createHtmlOutputFromFile("form")
    .setTitle("Patient History")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag("viewport", "width=device-width, initial-scale=1");
}

function submitForm(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);

  // Create sheet with headers if it doesn't exist
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(getHeaders());
  }

  // Ensure headers exist on first row
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(getHeaders());
  }

  const row = buildRow(data);
  sheet.appendRow(row);

  return { success: true };
}

function getHeaders() {
  const headers = [
    "Timestamp",
    "Completing For",
    // Respondent
    "Respondent First Name", "Respondent Last Name",
    "Respondent Email", "Respondent Phone", "Respondent Address",
    // Patient
    "Patient First Name", "Patient Last Name",
    "Preferred Name", "Former Name",
    "Sex at Birth", "Gender", "Preferred Pronouns",
    "Date of Birth",
    "Patient Email", "Patient Phone Number",
    "Patient Street Address", "Patient City", "Patient State", "Patient Zip Code",
    // Emergency contact
    "Emergency Contact First Name", "Emergency Contact Last Name",
    "Emergency Contact Email", "Emergency Contact Phone Number",
    "Relationship to Patient",
    // Practitioners
    "Has Therapist", "Therapists",
    "Has Psychiatrist", "Psychiatrists",
    "Has PCP", "PCPs",
    "Has Other Practitioners", "Other Practitioners",
    // Health history
    "Medical Conditions",
    "Psychiatric Conditions",
    "Surgeries",
    "Hospitalizations",
    "Additional Health Information",
    // Substance use
    "Alcohol", "Tobacco", "Cannabis", "Opiates",
    "Cocaine or other Stimulants", "Hallucinogens",
    "Benzodiazepines and other Sedatives", "Other Substances",
    // Medications
    "Current Medications",
    "Past Medications",
    // Allergies
    "Allergies",
    // Past psychiatric treatments
    "Psychiatric Hospitalizations", "Ketamine Treatments",
    "Past Therapy", "Other Treatments",
    // Non-medical
    "Avocations", "Exercise", "Vocations", "Social",
    "Education", "Spirituality", "Goals for Treatment",
    // Processing
    "Processed",
  ];
  return headers;
}

function buildRow(d) {
  return [
    new Date().toISOString(),
    d.completingFor || "",
    // Respondent
    d.respondentFirstName || "", d.respondentLastName || "",
    d.respondentEmail || "", d.respondentPhone || "", d.respondentAddress || "",
    // Patient
    d.patientFirstName || "", d.patientLastName || "",
    d.preferredName || "", d.formerName || "",
    d.sexAtBirth || "", d.gender || "", d.pronouns || "",
    d.dateOfBirth || "",
    d.patientEmail || "", d.patientPhone || "",
    d.streetAddress || "", d.city || "", d.state || "", d.zipCode || "",
    // Emergency contact
    d.ecFirstName || "", d.ecLastName || "",
    d.ecEmail || "", d.ecPhone || "",
    d.ecRelationship || "",
    // Practitioners — stored as JSON strings
    d.hasTherapist || "No", formatListEntries(d.therapists),
    d.hasPsychiatrist || "No", formatListEntries(d.psychiatrists),
    d.hasPCP || "No", formatListEntries(d.pcps),
    d.hasOtherPractitioners || "No", formatListEntries(d.otherPractitioners),
    // Health history — stored as JSON strings
    formatSimpleList(d.medicalConditions),
    formatSimpleList(d.psychiatricConditions),
    formatDatedEntries(d.surgeries),
    formatDatedEntries(d.hospitalizations),
    d.additionalHealth || "",
    // Substance use
    d.alcohol || "", d.tobacco || "", d.cannabis || "", d.opiates || "",
    d.stimulants || "", d.hallucinogens || "",
    d.benzodiazepines || "", d.otherSubstances || "",
    // Medications — stored as JSON strings
    formatMedications(d.currentMedications),
    formatPastMedications(d.pastMedications),
    // Allergies
    formatAllergyEntries(d.allergies),
    // Past psychiatric treatments
    d.psychHospitalizations || "", d.ketamineTreatments || "",
    d.pastTherapy || "", d.otherTreatments || "",
    // Non-medical
    d.avocations || "", d.exercise || "", d.vocations || "",
    d.social || "", d.education || "", d.spirituality || "",
    d.goals || "",
    // Processing column (empty = unprocessed)
    "",
  ];
}

function formatListEntries(entries) {
  if (!entries || entries.length === 0) return "N/A";
  return entries
    .filter(function(e) { return e.name; })
    .map(function(e) {
      var parts = [e.name];
      if (e.practice) parts.push("Practice: " + e.practice);
      if (e.phone) parts.push("Phone: " + e.phone);
      if (e.fax) parts.push("Fax: " + e.fax);
      return parts.join(" | ");
    })
    .join("\n") || "N/A";
}

function formatSimpleList(entries) {
  if (!entries || entries.length === 0) return "N/A";
  return entries
    .filter(function(e) { return e; })
    .join("\n") || "N/A";
}

function formatDatedEntries(entries) {
  if (!entries || entries.length === 0) return "N/A";
  return entries
    .filter(function(e) { return e.name; })
    .map(function(e) {
      var parts = [e.name];
      if (e.date) parts.push("Date: " + e.date);
      if (e.reason) parts.push("Reason: " + e.reason);
      return parts.join(" | ");
    })
    .join("\n") || "N/A";
}

function formatMedications(entries) {
  if (!entries || entries.length === 0) return "N/A";
  return entries
    .filter(function(e) { return e.name; })
    .map(function(e) {
      var parts = [e.name];
      if (e.dose) parts.push("Dose: " + e.dose);
      if (e.frequency) parts.push("Freq: " + e.frequency);
      if (e.route) parts.push("Route: " + e.route);
      if (e.reason) parts.push("Reason: " + e.reason);
      return parts.join(" | ");
    })
    .join("\n") || "N/A";
}

function formatPastMedications(entries) {
  if (!entries || entries.length === 0) return "N/A";
  return entries
    .filter(function(e) { return e.name; })
    .map(function(e) {
      var parts = [e.name];
      if (e.dose) parts.push("Dose: " + e.dose);
      if (e.frequency) parts.push("Freq: " + e.frequency);
      if (e.reasonStopped) parts.push("Reason stopped: " + e.reasonStopped);
      return parts.join(" | ");
    })
    .join("\n") || "N/A";
}

function formatAllergyEntries(entries) {
  if (!entries || entries.length === 0) return "N/A";
  return entries
    .filter(function(e) { return e.description; })
    .map(function(e) {
      var parts = [e.description];
      if (e.reaction) parts.push("Reaction: " + e.reaction);
      if (e.severity) parts.push("Severity: " + e.severity);
      return parts.join(" | ");
    })
    .join("\n") || "N/A";
}
