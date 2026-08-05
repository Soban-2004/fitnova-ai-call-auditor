# FitNova — Sales-Call Intelligence System

An AI pipeline that ingests recorded sales calls, transcribes and diarizes them, runs a
3-pass LLM analysis (speaker roles, compliance/quality issues, dimension ratings),
computes a deterministic score, and surfaces all of it through director/team-leader/advisor
dashboards with a live contest-and-review workflow.

Originally a 48-hour take-home assignment; built instead at production-level care since
there was no time pressure — real tests, real error handling, real failure-path recovery,
not just a happy-path demo.

**Live:**
- Frontend: https://fitnova-ai-call-auditor.vercel.app
- Backend API: https://fitnova-backend-t1nz.onrender.com/api/health

## What's in it

- **Director / Team Leader / Advisor dashboards** — org-wide health, team coaching queues,
  an advisor's own scorecard. Score trend charts with a 4/8/12-week range selector.
- **All Calls page** — a filterable, paginated log (advisor, team, status, call type, issue
  tag, score range, date range), URL-driven so filtered views are shareable links.
- **Call detail page** — diarized transcript with an audio player synced to it (click a
  timestamp, it seeks), per-tag issue cards, dimension ratings, full score version history.
- **Contest / confirm / dismiss workflow** — an advisor can contest a flagged issue; a team
  leader confirms or dismisses it; a dismissal triggers a live score recalculation, versioned
  (scores are never overwritten, only ever appended).
- **Live updates** — an SSE stream pushes "a call finished processing" to every open
  dashboard tab, which re-fetches in place (no polling, no manual reload needed).
