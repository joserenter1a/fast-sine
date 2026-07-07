"""FastAPI service for fast-sine.

Stateless: every request re-reads the template + registry, validates the
client's submission, injects the contractor/date constants, and streams back a
finished PDF. There is deliberately no endpoint that renders the contractor
signature on its own — see the invariant in render.py.

Run: uvicorn app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

import parser as tmpl
import render

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="fast-sine", description="Contract template -> signed PDF")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/fields")
def fields() -> dict:
    """The fields the client UI must collect, straight from the registry so the
    front end never hardcodes the token list."""
    _, spec = tmpl.parse()
    keep = ("type", "width", "height", "max_length")
    return {
        name: {k: f[k] for k in keep if k in f}
        for name, f in tmpl.client_fields(spec).items()
    }


@app.get("/preview")
def preview() -> Response:
    """A blank copy of the contract (underscore placeholders, no signatures) so
    the client can read what they're agreeing to before signing."""
    return Response(
        content=render.render_preview(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="contract-preview.pdf"'},
    )


@app.post("/generate")
def generate(submission: dict = Body(...)) -> Response:
    """Validate the client submission and return the finished contract PDF.
    Missing required fields or unreadable signature data -> 422, no PDF."""
    try:
        pdf = render.render_pdf(submission)
    except render.IncompleteSubmission as exc:
        raise HTTPException(
            status_code=422, detail={"error": "incomplete", "missing": exc.missing}
        )
    except (ValueError, TypeError, OSError) as exc:
        raise HTTPException(
            status_code=422, detail={"error": "invalid_input", "message": str(exc)}
        )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="contract.pdf"'},
    )


# Serve the canvas UI at "/". Mounted last so the API routes above win.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
