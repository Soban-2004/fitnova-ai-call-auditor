"""
Promote a new prompt version: deactivates the current active row for a
prompt_type and inserts+activates the new one. The old version is never
deleted (design doc Section 5, Prompt Versioning) — every issue_tag /
dimension_rating already stored still points at the prompt_version_id that
actually produced it, so "why did scoring patterns change?" stays answerable
by diffing versions.

Usage: python upgrade_prompt.py <prompt_type> <version> <prompt_file>
Example: python upgrade_prompt.py issue_detection 2 ../backend/prompts/issue_detection_v2.txt
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.database import async_session_factory, dispose_engine  # noqa: E402
from app.models.analysis import PromptVersion  # noqa: E402


async def upgrade(prompt_type: str, version: int, prompt_file: Path) -> None:
    text = prompt_file.read_text(encoding="utf-8")

    async with async_session_factory() as session:
        existing = await session.scalar(
            select(PromptVersion).where(
                PromptVersion.prompt_type == prompt_type, PromptVersion.version == version
            )
        )
        if existing is not None:
            print(f"{prompt_type} v{version} already exists (id={existing.id}) — activating it.")
            new_row = existing
        else:
            new_row = PromptVersion(prompt_type=prompt_type, version=version, system_prompt=text)
            session.add(new_row)
            print(f"+ inserted {prompt_type} v{version}")

        currently_active = (
            await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_type == prompt_type, PromptVersion.is_active.is_(True)
                )
            )
        ).scalars().all()
        for row in currently_active:
            if row.version != version:
                row.is_active = False
                print(f"- deactivated {prompt_type} v{row.version}")

        new_row.is_active = True
        new_row.system_prompt = text
        await session.commit()
        print(f"= {prompt_type} v{version} is now active")

    await dispose_engine()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    asyncio.run(upgrade(sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])))
