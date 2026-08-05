import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.adapters.base import BaseSourceAdapter, CallEvent
from app.config import settings

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".m4a", ".webm"}


class FileUploadAdapter(BaseSourceAdapter):
    """Prototype adapter: accepts an audio file + metadata via POST /api/upload.

    A future TelephonyWebhookAdapter would differ only in normalize(): it
    receives a JSON POST with a recording URL instead of a multipart file,
    downloads the audio to the same UPLOAD_DIR, and maps vendor call-id/
    agent-id/timestamp fields onto the same CallEvent fields below.
    """

    def __init__(self, upload_dir: str | None = None):
        self.upload_dir = Path(upload_dir or settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def normalize(
        self,
        raw_payload: dict,
    ) -> CallEvent:
        """
        raw_payload keys: audio_file (UploadFile), advisor_id (str),
        customer_phone (str | None), external_id (str | None), metadata (str | None JSON)
        """
        audio_file: UploadFile = raw_payload["audio_file"]
        advisor_id: str = raw_payload["advisor_id"]
        customer_phone: str | None = raw_payload.get("customer_phone")
        external_id: str | None = raw_payload.get("external_id")
        metadata_str: str | None = raw_payload.get("metadata")

        ext = Path(audio_file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported audio format '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

        external_id = external_id or str(uuid.uuid4())
        stored_filename = f"{external_id}{ext}"
        dest_path = self.upload_dir / stored_filename

        contents = await audio_file.read()
        async with aiofiles.open(dest_path, "wb") as out:
            await out.write(contents)

        raw_metadata: dict = {}
        if metadata_str:
            try:
                raw_metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                raw_metadata = {"unparsed_metadata": metadata_str}
        raw_metadata["original_filename"] = audio_file.filename
        raw_metadata["content_type"] = audio_file.content_type

        return CallEvent(
            external_id=external_id,
            source_system="file_upload",
            advisor_id=advisor_id,
            audio_ref=str(dest_path),
            called_at=datetime.now(timezone.utc),
            customer_phone=customer_phone,
            raw_metadata=raw_metadata,
        )