- **Upload page** — demo entry point standing in for a real telephony webhook; shows genuine
  live pipeline progress (not a fake progress bar — see [Design decisions](#design-decisions)).

## Architecture

```
Audio in (file upload today; a telephony webhook adapter later — same interface)
  -> ingestion (idempotency check: source_system + external_id)
  -> calls row, status=QUEUED
  -> background worker (asyncio task in the same process, DB-polling, not a broker)
       TRANSCRIBING  — Deepgram Nova-3, diarized, language="multi" (Hindi-English code-switching safe)
       ANALYZING     — 3 LLM passes (speaker ID -> issue detection -> dimension ratings),
                        each schema-validated; issues go through 3-layer validation
                        (Pydantic -> RapidFuzz -> Gemini embeddings) before being stored
       SCORING        — deterministic engine computes the score from ratings + validated
                         tags; the LLM never does arithmetic
       COMPLETED / FAILED — retry_count + a periodic sweep recover stuck/failed calls
  -> dashboards (plain SQL, server-rendered per request) + SSE nudges any open tab to refresh
```

LLM calls go through a provider fallback chain — Groq (primary) -> Gemini -> Ollama Cloud —
so one provider's outage doesn't fail a call outright.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (async), SQLAlchemy 2.0 (async), asyncpg, Alembic, Neon Postgres |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, Recharts |
| Transcription | Deepgram Nova-3 (STT + diarization) |
| LLM | Groq -> Gemini -> Ollama Cloud fallback chain (no LangChain/LiteLLM — a thin provider abstraction) |
| Tag validation | Pydantic schema + RapidFuzz fuzzy match + Gemini embeddings (semantic similarity) |
| Live updates | Server-Sent Events, in-process pub-sub (no Redis at this scale) |
| Backend host | Render |
| Frontend host | Vercel |

## Running it locally

```bash
# Backend
cd backend
python -m venv venv && source venv/Scripts/activate   # or venv/bin/activate on Mac/Linux
pip install -r requirements.txt
cp ../.env.example .env   # fill in DATABASE_URL + API keys, see below
alembic upgrade head      # or just start the app — it self-migrates on boot too
python ../scripts/seed_db.py
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
cp ../.env.example .env.local   # keep only the NEXT_PUBLIC_API_URL line
npm run dev
```

Visit `http://localhost:3000`. To see real (not backfilled) data flowing through the
pipeline, generate and process the 6 synthetic sample calls:
```bash
python scripts/generate_sample_calls.py     # edge-tts synthetic voices, ~2 min
python scripts/process_all_samples.py       # uploads + polls each through the real pipeline
python scripts/seed_score_history.py        # optional: backdates 6 weeks of history per call, for the trend charts
```

### Environment variables

See `.env.example` for the full list with defaults. The ones with no default that you must
supply: `DATABASE_URL` (Neon connection string), `DEEPGRAM_API_KEY`, `GROQ_API_KEY`,
`GEMINI_API_KEY` (also powers tag-validation embeddings, not just the LLM fallback),
`OLLAMA_API_KEY`, and `NEXT_PUBLIC_API_URL` for the frontend.

### Optional: local Postgres instead of Neon

`docker-compose.yml` spins up a local Postgres if you'd rather not use Neon while
developing — not required, the project defaults to Neon everywhere.

## Testing

```bash
cd backend
pytest -q
```

35 tests, all integration-style against the real dev DB (throwaway rows, cleaned up per
test) rather than mocks — deliberately, so a real `TranscriptionError` (file genuinely
missing) drives the failure path exactly as the background worker would hit it in
production. A couple of the tag-validation tests make a real call to Gemini's embedding
API (only the ones where fuzzy match is expected to fail — see below), so they need
`GEMINI_API_KEY` set and network access.

## Deployment

Backend on Render, frontend on Vercel, DB already on Neon. Both auto-deploy from this
repo's `main` branch.

**Backend (Render)**: `render.yaml` in the repo root is a Blueprint — "New +" -> "Blueprint"
in Render, connect the repo, it reads build command / start command / health check path
from that file. You still need to fill in the secrets it leaves blank (`sync: false`):
`DATABASE_URL`, `DEEPGRAM_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_API_KEY`,
`FRONTEND_URL`.

**Frontend (Vercel)**: import the repo, set **Root Directory** to `frontend`, set
`NEXT_PUBLIC_API_URL` to the Render backend's URL. Redeploy after changing it — Next.js
bakes `NEXT_PUBLIC_*` vars into the client bundle at build time, so just saving the env
var without a fresh deploy leaves the old value in the already-built JS.

**After both are up**: go back to Render and set `FRONTEND_URL` to the real Vercel URL,
then redeploy the backend. CORS checks this for an exact match (scheme, no trailing
slash) — until it's set correctly, the dashboard's server-rendered parts will work (that's
a server-to-server fetch, not subject to browser CORS) but the sidebar's team/advisor
lists will silently fail (client-side fetch, blocked by CORS, caught into a
`console.error` with no visible banner) — the specific symptom that flagged this exact
misconfiguration during this project's own deploy.

Three real gotchas hit during this project's actual deploy, left here since they're not
obvious from the code:
1. **Render defaults to a very new Python** (3.14 at time of writing) with no prebuilt
   wheel yet for `rapidfuzz`, and its source-build fallback fails on a `pyproject.toml`
   strictness bug unrelated to this project. Fixed by pinning `PYTHON_VERSION=3.10.13` in
   `render.yaml` — matching what's actually been tested, not just "anything newer."
2. **Monorepo root directory**: since `git init` was run inside `fitnova/` itself, that
   directory *is* the repo root — `render.yaml`'s `rootDir` and Vercel's Root Directory
   setting are both just `backend` / `frontend`, not `fitnova/backend` / `fitnova/frontend`.
3. **Migrations self-run on boot** (`alembic upgrade head`, as a subprocess, before the
   worker starts — see `main.py`'s lifespan) specifically so there's no separate manual
   migration step to forget on a host like Render's free tier that doesn't offer a
   reliable pre-deploy hook.

## Design decisions

**Adapter pattern for call ingestion.** `BaseSourceAdapter.normalize()` maps any vendor's
payload (telephony webhook, CRM export, manual upload) onto one internal `CallEvent`
shape. Only `FileUploadAdapter` exists today; a real telephony integration is a new file,
zero changes anywhere downstream.

**Idempotency, not just insert.** `UNIQUE(source_system, external_id)` plus explicit status
handling: `COMPLETED` -> reject (already processed), in-flight -> reject (already being
worked on), `FAILED` -> allow retry (resets `retry_count`, accepts a corrected `audio_ref`).
Stops a webhook firing twice from double-processing a call.

**3-pass LLM analysis, each pass narrow and validated.** Speaker role ID, issue detection,
dimension ratings run as separate calls (not one call trying to think about everything at
once) at `temperature=0`, each schema-validated before the next step touches the output.

**3-layer tag validation** — an issue tag is never trusted just because the LLM said so:
1. Pydantic schema (right shape, known tag/severity, non-empty quote, in-bounds timestamp)
2. RapidFuzz (does the quoted text roughly appear in the transcript near that timestamp?)
3. Gemini embeddings, semantic similarity — catches genuine paraphrases fuzzy match misses
   (e.g. "offer expires tomorrow" vs "offer ends tomorrow"), only called when Layer 2
   already failed (a fuzzy pass already validates the tag — skip the network round-trip).
   Originally a local `sentence-transformers` model; swapped to Gemini's hosted embedding
   API for the deploy (`torch` alone is ~1-2GB installed and 300-500MB+ resident once
   loaded — real risk of not fitting a free-tier host, and this reuses the Gemini key/SDK
   already in the project rather than adding a new dependency). `SEMANTIC_THRESHOLD` was
   recalibrated empirically for the new embedding space (0.75, tuned for the old model,
   would have wrongly passed unrelated text under the new one — see
   `services/validation.py`'s module docstring for the actual measured scores).

A tag passes if it clears Layer 1 **and** at least one of (Layer 2, Layer 3).
Schema-pass-only -> `needs_review` (kept, surfaced for a human — never silently dropped).

**Deterministic scoring — the LLM never does arithmetic.** Dimension ratings feed a
weighted base score; validated issue tags apply severity-based deductions,
deduplicated by tag type (a real bug: duplicate tag instances were stacking deductions
before this).

**Scores and prompts are versioned, never overwritten.** A dismiss/confirm decision that
changes the deduction inserts a new `call_scores` row (never updates the old one) plus a
`score_audit_log` entry recording who/why. Prompt text is versioned in the DB with an
`is_active` flag — a rubric change is a new version, not a silent edit of one already
referenced by real scored calls.

**State machine in a DB column, not a broker.** `QUEUED -> TRANSCRIBING -> ANALYZING ->
COMPLETED/FAILED` lives in `calls.status`; a background `asyncio` task polls for `QUEUED`
rows every few seconds. No Celery/Redis — for a single-process worker, a distributed
queue would add infrastructure without demonstrable benefit at this scale; swapping the
executor later doesn't change the schema. A periodic sweep recovers calls stuck past a
timeout and requeues failed ones under a retry cap.

**Live progress is in-memory, not a DB write — deliberately.** The Upload page's
step-by-step progress used to write `calls.current_step` in its own committed transaction,
on the theory that a separate connection can't see this session's uncommitted flushes.
True, but that UPDATE targets the exact row the worker holds under
`SELECT ... FOR UPDATE` for the pipeline's entire duration — Postgres blocks a conflicting
write from another connection until that lock releases, so the "independent commit" would
just hang until the pipeline finished anyway (confirmed by directly reproducing the block
during this project's own build). Progress reporting doesn't need to survive a process
restart — it only needs to be visible within one running process — so it's a plain
in-memory map instead, same pattern as the SSE broadcaster right next to it.

**SSE over polling or WebSockets for live dashboard updates.** Data only ever flows
server -> client here (a call finished, please refresh) — nothing the client needs to send
back — so a one-directional stream fits better than a full-duplex WebSocket, and pushing on
an actual state change beats polling on a timer. No Redis: the worker and the API share one
process, so an in-process `asyncio.Queue` per subscriber is enough at this scale; it would
need a real broker the moment there's more than one backend instance.

## What's real vs. what's simplified

Being direct about this rather than letting it blend in:

- **Advisor identity is metadata, not a voiceprint.** "Priya Sharma made this call" comes
  from `Call.advisor_id`, asserted at ingestion (the way a real CRM/dialer would tell you
  which advisor's queue placed the call) — never inferred from the audio. What genuinely
  *is* inferred per call is which anonymous diarized `Speaker 0/1` is playing the advisor
  role, via the speaker-ID LLM pass. Nothing cross-checks that the voice on the recording
  actually matches the named advisor — a real gap if upstream metadata were ever wrong.
- **Audio storage is local disk**, ephemeral on Render. `backend/sample_calls/*.wav` (the
  6-call demo dataset) is committed to the repo, so it survives every redeploy. A call
  uploaded live through the demo Upload page has its transcript and score survive fine
  (that's in Postgres) but its raw audio file is wiped on the next restart — the player
  would 404 for that one call. The real fix (S3 + presigned URLs + Deepgram's
  transcribe-by-URL mode) was scoped out for this submission; see "What's next."
  Uploading anything other than the 6 committed sample calls means it goes through the
  full pipeline for real — Deepgram + 3 real LLM calls — burns real API quota, worth
  knowing before a reviewer clicks around.
- **Single-process assumptions**: the SSE broadcaster and the in-memory progress map both
  only work within one running backend process. Fine at this scale (Render's free/starter
  tier runs one instance); would need Redis pub-sub the moment there's more than one.
- **No real telephony adapter.** The Upload page is a deliberate stand-in for what a
  webhook from a telephony vendor would do automatically.
- **Score history before this week is synthetic.** `seed_score_history.py` backdates 6
  weeks of jittered scores per real scored call purely so the trend charts have more than
  one data point to draw a line through — clearly separated by `source_system="seed_backfill"`
  (never `"file_upload"`), reset to a clean `open` tag state (no fake contest history). It's
  random noise around each call's real score, not an invented trend.

## What's next

- **S3 (or equivalent) audio storage** — the one item that actually blocks calling audio
  storage "production-ready" rather than "demo-ready." Adapter uploads to a bucket,
  Deepgram transcribes by URL (its own hosted-audio mode, no download-then-upload round
  trip), the audio endpoint redirects to a presigned URL instead of proxying bytes.
- **Neon's pooled (`-pooler`) connection endpoint** — the direct endpoint was used
  throughout; a workload with many short-lived connections (exactly this app's shape) is
  what Neon's pgbouncer pooling is meant for, and would reduce a real class of connection
  flakiness observed during heavy concurrent testing this session.
- **Voiceprint verification** — cross-check that the recorded voice actually matches the
  advisor named in ingestion metadata, closing the identity gap noted above.
- **Redis-backed SSE broadcast + progress store** — needed the moment the backend runs as
  more than one instance; today's in-memory versions are explicitly single-process.
- **Granular retry/backoff per failure type** — right now any exception in the pipeline
  gets the same flat retry treatment; a rate-limited LLM call and a genuinely malformed
  audio file probably deserve different handling.

## Project structure

```
fitnova/
  backend/
    app/
      adapters/       # source-agnostic ingestion (file_upload.py today)
      llm/            # provider abstraction (Groq/Gemini/Ollama), fallback chain
      models/         # SQLAlchemy ORM
      routers/        # FastAPI endpoints
      schemas/        # Pydantic request/response + LLM output shapes
      services/       # ingestion, transcription, analysis, validation, scoring, processor (worker), events (SSE + progress)
    alembic/versions/  # schema migrations
    sample_calls/      # the 6 committed demo audio files + manifest.json
    tests/
  frontend/
    src/
      app/            # Next.js App Router pages (dashboards, call detail, calls log, upload)
      components/     # dashboard/, call/, calls/, layout/, ui/
      lib/            # api client, types, formatting helpers
  scripts/            # generate_sample_calls.py, process_all_samples.py, seed_db.py, seed_score_history.py, upgrade_prompt.py
  render.yaml         # Render Blueprint (backend)
  docker-compose.yml  # optional local Postgres, not required (defaults to Neon)
```
