from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.file_upload import FileUploadAdapter
from app.database import get_db
from app.models.org import Advisor
from app.schemas.call import UploadResponse
from app.services.ingestion import DuplicateCallError, ingest_call_event

router = APIRouter(prefix="/api", tags=["upload"])
_adapter = FileUploadAdapter()


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_call(
    audio_file: UploadFile = File(...),
    advisor_id: str = Form(...),
    customer_phone: str | None = Form(None),
    external_id: str | None = Form(None),
    metadata: str | None = Form(None),
    session: AsyncSession = Depends(get_db),
):
    advisor = await session.get(Advisor, advisor_id)
    if advisor is None:
        raise HTTPException(status_code=404, detail=f"Advisor {advisor_id} not found")

    try:
        event = await _adapter.normalize(
            {
                "audio_file": audio_file,
                "advisor_id": advisor_id,
                "customer_phone": customer_phone,
                "external_id": external_id,
                "metadata": metadata,
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        result = await ingest_call_event(session, event)
    except DuplicateCallError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))

    await session.commit()

    message = "Call re-queued for retry" if result.is_retry else "Call queued for processing"
    return UploadResponse(call_id=result.call_id, status=result.status, message=message)
