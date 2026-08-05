"""Regex-based PII redaction, applied before any LLM sees a transcript (and
before a raw customer phone number is ever persisted to raw_metadata).

Production upgrade path (documented, not built): swap these regexes for a
dedicated PII detection model (e.g. Microsoft Presidio) for higher recall on
names and less-structured PII. Regex is precise enough for the highly
structured PII types below (phone/email/Aadhaar/card/PAN) but is not a
general-purpose NER system — customer *name* redaction here is intentionally
conservative (title-based heuristic) rather than a false claim of full NER.
"""
import re

# Order matters: more specific patterns (Aadhaar, PAN, card) must run before
# the general phone pattern, or their digit runs get partially eaten by it.
PII_PATTERNS: list[tuple[str, str]] = [
    # PAN card: AAAAA0000A format — must precede generic patterns
    (r"\b[A-Z]{5}\d{4}[A-Z]\b", "[PAN]"),
    # Email
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL]"),
    # Credit/debit card: 13-19 digits, optionally grouped in 4s with spaces/dashes
    (r"\b(?:\d[ -]?){13,19}\b", "[CARD]"),
    # Aadhaar: exactly 12 digits, optionally grouped as 4-4-4
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[AADHAAR]"),
    # Indian mobile: 10 digits starting 6-9, optional +91/0 prefix
    (r"(?:\+91[\s-]?|0)?[6-9]\d{9}\b", "[PHONE]"),
    # Indian landline with STD code
    (r"\b0\d{2,4}[\s-]?\d{6,8}\b", "[PHONE]"),
]

# Very small heuristic for "my name is X" / "this is X speaking" patterns.
# Deliberately conservative — false negatives are safer than mangling
# ordinary sentences. This is the piece the Presidio upgrade replaces.
_NAME_PATTERNS = [
    re.compile(r"\bmy name is ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", re.IGNORECASE),
    re.compile(r"\bthis is ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?) speaking", re.IGNORECASE),
]


def redact_text(text: str) -> str:
    """Apply all PII patterns to a string and return the redacted version."""
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = re.sub(pattern, replacement, result)
    for pattern in _NAME_PATTERNS:
        result = pattern.sub(lambda m: m.group(0).replace(m.group(1), "[CUSTOMER_NAME]"), result)
    return result


def redact_transcript_segments(segments: list[dict]) -> list[dict]:
    """Redact PII from transcript segment dicts in place and return them."""
    for seg in segments:
        seg["text"] = redact_text(seg["text"])
    return segments
