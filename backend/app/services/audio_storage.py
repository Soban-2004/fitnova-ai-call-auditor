"""Durable audio storage on Backblaze B2, via its S3-compatible API (boto3 —
B2's native API works too, but the S3-compatible one means no new client
library, just a different endpoint_url on the same boto3 the rest of the
Python ecosystem already knows).

Why this exists at all: the local UPLOAD_DIR write in adapters/file_upload.py
is what transcription reads immediately after upload (see
services/transcription.py) — fine for that, since transcription always
happens right after the file lands, long before any restart could occur. But
that local file does NOT survive a container restart/redeploy on a host like
Render, which has no persistent disk by default. This module provides a
second, durable copy specifically for playback later (routers/calls.py's
audio endpoint) — Call.audio_ref keeps meaning "the local path transcription
used," Call.audio_backup_ref is the new, separate "where to find this
durably" reference. Two different fields on purpose: changing what
audio_ref means would risk the proven-working transcription code path for
no reason, since transcription never needs the durable copy at all.

Entirely optional — every function here degrades to a no-op (returns None)
if B2 isn't configured, so the app runs fine without it; only new-upload
audio durability is affected, not by anything else.

boto3 is synchronous; every call here runs through asyncio.to_thread() so it
never blocks the event loop the rest of this async app runs on.
"""
import asyncio
import logging
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger("fitnova.audio_storage")

B2_REF_PREFIX = "b2:"


def is_configured() -> bool:
    return bool(
        settings.B2_ENDPOINT_URL and settings.B2_BUCKET_NAME and settings.B2_KEY_ID and settings.B2_APPLICATION_KEY
    )


def _region_from_endpoint() -> str:
    """B2 endpoints are "s3.<region>.backblazeb2.com" — boto3 needs an
    explicit region to sign with SigV4 against a non-AWS endpoint; without
    one it silently falls back to the legacy SigV2 query-string format
    (AWSAccessKeyId=...&Signature=...), which B2 rejects outright as
    unauthorized rather than a clear signature error (confirmed live: a
    SigV2 presigned URL against B2 came back "bucket is not authorized",
    not a signature-mismatch message)."""
    host = urlparse(settings.B2_ENDPOINT_URL).hostname or ""
    parts = host.split(".")
    return parts[1] if len(parts) > 1 else "us-west-004"


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.B2_ENDPOINT_URL,
        aws_access_key_id=settings.B2_KEY_ID,
        aws_secret_access_key=settings.B2_APPLICATION_KEY,
        region_name=_region_from_endpoint(),
        config=Config(signature_version="s3v4"),
    )


async def upload_audio(local_path: str, key: str) -> str | None:
    """Uploads a local file to B2. Returns the durable "b2:{key}" ref on
    success, or None on any failure (not configured, network error, bad
    credentials, etc.) — a storage-layer hiccup here must never fail the
    upload itself; the local copy already written is enough to proceed, this
    is a best-effort durability upgrade on top of that, not a requirement."""
    if not is_configured():
        return None

    def _do_upload() -> None:
        _client().upload_file(local_path, settings.B2_BUCKET_NAME, key)

    try:
        await asyncio.to_thread(_do_upload)
        return f"{B2_REF_PREFIX}{key}"
    except (BotoCoreError, ClientError, OSError) as e:
        logger.warning("B2 upload failed for key=%s, continuing local-only: %s", key, e)
        return None


async def presigned_url(key: str, expires_in: int = 3600) -> str | None:
    """A time-limited, direct-to-B2 URL — the audio endpoint redirects the
    browser here instead of proxying bytes through this process."""
    if not is_configured():
        return None

    def _do_generate() -> str:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.B2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )

    try:
        return await asyncio.to_thread(_do_generate)
    except (BotoCoreError, ClientError) as e:
        logger.warning("Failed to generate a presigned URL for key=%s: %s", key, e)
        return None
