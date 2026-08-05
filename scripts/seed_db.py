"""
Seed the database with:
- 1 org (FitNova)
- 3 teams (Alpha, Beta, Gamma)
- 2 advisors per team (6 total)
- 3 prompt versions (one per prompt_type, all v1, all active)

Idempotent: re-running skips rows that already exist (matched by fixed UUID
for org/team/advisor, and by (prompt_type, version) for prompts).

Run from fitnova/backend/: python ../scripts/seed_db.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.database import async_session_factory, dispose_engine  # noqa: E402
from app.models import Org, Team, Advisor, PromptVersion  # noqa: E402

# Fixed UUIDs for predictable references in tests/demo
ORG_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")

TEAM_ALPHA_ID = uuid.UUID("b0000000-0000-0000-0000-000000000001")
TEAM_BETA_ID = uuid.UUID("b0000000-0000-0000-0000-000000000002")
TEAM_GAMMA_ID = uuid.UUID("b0000000-0000-0000-0000-000000000003")

ADVISOR_IDS = {
    "Priya Sharma": uuid.UUID("c0000000-0000-0000-0000-000000000001"),
    "Rahul Mehta": uuid.UUID("c0000000-0000-0000-0000-000000000002"),
    "Ananya Reddy": uuid.UUID("c0000000-0000-0000-0000-000000000003"),
    "Vikram Patel": uuid.UUID("c0000000-0000-0000-0000-000000000004"),
    "Sneha Gupta": uuid.UUID("c0000000-0000-0000-0000-000000000005"),
    "Arjun Nair": uuid.UUID("c0000000-0000-0000-0000-000000000006"),
}

TEAMS = {
    TEAM_ALPHA_ID: {"name": "Team Alpha", "advisors": ["Priya Sharma", "Rahul Mehta"]},
    TEAM_BETA_ID: {"name": "Team Beta", "advisors": ["Ananya Reddy", "Vikram Patel"]},
    TEAM_GAMMA_ID: {"name": "Team Gamma", "advisors": ["Sneha Gupta", "Arjun Nair"]},
}

PROMPT_DIR = BACKEND_DIR / "prompts"
PROMPT_TYPES = ["speaker_identification", "issue_detection", "dimension_rating"]


def _email_for(name: str) -> str:
    return f"{name.lower().replace(' ', '.')}@fitnova.example"


async def seed():
    async with async_session_factory() as session:
        # --- Org ---
        org = await session.get(Org, ORG_ID)
        if org is None:
            org = Org(id=ORG_ID, name="FitNova")
            session.add(org)
            print(f"+ org: {org.name}")
        else:
            print(f"= org already exists: {org.name}")

        # --- Teams + Advisors ---
        for team_id, team_data in TEAMS.items():
            team = await session.get(Team, team_id)
            if team is None:
                team = Team(id=team_id, org_id=ORG_ID, name=team_data["name"])
                session.add(team)
                print(f"+ team: {team_data['name']}")
            else:
                print(f"= team already exists: {team_data['name']}")

            for advisor_name in team_data["advisors"]:
                advisor_id = ADVISOR_IDS[advisor_name]
                advisor = await session.get(Advisor, advisor_id)
                if advisor is None:
                    advisor = Advisor(
                        id=advisor_id,
                        team_id=team_id,
                        name=advisor_name,
                        email=_email_for(advisor_name),
                    )
                    session.add(advisor)
                    print(f"  + advisor: {advisor_name}")
                else:
                    print(f"  = advisor already exists: {advisor_name}")

        # --- Prompt versions (v1, active) ---
        for prompt_type in PROMPT_TYPES:
            prompt_file = PROMPT_DIR / f"{prompt_type}_v1.txt"
            if not prompt_file.exists():
                print(f"! missing prompt file, skipping: {prompt_file}")
                continue

            existing = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_type == prompt_type,
                    PromptVersion.version == 1,
                )
            )
            if existing.scalar_one_or_none() is not None:
                print(f"= prompt already seeded: {prompt_type} v1")
                continue

            prompt_text = prompt_file.read_text(encoding="utf-8")
            session.add(
                PromptVersion(
                    prompt_type=prompt_type,
                    version=1,
                    system_prompt=prompt_text,
                    is_active=True,
                )
            )
            print(f"+ prompt: {prompt_type} v1 (active)")

        await session.commit()
    await dispose_engine()
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
