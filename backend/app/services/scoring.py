"""Deterministic scoring engine (design doc Section 7).

Core principle: the LLM identifies observations (dimension scores, issue
tags). This function does all the arithmetic. No LLM ever computes a score —
that's what makes scores reproducible, auditable, and safe to recalculate
instantly when a tag is dismissed (see the contest/review flow in Phase 6).
"""
from dataclasses import dataclass

from app.config import settings


@dataclass
class ScoreResult:
    base_score: float
    deductions_total: float
    final_score: int


def compute_score(dimension_ratings: dict[str, dict], tags: list[dict]) -> ScoreResult:
    """
    Args:
        dimension_ratings: {"needs_discovery": {"score": 7}, ...} — 0-10 each.
        tags: issue tag dicts, each with at least {"severity", "status"},
              ideally also "tag_type". Only status == "open" tags are
              deducted; needs_review/contested/dismissed/confirmed tags never
              affect the score (confirmed is a deliberate no-op — see design
              doc Section 10).

    Returns:
        ScoreResult(base_score, deductions_total, final_score)

    Deduction dedup: a given tag_type deducts at most once per call, even if
    it was flagged multiple times (e.g. an advisor using 4 separate
    pressure-selling lines across a call). Found via real testing —
    undeduped, a repeated behavior can stack past any base score and floor
    every affected call to 0, which destroys the score's signal (a call with
    one bad line and a call with four become indistinguishable). Deducting
    once per distinct issue *category* keeps the score meaningful while every
    individual instance is still stored and shown as separate evidence in the
    UI — this only changes what counts toward arithmetic, not what's
    recorded. Tags without a tag_type (e.g. ad-hoc test fixtures) fall back
    to per-instance deduction so existing behavior is unaffected.
    """
    weights = settings.scoring_weights
    penalties = settings.severity_penalties

    base_score = 0.0
    for dim_name, weight in weights.items():
        dim = dimension_ratings.get(dim_name, {})
        score = dim.get("score", 5)  # default to neutral if the LLM omitted a dimension
        base_score += score * 10 * weight

    open_tags = [tag for tag in tags if tag.get("status") == "open"]
    severity_by_type: dict[object, str] = {}
    for tag in open_tags:
        key = tag.get("tag_type") or id(tag)
        severity_by_type.setdefault(key, tag["severity"])

    deductions = sum(penalties.get(severity, 0) for severity in severity_by_type.values())

    final_score = max(0, round(base_score - deductions))

    return ScoreResult(
        base_score=round(base_score, 1),
        deductions_total=float(deductions),
        final_score=final_score,
    )
