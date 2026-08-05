"""Server-Sent Events stream — lets a dashboard tab find out a call finished
processing without polling. One-directional (server -> client) by nature, so
SSE rather than a full WebSocket; the browser's native EventSource also
handles reconnect-on-drop for free. Hand-rolled on FastAPI's StreamingResponse
(text/event-stream is just a plain text format — no extra dependency needed
for something this small).

Frontend subscribes once (see components/layout/LiveUpdates.tsx) and calls
Next.js's router.refresh() on any event — that re-runs the current route's
server-side data fetch in place, no full page reload.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.events import broadcaster

logger = logging.getLogger("fitnova.events")
router = APIRouter(prefix="/api", tags=["events"])

HEARTBEAT_SECONDS = 15


@router.get("/events")
async def stream_events(request: Request):
    queue = broadcaster.subscribe()

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Comment-only heartbeat so idle proxies/load balancers
                    # don't time the connection out.
                    yield ": keep-alive\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering if this ever sits behind nginx
        },
    )
