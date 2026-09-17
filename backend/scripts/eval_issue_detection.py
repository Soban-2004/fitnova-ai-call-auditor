"""Labeled benchmark for issue detection (services/analysis.py's detect_issues,
Call #2 of the 3-pass LLM analysis) -- the component whose output most
directly drives what a director/team-leader sees and what a call's score
gets docked for, and the one every other layer (3-layer validation, contest/
review, scoring) exists to check the work of.

Deliberately offline from the real upload/transcription pipeline: these are
hand-written transcript segments, not real Deepgram output, so this isolates
issue-detection accuracy from transcription/diarization accuracy (a separate,
much better-understood concern -- Deepgram's own accuracy isn't this
project's code to fix). It does hit the real, configured LLM fallback chain
(Groq->Gemini->Ollama) for real, though, and does read the real active
"issue_detection" prompt from the database -- both exactly as production
would.

Run by hand only -- never wire this into a request path (each run is a
handful of real LLM calls against the same free-tier quotas the fallback
chain already runs tight on).

Usage (from backend/):
    python scripts/eval_issue_detection.py
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_session_factory  # noqa: E402
from app.services.analysis import detect_issues, get_active_prompt  # noqa: E402

_RESULTS_PATH = Path(__file__).resolve().parent / "eval_results.json"
_MAX_HISTORY_ENTRIES = 50


def _seg(t0: float, t1: float, role: str, text: str) -> dict:
    return {"start_ts": t0, "end_ts": t1, "speaker_role": role, "text": text}


# Each scenario: (name, segments, tags that MUST appear, tags that must NOT
# appear). Not exact-set matching -- a real issue-detection model may
# reasonably surface a legitimate issue this hand-written label set didn't
# anticipate, and penalizing that would just be testing my own labeling
# completeness, not the model. What actually matters: does it catch the
# violations that are unambiguously there, and does it stay quiet on a call
# that did the right things.
_SCENARIOS: list[tuple[str, list[dict], set[str], set[str]]] = [
    (
        "good_call",  # mirrors scripts/generate_test_upload_calls.py's "good" sample
        [
            _seg(0, 4, "advisor", "Hi, this is Priya from FitNova. Am I speaking with Karan?"),
            _seg(4, 6, "customer", "Yes, speaking."),
            _seg(
                6, 11, "advisor",
                "Great! What are you currently looking to work on -- weight loss, strength, or general fitness?",
            ),
            _seg(
                11, 17, "customer",
                "Mostly general fitness, I sit at a desk all day and want to get more active.",
            ),
            _seg(17, 22, "advisor", "Makes sense. Any injuries or health conditions I should know about?"),
            _seg(22, 25, "customer", "No, nothing like that, I'm generally healthy."),
            _seg(
                25, 35, "advisor",
                "Good to know. Our Standard plan is four thousand five hundred a month, three sessions "
                "a week plus a diet plan. Want me to book a free trial first so your coach can assess you?",
            ),
            _seg(35, 37, "customer", "Yes, that sounds good."),
            _seg(37, 41, "advisor", "I have a slot Saturday at 5 PM online -- does that work?"),
            _seg(41, 43, "customer", "Saturday works for me, thank you."),
            _seg(43, 46, "advisor", "Perfect, you're all booked. Have a great day!"),
        ],
        set(),  # nothing should fire on a call that did discovery, disclosed price, and booked a real trial
        {"NO_NEEDS_DISCOVERY", "PRESSURE_SELLING", "UNDISCLOSED_COSTS", "NO_TRIAL_BOOKING"},
    ),
    (
        "pressure_call",  # mirrors scripts/generate_test_upload_calls.py's "pressure" sample
        [
            _seg(0, 3, "advisor", "Hi, this is Rahul from FitNova calling about your fitness enquiry."),
            _seg(3, 4, "customer", "Oh, hi."),
            _seg(
                4, 9, "advisor",
                "Look, I'll be direct -- we have an offer that expires tonight at midnight, "
                "so I don't want you to miss it.",
            ),
            _seg(9, 11, "customer", "What's the offer?"),
            _seg(
                11, 18, "advisor",
                "Normally six thousand a month, but if you lock in right now I can get you three "
                "thousand five hundred. This price is gone the moment I hang up.",
            ),
            _seg(18, 21, "customer", "I was hoping to think it over for a day."),
            _seg(
                21, 27, "advisor",
                "Honestly there's only one slot left this month, and thinking about it means losing "
                "it. Should I just book you in right now?",
            ),
            _seg(27, 30, "customer", "Okay, I guess, if it's really ending today."),
            _seg(30, 33, "advisor", "Great, you're locked in. I'll send the details shortly."),
        ],
        {"PRESSURE_SELLING", "NO_NEEDS_DISCOVERY"},  # false urgency/scarcity, and never asks what the customer needs
        set(),
    ),
    (
        "compliance_violation_call",  # hand-written, not from the sample-call scripts
        [
            _seg(0, 3, "advisor", "Hi, this is calling from FitNova about your enquiry."),
            _seg(3, 4, "customer", "Hi."),
            _seg(5, 9, "advisor", "What's your main fitness goal at the moment?"),
            _seg(9, 12, "customer", "I want to lose about ten kilos."),
            _seg(
                12, 20, "advisor",
                "With our program I can guarantee you'll lose ten kilos in two weeks, no matter what "
                "your body type is -- it's medically proven to work for everyone.",
            ),
            _seg(20, 23, "customer", "That sounds almost too good to be true."),
            _seg(
                23, 30, "advisor",
                "I promise it, we've never had it not work. Should I sign you up for the twelve-month plan?",
            ),
            _seg(30, 32, "customer", "Sure, I guess."),
        ],
        {"COMPLIANCE_VIOLATION", "OVER_PROMISING"},  # unrealistic/guaranteed health outcome claim
        set(),
    ),
]


async def _run_scenario(session, prompt: str, name: str, segments: list[dict], must_have: set[str], must_not: set[str]):
    result = await detect_issues(segments, prompt)
    detected = {issue.tag for issue in result.issues}

    hits = must_have & detected
    misses = must_have - detected
    false_positives = must_not & detected

    print(f"\n=== {name} ===")
    print(f"  call_type      : {result.call_type}")
    print(f"  detected tags  : {sorted(detected) or '(none)'}")
    if misses:
        print(f"  MISSED (expected but not flagged): {sorted(misses)}")
    if false_positives:
        print(f"  FALSE POSITIVE (should never have fired): {sorted(false_positives)}")
    if not misses and not false_positives:
        print("  OK -- matches expectations")

    return {
        "name": name,
        "must_have": sorted(must_have),
        "must_not": sorted(must_not),
        "detected": sorted(detected),
        "hits": sorted(hits),
        "misses": sorted(misses),
        "false_positives": sorted(false_positives),
    }


async def main() -> int:
    async with async_session_factory() as session:
        prompt = await get_active_prompt(session, "issue_detection")

        results = []
        for name, segments, must_have, must_not in _SCENARIOS:
            results.append(await _run_scenario(session, prompt.system_prompt, name, segments, must_have, must_not))

    total_must_have = sum(len(r["must_have"]) for r in results)
    total_hits = sum(len(r["hits"]) for r in results)
    total_false_positives = sum(len(r["false_positives"]) for r in results)
    recall = total_hits / total_must_have if total_must_have else 1.0

    print("\n=== Overall ===")
    print(f"  scenarios            : {len(results)}")
    print(f"  recall (must-have)   : {recall:.1%}  ({total_hits}/{total_must_have})")
    print(f"  false positives      : {total_false_positives}")

    _append_history(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenarios": len(results),
            "recall": round(recall, 4),
            "false_positives": total_false_positives,
            "results": results,
        }
    )

    # Non-zero exit on a real regression -- a miss on a must-have tag, or any
    # false positive on a call that should have stayed clean.
    return 0 if recall == 1.0 and total_false_positives == 0 else 1


def _append_history(entry: dict) -> None:
    history: list[dict] = []
    if _RESULTS_PATH.exists():
        try:
            history = json.loads(_RESULTS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            history = []
    history.append(entry)
    history = history[-_MAX_HISTORY_ENTRIES:]
    _RESULTS_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"\n  (appended to {_RESULTS_PATH.name}, {len(history)} run(s) of history)")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
