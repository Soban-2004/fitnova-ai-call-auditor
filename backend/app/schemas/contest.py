from typing import Literal

from pydantic import BaseModel


class ContestRequest(BaseModel):
    reason: str


class ContestResponse(BaseModel):
    tag_id: str
    status: str
    message: str


class ReviewRequest(BaseModel):
    action: Literal["confirm", "dismiss"]
    comment: str = ""
    reviewed_by: str = "Team Leader"


class ReviewResponse(BaseModel):
    tag_id: str
    status: str
    score_updated: bool
    old_score: int | None = None
    new_score: int | None = None
    new_version: int | None = None
