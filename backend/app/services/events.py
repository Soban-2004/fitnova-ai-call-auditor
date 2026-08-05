"""In-process pub-sub for Server-Sent Events (routers/events.py).

No Redis/broker — the background worker (processor.py) and the API server
share one process, so an `asyncio.Queue` per connected client is enough.
This would need a real broker (Redis pub/sub, etc.) the moment there's more
than one backend process/worker, since subscribers only ever see events
published within their own process.
"""
import asyncio
import logging
from typing import Any

logger = logging.getLogger("fitnova.events")


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def publish(self, event: dict[str, Any]) -> None:
        """Never raises — a broadcast failure must not take down the
        pipeline that triggered it. Full subscriber queues are dropped
        (a slow/stalled client shouldn't back-pressure the worker)."""
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropping event for a slow SSE subscriber (queue full)")
            except Exception:
                logger.exception("Failed to publish event to a subscriber")


broadcaster = EventBroadcaster()


# In-memory per-call progress ("current_step"), read by GET /calls/{id}/status.
#
# Deliberately NOT a DB column: the natural place to write it would be
# `calls.current_step`, but run_worker_once() holds a `SELECT ... FOR UPDATE`
# lock on that exact row for the pipeline's entire duration, and Postgres
# blocks any other connection's UPDATE on a locked row until the lock is
# released — confirmed empirically (a second session's UPDATE sat blocked
# for 5+ seconds with no sign of returning). A per-step DB write would either
# hang the whole pipeline or, worse, tie up a connection until something
# times it out. An in-memory dict has no lock to wait on and no connection
# cost; the cost is that progress is lost on a process restart, which is
# fine for a purely-cosmetic "how far along is this" display — see
# routers/calls.py's fallback to the coarse status-derived guess.
_call_progress: dict[str, str] = {}


def set_call_progress(call_id: str, step: str | None) -> None:
    if step is None:
        _call_progress.pop(call_id, None)
    else:
        _call_progress[call_id] = step


def get_call_progress(call_id: str) -> str | None:
    return _call_progress.get(call_id)
