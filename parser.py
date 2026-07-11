"""Token registry and template parser for fast-sine.

Everything downstream (render, routes, UI) depends on this: it is the single
source of truth for which tokens exist in the contract and how each one is
filled. Tokens look like ``___(Name)___`` and must be unique.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = (
    BASE_DIR / "contract" / "template" / "mayas_event_center" / "mayas_contract.txt"
)
FIELDS_PATH = BASE_DIR / "contract" / "fields.json"

TOKEN_RE = re.compile(r"___\(([^)]+)\)___")

VALID_TYPES = {"text", "signature", "date"}


class TemplateError(ValueError):
    """Raised when the template and the field registry disagree."""


def load_template(path: Path = TEMPLATE_PATH) -> str:
    return path.read_text(encoding="utf-8")


def load_fields(path: Path = FIELDS_PATH) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_tokens(text: str) -> list[str]:
    """Return token names in the order they appear in the template."""
    return TOKEN_RE.findall(text)


def segments(text: str) -> list[tuple[str, str | None]]:
    """Split the template into (literal_text, token_or_None) pairs.

    Reassembling ``"".join(lit for lit, _ in ...)`` with each token replaced by
    its rendered value reproduces the whole document in one pass.
    """
    out: list[tuple[str, str | None]] = []
    pos = 0
    for m in TOKEN_RE.finditer(text):
        out.append((text[pos : m.start()], m.group(1)))
        pos = m.end()
    out.append((text[pos:], None))
    return out


def validate(text: str, fields: dict[str, dict]) -> None:
    """Ensure the template's tokens and fields.json are a 1:1 match.

    Raises TemplateError on any mismatch, duplicate, or malformed field def.
    """
    tokens = find_tokens(text)

    dupes = {t for t in tokens if tokens.count(t) > 1}
    if dupes:
        raise TemplateError(f"duplicate tokens in template: {sorted(dupes)}")

    token_set = set(tokens)
    field_set = set(fields)
    missing_defs = token_set - field_set
    if missing_defs:
        raise TemplateError(f"tokens with no field definition: {sorted(missing_defs)}")
    unused_defs = field_set - token_set
    if unused_defs:
        raise TemplateError(f"field definitions with no token: {sorted(unused_defs)}")

    for name, spec in fields.items():
        ftype = spec.get("type")
        if ftype not in VALID_TYPES:
            raise TemplateError(
                f"{name!r}: type must be one of {sorted(VALID_TYPES)}, got {ftype!r}"
            )
        auto = spec.get("auto", False)
        if spec.get("required") and auto:
            raise TemplateError(
                f"{name!r}: a field cannot be both 'auto' and 'required'"
            )
        if ftype == "signature" and auto and not spec.get("source"):
            raise TemplateError(f"{name!r}: auto signature needs a 'source' asset path")
        alias = spec.get("alias")
        if alias:
            if auto or spec.get("required"):
                raise TemplateError(
                    f"{name!r}: an alias field cannot be 'auto' or 'required'"
                )
            target = fields.get(alias)
            if target is None:
                raise TemplateError(f"{name!r}: alias target {alias!r} is not defined")
            if target.get("type") != ftype:
                raise TemplateError(
                    f"{name!r}: alias target {alias!r} has type "
                    f"{target.get('type')!r}, expected {ftype!r}"
                )
            if target.get("alias"):
                raise TemplateError(
                    f"{name!r}: alias target {alias!r} is itself an alias"
                )


def client_fields(fields: dict[str, dict]) -> dict[str, dict]:
    """Fields the client must supply (required, non-auto)."""
    return {n: s for n, s in fields.items() if s.get("required") and not s.get("auto")}


def auto_fields(fields: dict[str, dict]) -> dict[str, dict]:
    """Fields filled server-side (constants + derived dates)."""
    return {n: s for n, s in fields.items() if s.get("auto")}


def ui_fields(fields: dict[str, dict]) -> dict[str, dict]:
    """Fields the client UI collects: everything client-enterable, required or
    optional. Auto constants and aliases (repeats of another field) stay out."""
    return {
        n: s for n, s in fields.items() if not s.get("auto") and not s.get("alias")
    }


def parse() -> tuple[str, dict[str, dict]]:
    """Load template + fields, validate, and return both. Raises on mismatch."""
    text = load_template()
    fields = load_fields()
    validate(text, fields)
    return text, fields


if __name__ == "__main__":
    text, fields = parse()
    tokens = find_tokens(text)
    print(f"OK: template and fields.json agree on {len(tokens)} unique tokens.\n")
    for name, spec in fields.items():
        if spec.get("auto"):
            role = "auto"
        elif spec.get("alias"):
            role = f"alias -> {spec['alias']}"
        else:
            role = "client*" if spec.get("required") else "optional"
        print(f"  {name:<20} {spec['type']:<10} [{role}]")
    print(f"\n  client-required: {list(client_fields(fields))}")
    print(f"  auto           : {list(auto_fields(fields))}")
