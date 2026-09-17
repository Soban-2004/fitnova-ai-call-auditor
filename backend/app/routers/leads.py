"""Leads: the AI voice agent's actual hand-off to a human advisor.

A Lead is created once (routers/voice_agent.py, when a qualifying call
finishes) and then moves through NEW -> ASSIGNED -> CONTACTED ->
TRIAL_BOOKED as a real advisor works it -- replacing what used to be just
a spoken promise ("an advisor will follow up") plus a saved Call nobody
was pointed at. Deliberately not a CRM: one table, one status enum, no
notifications/queues -- see app/models/lead.py's docstring for the scope
reasoning.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead import Lead
from app.models.org import Advisor
from app.schemas.lead import LEAD_STATUSES, AssignLeadRequest, LeadOut, UpdateLeadStatusRequest
from app.services.query_helpers import latest_scores_for_calls

router = APIRouter(prefix="/api/leads", tags=["leads"])


async def _to_lead_out(session: AsyncSession, lead: Lead, advisor_names: dict[str, str], score: int | None) -> LeadOut:
    return LeadOut(
        id=str(lead.id),
        call_id=str(lead.call_id),
        customer_name=lead.customer_name,
        customer_phone=lead.customer_phone,
        fitness_goal=lead.fitness_goal,
        health_notes=lead.health_notes,
        availability=lead.availability,
        confirmed_time=lead.confirmed_time,
        assigned_advisor_id=str(lead.assigned_advisor_id) if lead.assigned_advisor_id else None,
        assigned_advisor_name=advisor_names.get(str(lead.assigned_advisor_id)) if lead.assigned_advisor_id else None,
        status=lead.status,
        call_score=score,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.get("", response_model=list[LeadOut])
async def list_leads(
    status: str | None = None,
    assigned_advisor_id: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[LeadOut]:
    query = select(Lead).order_by(Lead.created_at.desc())
    if status:
        query = query.where(Lead.status == status)
    if assigned_advisor_id:
        query = query.where(Lead.assigned_advisor_id == assigned_advisor_id)
    leads = (await session.execute(query)).scalars().all()

    advisor_ids = {str(lead.assigned_advisor_id) for lead in leads if lead.assigned_advisor_id}
    advisors = (
        (await session.execute(select(Advisor).where(Advisor.id.in_(advisor_ids)))).scalars().all()
        if advisor_ids
        else []
    )
    advisor_names = {str(a.id): a.name for a in advisors}

    scores = await latest_scores_for_calls(session, [str(lead.call_id) for lead in leads])

    return [
        await _to_lead_out(
            session, lead, advisor_names, scores[str(lead.call_id)].final_score if str(lead.call_id) in scores else None
        )
        for lead in leads
    ]


@router.post("/{lead_id}/assign", response_model=LeadOut)
async def assign_lead(lead_id: str, body: AssignLeadRequest, session: AsyncSession = Depends(get_db)) -> LeadOut:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    advisor = await session.get(Advisor, body.advisor_id)
    if advisor is None:
        raise HTTPException(status_code=404, detail=f"Advisor {body.advisor_id} not found")

    lead.assigned_advisor_id = advisor.id
    if lead.status == "NEW":
        lead.status = "ASSIGNED"
    await session.commit()
    await session.refresh(lead)

    scores = await latest_scores_for_calls(session, [str(lead.call_id)])
    score = scores[str(lead.call_id)].final_score if str(lead.call_id) in scores else None
    return await _to_lead_out(session, lead, {str(advisor.id): advisor.name}, score)


@router.post("/{lead_id}/status", response_model=LeadOut)
async def update_lead_status(lead_id: str, body: UpdateLeadStatusRequest, session: AsyncSession = Depends(get_db)) -> LeadOut:
    if body.status not in LEAD_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {LEAD_STATUSES}")
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

    lead.status = body.status
    await session.commit()
    await session.refresh(lead)

    advisor_names = {}
    if lead.assigned_advisor_id:
        advisor = await session.get(Advisor, lead.assigned_advisor_id)
        if advisor:
            advisor_names = {str(advisor.id): advisor.name}
    scores = await latest_scores_for_calls(session, [str(lead.call_id)])
    score = scores[str(lead.call_id)].final_score if str(lead.call_id) in scores else None
    return await _to_lead_out(session, lead, advisor_names, score)
