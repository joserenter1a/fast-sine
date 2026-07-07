"""Paragraph styles for the rendered contract. Kept separate so the visual
design can change without touching render logic."""

from __future__ import annotations

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

BODY_FONT = "Times-Roman"
BOLD_FONT = "Times-Bold"


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    return {
        "Title": ParagraphStyle(
            "ContractTitle",
            parent=base,
            fontName=BOLD_FONT,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=24,
        ),
        "Body": ParagraphStyle(
            "ContractBody",
            parent=base,
            fontName=BODY_FONT,
            fontSize=10.5,
            leading=16,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
        ),
        "Signature": ParagraphStyle(
            "ContractSignature",
            parent=base,
            fontName=BODY_FONT,
            fontSize=10.5,
            leading=48,
            alignment=TA_LEFT,
            spaceBefore=10,
            spaceAfter=6,
        ),
    }
