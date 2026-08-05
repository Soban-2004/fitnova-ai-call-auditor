"""
Backdates historical clones of the 5 scored sample calls across the past
6 weeks so the dashboard trend charts have more than one ISO-week bucket to
draw a line through (see query_helpers.build_score_trend, which groups by
Call.called_at — every real sample call currently lands in the *same* week
since they were all ingested on the same day, so the trend line is a single
flat point until this backfill runs).

This is pure DB backfill — no Deepgram/LLM calls, no cost. Every row it
creates uses source_system="seed_backfill" (never "file_upload") so it's
trivially distinguishable from real pipeline output and gets called out
explicitly in the README's "what's mocked" section.

Idempotent: re-running skips any (external_id, week) pair already backfilled,
so it's safe to run again after adding new sample calls.

Run from fitnova/backend/: python ../scripts/seed_score_history.py
"""
import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.database import async_session_factory, dispose_engine  # noqa: E402
from app.models.analysis import DimensionRating, IssueTag  # noqa: E402
from app.models.call import Call  # noqa: E402
from app.models.score import CallScore  # noqa: E402
from app.models.transcript import TranscriptSegment  # noqa: E402

WEEKS_BACK = 6
JITTER_POINTS = 8  # +/- applied to final_score per historical week — mild random noise, no invented trend
SOURCE_SYSTEM = "seed_backfill"

# call_06_nonsales has no score (it's a wrong-number call) so it contributes
# nothing to a score trend — deliberately excluded.
SCORING_EXTERNAL_IDS = [
    "call_01_good",
    "call_02_pressure",
    "call_03_no_discovery",
    "call_04_overpromise",
    "call_05_codeswitching",
]


async def _load_original(session, external_id: str) -> Call | None:
    return await session.scalar(
        select(Call).where(Call.source_system == "file_upload", Call.external_id == external_id)
    )


async def _already_backfilled(session, seed_external_id: str) -> bool:
    existing = await session.scalar(
        select(Call.id).where(Call.source_system == SOURCE_SYSTEM, Call.external_id == seed_external_id)
    )
    return existing is not None


async def _clone_one(session, original: Call, week_offset: int) -> bool:
    seed_external_id = f"{original.external_id}-seed-wk{week_offset}"
    if await _already_backfilled(session, seed_external_id):
        return False

    # Backdate into a distinct ISO week; jitter by a few days/hours so points
    # aren't robotically exactly 7 days apart.
    now = datetime.now(timezone.utc)
    called_at = now - timedelta(weeks=week_offset, days=random.randint(-2, 2), hours=random.randint(0, 23))

    new_call = Call(
        id=uuid.uuid4(),
        advisor_id=original.advisor_id,
        source_system=SOURCE_SYSTEM,
        external_id=seed_external_id,
        audio_ref=original.audio_ref,
        duration_secs=original.duration_secs,
        called_at=called_at,
        status="COMPLETED",
        call_type=original.call_type,
        diarization_quality=original.diarization_quality,
        created_at=called_at,
        updated_at=called_at,
    )
    session.add(new_call)
    await session.flush()

    segments = (
        await session.execute(select(TranscriptSegment).where(TranscriptSegment.call_id == original.id))
    ).scalars().all()
    for seg in segments:
        session.add(TranscriptSegment(
            id=uuid.uuid4(), call_id=new_call.id, speaker_label=seg.speaker_label,
            speaker_role=seg.speaker_role, text=seg.text, start_ts=seg.start_ts, end_ts=seg.end_ts,
        ))

    tags = (await session.execute(select(IssueTag).where(IssueTag.call_id == original.id))).scalars().all()
    for tag in tags:
        session.add(IssueTag(
            id=uuid.uuid4(), call_id=new_call.id, prompt_version_id=tag.prompt_version_id,
            tag_type=tag.tag_type, severity=tag.severity, quote=tag.quote,
            start_ts=tag.start_ts, end_ts=tag.end_ts, reason=tag.reason,
            validation_score=tag.validation_score,
            status="open",  # reset — no contest/dismiss history to replay onto a clone
        ))

    dims = (
        await session.execute(select(DimensionRating).where(DimensionRating.call_id == original.id))
    ).scalars().all()
    for dim in dims:
        session.add(DimensionRating(
            id=uuid.uuid4(), call_id=new_call.id, prompt_version_id=dim.prompt_version_id,
            dimension=dim.dimension, score=dim.score, evidence=dim.evidence,
        ))

    latest_score = await session.scalar(
        select(CallScore).where(CallScore.call_id == original.id).order_by(CallScore.version.desc())
    )
    if latest_score:
        jitter = random.randint(-JITTER_POINTS, JITTER_POINTS)
        final_score = max(0, min(100, latest_score.final_score + jitter))
        session.add(CallScore(
            id=uuid.uuid4(), call_id=new_call.id, version=1,
            base_score=latest_score.base_score,
            deductions_total=round(latest_score.base_score - final_score, 1),
            final_score=final_score,
            trigger="seed_backfill", computed_at=called_at,
        ))

    return True


async def main():
    async with async_session_factory() as session:
        originals = {}
        for external_id in SCORING_EXTERNAL_IDS:
            original = await _load_original(session, external_id)
            if original is None:
                print(f"  SKIP {external_id}: not found — run process_all_samples.py first")
                continue
            originals[external_id] = original

        created = 0
        for external_id, original in originals.items():
            made = 0
            for week_offset in range(1, WEEKS_BACK + 1):
                if await _clone_one(session, original, week_offset):
                    made += 1
            created += made
            print(f"  {external_id}: {made} new week(s) backfilled ({WEEKS_BACK - made} already existed)")

        await session.commit()
        print(f"\nDone — {created} historical call+score rows created across up to {WEEKS_BACK} weeks.")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
