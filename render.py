"""Single-pass contract renderer.

Walks the template once, substituting each token with its rendered value —
text -> text, date -> today-derived string, signature -> inline <img> — and
builds a styled PDF with ReportLab Platypus. No coordinate detection, no
second pass.

Invariant: the contractor's constant signature/name are injected only here,
in the final render, and only after every required client field is present.
``render_pdf`` raises ``IncompleteSubmission`` otherwise, so a contractor
signature can never land on a document the client hasn't completed.
"""

from __future__ import annotations

import base64
import io
import re
import tempfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate

import parser as tmpl
from styles import build_styles

BLANK_LINE_RE = re.compile(r"\n\s*\n")
WRAP_RE = re.compile(r"[ \t]*\n[ \t]*")
EMPTY_TEXT_RULE = "_" * 12  # short underscore rule for blank text fields


class IncompleteSubmission(Exception):
    """Client omitted one or more required fields; no PDF is produced."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"missing required client fields: {missing}")


def missing_client_fields(submission: dict, fields: dict) -> list[str]:
    return [name for name in tmpl.client_fields(fields) if not submission.get(name)]


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_date(fmt: str, today: date) -> str:
    if fmt == "ordinal_day":
        return _ordinal(today.day)
    if fmt == "month_year":
        return today.strftime("%B, %Y")
    # "long"
    return f"{today.strftime('%B')} {today.day}, {today.year}"


def _decode_signature(value) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        if value.startswith("data:"):
            value = value.split(",", 1)[1]
        return base64.b64decode(value)
    raise TypeError(f"unsupported signature value: {type(value).__name__}")


def _img_tag(path: Path, spec: dict) -> str:
    return (
        f"<img src={quoteattr(str(path))} "
        f'width="{spec["width"]}" height="{spec["height"]}" valign="middle"/>'
    )


def _blank_rule(spec) -> str:
    """Underscore placeholder for a blank preview field, sized to the field."""
    if spec["type"] == "signature":
        return "_" * max(12, int(spec.get("width", 120) / 6))
    return EMPTY_TEXT_RULE


def _render_token(name, spec, submission, today, sigdir, base_dir, preview):
    ftype = spec["type"]
    if preview:
        # Blank template: every field renders as a placeholder. The contractor
        # signature asset is deliberately never injected here (see invariant).
        return _blank_rule(spec)
    if ftype == "text":
        val = (spec.get("value") if spec.get("auto") else submission.get(name)) or ""
        val = val.strip()
        return escape(val) if val else EMPTY_TEXT_RULE
    if ftype == "date":
        return escape(_format_date(spec.get("format", "long"), today))
    if ftype == "signature":
        if spec.get("auto"):
            path = (base_dir / spec["source"]).resolve()
        else:
            path = sigdir / f"{name}.png"
            path.write_bytes(_decode_signature(submission[name]))
        return _img_tag(path, spec)
    raise tmpl.TemplateError(f"{name!r}: unknown field type {ftype!r}")


def _build_markup(text, fields, submission, today, sigdir, base_dir, preview) -> str:
    parts: list[str] = []
    for literal, token in tmpl.segments(text):
        parts.append(escape(literal))
        if token is not None:
            parts.append(
                _render_token(
                    token, fields[token], submission, today, sigdir, base_dir, preview
                )
            )
    return "".join(parts)


def _build_pdf(markup: str) -> bytes:
    styles = build_styles()
    blocks = [b.strip() for b in BLANK_LINE_RE.split(markup) if b.strip()]
    flow = []
    for i, block in enumerate(blocks):
        block = WRAP_RE.sub(" ", block)
        # A short block carrying an image is a standalone signature line and
        # needs extra leading to fit the sig; a long paragraph that merely ends
        # with an inline initial stays normal body text.
        text_only = re.sub(r"<img[^>]*>", "", block).strip()
        if i == 0:
            style = styles["Title"]
        elif "<img" in block and len(text_only) < 60:
            style = styles["Signature"]
        else:
            style = styles["Body"]
        flow.append(Paragraph(block, style))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        title="Contract Agreement",
        topMargin=inch,
        bottomMargin=inch,
        leftMargin=inch,
        rightMargin=inch,
    )
    doc.build(flow)
    return buf.getvalue()


def _render(submission: dict, *, preview: bool, base_dir: Path) -> bytes:
    text, fields = tmpl.parse()
    if not preview:
        missing = missing_client_fields(submission, fields)
        if missing:
            raise IncompleteSubmission(missing)

    today = date.today()
    with tempfile.TemporaryDirectory() as tmpdir:
        markup = _build_markup(
            text, fields, submission, today, Path(tmpdir), base_dir, preview
        )
        return _build_pdf(markup)


def render_pdf(submission: dict, *, base_dir: Path = tmpl.BASE_DIR) -> bytes:
    """Validate the client submission, inject contractor + date constants,
    and return the finished PDF as bytes. Raises IncompleteSubmission if any
    required client field is missing."""
    return _render(submission, preview=False, base_dir=base_dir)


def render_preview(*, base_dir: Path = tmpl.BASE_DIR) -> bytes:
    """Render a blank copy of the contract — every field an underscore
    placeholder, no contractor signature — so the client can read the terms
    before signing."""
    return _render({}, preview=True, base_dir=base_dir)


if __name__ == "__main__":
    # Eyeball render: generate placeholder client signatures and write a PDF.
    from PIL import Image, ImageDraw, ImageFont

    def _placeholder(label: str, size=(360, 110)) -> bytes:
        img = Image.new("RGBA", size, (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        d.text(
            (10, 30),
            label,
            fill=(10, 30, 90, 255),
            font=ImageFont.load_default(size=40),
        )
        b = io.BytesIO()
        img.save(b, format="PNG")
        return b.getvalue()

    sample = {
        "ClientName": "Jane Q. Public",
        "Initial_1": _placeholder("JQP", (140, 90)),
        "Initial_2": _placeholder("JQP", (140, 90)),
        "Initial_3": _placeholder("JQP", (140, 90)),
        "ClientSignature": _placeholder("Jane Q. Public"),
    }
    out = Path(
        "/private/tmp/claude-502/-Users-joser-fast-sine/13012686-c61e-4332-8ec8-12b49ba1729c/scratchpad/sample_output.pdf"
    )
    out.write_bytes(render_pdf(sample))
    print(f"wrote {out} ({out.stat().st_size} bytes)")
