from datetime import datetime

from pydantic import BaseModel


class OrgOut(BaseModel):
    id: str
    name: str
    created_at: datetime


class TeamOut(BaseModel):
    id: str
    org_id: str
    org_name: str
    name: str
    created_at: datetime


class AdvisorOut(BaseModel):
    id: str
    team_id: str
    team_name: str
    name: str
    email: str | None
    created_at: datetime
