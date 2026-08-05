"""Source-agnostic ingestion: every call source (telephony webhook, CRM export,
manual upload, future API) maps into the same internal CallEvent through a
thin adapter. Downstream code (state machine, transcription, analysis) never
knows which source a call came from.

To add a new source: implement BaseSourceAdapter.normalize() in a new file,
register it in ingestion.py. No other code changes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CallEvent:
    """Internal contract every source adapter normalizes into.

    Mirrors the `calls` table columns that come from the source (id/status/
    retry_count are assigned by the ingestion service, not the adapter).
    """

    external_id: str
    source_system: str  # 'telephony' | 'crm' | 'file_upload'
    advisor_id: str
    audio_ref: str
    duration_secs: int | None = None
    called_at: datetime | None = None
    customer_phone: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class BaseSourceAdapter(ABC):
    """One interface, one file per vendor. See file_upload.py for the
    prototype implementation; a telephony adapter would instead receive a
    webhook POST with a recording URL, download the audio, and map vendor
    fields (call SID, direction, agent extension, etc.) onto CallEvent —
    same output contract, different input shape.
    """

    @abstractmethod
    async def normalize(self, raw_payload: Any) -> CallEvent:
        """Map a vendor-specific payload to the internal CallEvent."""
        raise NotImplementedError
