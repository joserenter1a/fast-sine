# fast-sine

Turn a token-marked contract template into a signed PDF. The client reviews a
blank copy, fills their details, draws their initials and signature on a canvas,
and downloads a finished contract — the contractor's name and signature are
injected server-side as constants. Fully stateless: no database, no accounts,
no stored documents.

The contract currently served is Maya's Event Center's venue rental agreement
(`contract/template/mayas_event_center/mayas_contract.txt`), transcribed and
tokenized from the scanned originals in the same directory. The MEC
representative is the "contractor" whose signature is auto-applied.

## How it works

The template is marked up with unique tokens of the form `___(Name)___`.
`contract/fields.json` says how each token is filled. On `POST /generate`, the server validates that every required client
field is present, injects the contractor + date constants, and renders the whole
document in a single ReportLab pass.

**Key invariant:** the contractor's signature asset is injected *only* in the
final render, and *only* after the client's fields validate as complete. No
endpoint renders it on its own; the blank preview shows every signature as an
empty underline. A contractor signature can never land on a document the client
hasn't completed.

## Layout

| File                     | Role                                                                           |
| ------------------------ | ------------------------------------------------------------------------------ |
| `parser.py`            | Token registry; validates the template and`fields.json` agree 1:1            |
| `contract/fields.json` | Per-token config: type, size,`auto`/`source`                               |
| `styles.py`            | ReportLab paragraph styles (Times serif)                                       |
| `render.py`            | Single-pass renderer:`render_pdf()` (final) and `render_preview()` (blank) |
| `app.py`               | FastAPI app + static UI mount                                                  |
| `static/index.html`    | Dependency-free canvas signing UI                                              |

## Fields

Client-entered (required): booking/contact details (`ClientName`, `DepositDate`,
`EventName`, `EventDate`, `RoomDetails`, `PhoneNumber`, `Email`,
`ClientAddress`, `DepositAmount`, `PackageDetails`, `EventEndTime`),
`ClientSignature`, and five rules-acknowledgment initials
(`Initial_Capacity/Damages/Sound/Cleaning/EndTime`) drawn once and applied
everywhere. `Initial_NoAlcohol` is *optional* — the client initials it only if
their event will not serve alcohol; left blank it renders as an underline.

Auto (server constants): `MECSignature_Front/Final` (the representative's PNG,
`source` under `contract/assets/`) and the signing dates derived from today.

Two extra field kinds beyond the sample contract:

- **alias** — the template forbids duplicate tokens, but some values repeat
  (client name appears three times, the deposit amount twice). A field with
  `"alias": "ClientName"` renders that submitted value again without the client
  entering it twice.
- **multiline** — `PackageDetails` sets `"multiline": true`, which the UI
  renders as a textarea.

## Run locally

```bash
uv sync
uv run uvicorn app:app --reload
```

Open http://127.0.0.1:8000/ — review the blank contract in the embedded preview,
fill your name, draw your initials once and your signature, and submit to
download `contract.pdf`.

### Endpoints

| Method   | Path          | Purpose                                                  |
| -------- | ------------- | -------------------------------------------------------- |
| `GET`  | `/`         | Signing UI                                               |
| `GET`  | `/health`   | Liveness check                                           |
| `GET`  | `/fields`   | Client fields the UI must collect (from the registry)    |
| `GET`  | `/preview`  | Blank copy of the contract (inline PDF)                  |
| `POST` | `/generate` | Validate + render the signed PDF (`422` if incomplete) |

## Deploy to Vercel

The app is a single stateless ASGI function, which suits Vercel's Python runtime
well. Vercel auto-detects FastAPI from `pyproject.toml` and uses the `app` object
in `app.py` as the entrypoint — no extra shim needed.

The one thing that needs config: the renderer reads data files at runtime (the
template, `fields.json`, the contractor PNG, and `static/`). `vercel.json` forces
those non-Python files into the function bundle:

```json
{ "functions": { "app.py": { "includeFiles": "{contract,static}/**" } } }
```

Note `includeFiles` takes a **single** glob string — the brace expansion
`{contract,static}/**` covers both directories; a comma-separated value would be
read as one literal pattern and match neither.

Deploy:

```bash
vercel        # preview deployment
vercel --prod
```

**After deploying, hit `/preview` and `/generate` once.** If either returns a
`FileNotFoundError`, the data files weren't bundled — check the `includeFiles`
glob and that nothing in `.vercelignore` excludes `contract/` or `static/`.

Temp files during rendering go to `/tmp` (writable on Vercel). `uvicorn` is a
dependency only for local dev and is unused in the serverless deployment.

> An always-on ASGI host (Render, Railway, Fly.io) running `uvicorn app:app` is
> an equally valid target and needs no `vercel.json` — pick based on where you
> already deploy.

## Not built (deliberately)

Accounts, storage, audit trail, coordinate-based marker detection, styled `.docx`
fidelity, and multi-party asynchronous countersigning. The contractor step is a
constant, not a second human signing later — which is what keeps this stateless.
