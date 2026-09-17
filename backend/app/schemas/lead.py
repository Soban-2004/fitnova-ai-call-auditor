from datetime import datetime

from pydantic import BaseModel

LEAD_STATUSES = ["NEW", "ASSIGNED", "CONTACTED", "TRIAL_BOOKED"]


class LeadOut(BaseModel):
    id: str
    call_id: str
    customer_name: str | None
    customer_phone: str | None
    fitness_goal: str | None
    health_notes: str | None
    availability: str | None
    confirmed_time: str | None
    assigned_advisor_id: str | None
    assigned_advisor_name: str | None
    status: str
    # The AI qualification call's own score -- lets an advisor (or a
    # director looking at the funnel) see how good the intake call was
    # before deciding how to follow up, not just that one happened.
    call_score: int | None
    created_at: datetime
    updated_at: datetime


class AssignLeadRequest(BaseModel):
    advisor_id: str


class UpdateLeadStatusRequest(BaseModel):
    status: str
