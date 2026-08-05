"""Pydantic models for the 3 LLM call outputs (design doc Section 5).

These are deliberately loose on `tag`/`severity` (plain str, not a Literal
enum) — an unknown tag or severity here should reject *that one issue* in
services/validation.py's Layer 1, not blow up json parsing for the entire
response and lose every other (valid) issue the LLM found in the same call.
Structural shape (right keys, right types) is what Pydantic enforces here;
enum membership is enforced per-item downstream.
"""
from pydantic import BaseModel, Field
from typing import Literal

ISSUE_TAG_TYPES = [
    "NO_NEEDS_DISCOVERY",
    "OVER_PROMISING",
    "PRESSURE_SELLING",
    "PRICE_BEFORE_VALUE",
    "UNDISCLOSED_COSTS",
    "WEAK_TRIAL_BOOKING",
    "NO_TRIAL_BOOKING",
    "TALKING_OVER_CUSTOMER",
    "NO_OBJECTION_HANDLING",
    "NO_NEXT_STEPS",
    "COMPLIANCE_VIOLATION",
]
SEVERITIES = ["critical", "major", "minor"]
DIMENSION_NAMES = [
    "needs_discovery",
    "product_knowledge",
    "objection_handling",
    "compliance",
    "trial_booking",
    "rapport_building",
]


class SpeakerIdResult(BaseModel):
    speaker_0: Literal["advisor", "customer"]
    speaker_1: Literal["advisor", "customer"]
    confidence: Literal["high", "medium", "low"]
    reasoning: str = ""


class IssueTagLLM(BaseModel):
    tag: str
    severity: str
    quote: str
    start_ts: float = 0.0
    end_ts: float = 0.0
    reason: str = ""


class IssueDetectionResult(BaseModel):
    call_type: Literal["sales", "non_sales", "unclear"] = "unclear"
    issues: list[IssueTagLLM] = Field(default_factory=list)


class DimensionScore(BaseModel):
    score: int
    evidence: str = ""


class DimensionRatingResult(BaseModel):
    dimensions: dict[str, DimensionScore] = Field(default_factory=dict)
