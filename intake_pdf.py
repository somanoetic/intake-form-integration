"""Generate a PDF document from intake form data."""

import os
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


PRIMARY = HexColor("#00656E")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        textColor=PRIMARY,
        fontSize=13,
        spaceAfter=6,
        spaceBefore=14,
    ))
    styles.add(ParagraphStyle(
        "FieldLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=HexColor("#718096"),
    ))
    styles.add(ParagraphStyle(
        "FieldValue",
        parent=styles["Normal"],
        fontSize=10,
        spaceBefore=1,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        textColor=PRIMARY,
        fontSize=18,
    ))
    return styles


def generate_intake_pdf(patient_name, note_sections, output_path=None):
    """Generate a PDF from structured intake note sections.

    note_sections: list of (section_title, content_text) tuples
    Returns the file path of the generated PDF.
    """
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".pdf", prefix="intake_")
        os.close(fd)

    styles = build_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []

    # Title
    story.append(Paragraph("Patient Intake Form", styles["DocTitle"]))
    story.append(Paragraph(
        f"<b>{patient_name}</b> &mdash; Generated {datetime.now():%B %d, %Y}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 16))

    # Sections
    for title, content in note_sections:
        story.append(Paragraph(title, styles["SectionHeader"]))
        # Handle multi-line content
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Escape HTML special chars
            line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Bold lines that start with a label (e.g., "  Alcohol: ...")
            if ":" in line and not line.startswith("-"):
                parts = line.split(":", 1)
                line = f"<b>{parts[0]}:</b>{parts[1]}"
            # Indent list items
            if line.startswith("-"):
                line = "&nbsp;&nbsp;&nbsp;" + line
            story.append(Paragraph(line, styles["FieldValue"]))
        story.append(Spacer(1, 4))

    doc.build(story)
    return output_path
