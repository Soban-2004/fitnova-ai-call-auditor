"""
Upload every sample call in backend/sample_calls/ (per manifest.json) to a
running FitNova backend, then poll until each reaches a terminal state
(COMPLETED or FAILED). Prints a summary comparing actual results against the
expected tags/score range recorded in the manifest.

Requires the backend to be running (see backend/app/main.py — the background
worker starts automatically in its lifespan). Polls the DB directly rather
than a /status endpoint since that endpoint is a later phase; upload itself
goes through the real HTTP API.

Run from fitnova/backend/: python ../scripts/process_all_samples.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.database import async_session_factory, dispose_engine  # noqa: E402
from app.models.analysis import DimensionRating, IssueTag  # noqa: E402
from app.models.call import Call  # noqa: E402
from app.models.score import CallScore  # noqa: E402

SAMPLE_DIR = BACKEND_DIR / "sample_calls"
API_URL = "http://127.0.0.1:8000"
POLL_INTERVAL_SECS = 5
TIMEOUT_SECS = 300
TERMINAL_STATES = {"COMPLETED", "FAILED"}


async def upload_all(manifest: list[dict]) -> dict[str, str]:
    """Returns {external_id: call_id}."""
    external_id_to_call_id = {}
    async with httpx.AsyncClient(timeout=60.0) as client:
        for entry in manifest:
            external_id = Path(entry["file"]).stem
            audio_path = SAMPLE_DIR / entry["file"]
            with open(audio_path, "rb") as f:
                resp = await client.post(
                    f"{API_URL}/api/upload",
                    files={"audio_file": (entry["file"], f, "audio/wav")},
                    data={"advisor_id": entry["advisor_id"], "external_id": external_id},
                )
            if resp.status_code == 201:
                call_id = resp.json()["call_id"]
                external_id_to_call_id[external_id] = call_id
                print(f"  uploaded {entry['file']} -> call_id={call_id}")
            elif resp.status_code == 409:
                print(f"  {entry['file']}: already processed/in-progress ({resp.json()['detail']}) — skipping")
            else:
                print(f"  {entry['file']}: upload failed [{resp.status_code}] {resp.text}")
    return external_id_to_call_id


async def poll_until_done(call_ids: list[str]) -> None:
    deadline = time.time() + TIMEOUT_SECS
    pending = set(call_ids)
    while pending and time.time() < deadline:
        async with async_session_factory() as session:
            rows = (await session.execute(select(Call).where(Call.id.in_(pending)))).scalars().all()
            for call in rows:
                if call.status in TERMINAL_STATES:
                    pending.discard(str(call.id))
        if pending:
            print(f"  waiting on {len(pending)} call(s)...")
            await asyncio.sleep(POLL_INTERVAL_SECS)
    if pending:
        print(f"  TIMEOUT: {len(pending)} call(s) did not finish within {TIMEOUT_SECS}s")


async def print_summary(manifest: list[dict], external_id_to_call_id: dict[str, str]) -> None:
    print("\n" + "=" * 100)
    print(f"{'file':<28} {'status':<10} {'call_type':<10} {'score':<7} {'tags (open)':<40}")
    print("-" * 100)
    async with async_session_factory() as session:
        for entry in manifest:
            external_id = Path(entry["file"]).stem
            call_id = external_id_to_call_id.get(external_id)
            if call_id is None:
                print(f"{entry['file']:<28} (not uploaded this run)")
                continue

            call = await session.get(Call, call_id)
            tags = (
                await session.execute(select(IssueTag).where(IssueTag.call_id == call_id))
            ).scalars().all()
            open_tags = [t.tag_type for t in tags if t.status == "open"]
            needs_review = [t.tag_type for t in tags if t.status == "needs_review"]
            score_row = (
                await session.execute(
                    select(CallScore).where(CallScore.call_id == call_id).order_by(CallScore.version.desc())
                )
            ).scalars().first()
            score = score_row.final_score if score_row else "-"

            tag_summary = ", ".join(open_tags) if open_tags else "(none)"
            if needs_review:
                tag_summary += f" [needs_review: {', '.join(needs_review)}]"

            print(f"{entry['file']:<28} {call.status:<10} {str(call.call_type):<10} {str(score):<7} {tag_summary:<40}")

            expected = entry["expected_tags"]
            expected_range = entry["expected_score_range"]
            match_note = []
            if expected:
                missing = [t for t in expected if t not in open_tags]
                if missing:
                    match_note.append(f"MISSING expected tags: {missing}")
            if expected_range and isinstance(score, int):
                lo, hi = expected_range
                if not (lo <= score <= hi):
                    match_note.append(f"score {score} outside expected [{lo}, {hi}]")
            if match_note:
                print(f"    ! {' | '.join(match_note)}")

            dims = (
                await session.execute(select(DimensionRating).where(DimensionRating.call_id == call_id))
            ).scalars().all()
            if dims:
                dim_str = ", ".join(f"{d.dimension}={d.score}" for d in dims)
                print(f"    dimensions: {dim_str}")
    print("=" * 100)


async def main():
    manifest_path = SAMPLE_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print(f"Uploading {len(manifest)} sample calls to {API_URL}...")
    external_id_to_call_id = await upload_all(manifest)

    if external_id_to_call_id:
        print(f"\nPolling until all {len(external_id_to_call_id)} calls reach a terminal state...")
        await poll_until_done(list(external_id_to_call_id.values()))

    await print_summary(manifest, external_id_to_call_id)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
