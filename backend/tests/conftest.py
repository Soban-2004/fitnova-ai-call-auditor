"""Session-wide test fixtures.

app/database.py's `engine` is a module-level singleton with a pooled
asyncpg connection pool. pytest-asyncio gives each test its own event loop
by default, and a pooled connection created on test A's loop is unusable on
test B's loop ("Future attached to a different loop" / "Event loop is
closed" on teardown). Disposing the engine after every test forces a fresh
pool (and fresh connections) on the next test's loop — the standard fix for
this exact async-SQLAlchemy + pytest-asyncio interaction.
"""
import pytest_asyncio

from app.database import engine


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()
