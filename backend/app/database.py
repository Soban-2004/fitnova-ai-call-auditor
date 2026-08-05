import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# asyncpg + Windows' default ProactorEventLoop has a known teardown bug: the SSL
# transport throws "Fatal error on SSL transport" / "Event loop is closed" during
# interpreter exit, after all work has already completed successfully. Switching
# to the selector loop on Windows avoids it. No-op on Linux/Mac.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency — yields a request-scoped async session."""
    async with async_session_factory() as session:
        yield session


async def dispose_engine():
    """Call at the end of standalone scripts (seed_db.py etc.) so the connection
    pool closes cleanly before the event loop exits."""
    await engine.dispose()
