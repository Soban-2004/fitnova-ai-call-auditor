from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.org import Advisor, Org, Team
from app.schemas.org import AdvisorOut, OrgOut, TeamOut

router = APIRouter(prefix="/api", tags=["org"])


@router.get("/orgs", response_model=list[OrgOut])
async def list_orgs(session: AsyncSession = Depends(get_db)):
    orgs = (await session.execute(select(Org).order_by(Org.name))).scalars().all()
    return [OrgOut(id=str(o.id), name=o.name, created_at=o.created_at) for o in orgs]


@router.get("/teams", response_model=list[TeamOut])
async def list_teams(session: AsyncSession = Depends(get_db)):
    rows = (
        await session.execute(select(Team, Org.name).join(Org, Team.org_id == Org.id).order_by(Team.name))
    ).all()
    return [
        TeamOut(id=str(team.id), org_id=str(team.org_id), org_name=org_name, name=team.name, created_at=team.created_at)
        for team, org_name in rows
    ]


@router.get("/advisors", response_model=list[AdvisorOut])
async def list_advisors(team_id: str | None = None, session: AsyncSession = Depends(get_db)):
    query = select(Advisor, Team.name).join(Team, Advisor.team_id == Team.id)
    if team_id:
        query = query.where(Advisor.team_id == team_id)
    rows = (await session.execute(query.order_by(Advisor.name))).all()
    return [
        AdvisorOut(
            id=str(advisor.id), team_id=str(advisor.team_id), team_name=team_name,
            name=advisor.name, email=advisor.email, created_at=advisor.created_at,
        )
        for advisor, team_name in rows
    ]
