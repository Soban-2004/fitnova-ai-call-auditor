from app.services.pii_redaction import redact_text, redact_transcript_segments


def test_redacts_indian_mobile():
    assert redact_text("Call me at 9876543210 anytime") == "Call me at [PHONE] anytime"


def test_redacts_mobile_with_country_code():
    assert "[PHONE]" in redact_text("reach me on +91 9876543210")


def test_redacts_email():
    assert redact_text("email me at test@gmail.com") == "email me at [EMAIL]"


def test_redacts_aadhaar():
    result = redact_text("my aadhaar is 1234 5678 9012")
    assert "[AADHAAR]" in result
    assert "1234" not in result


def test_redacts_pan():
    assert redact_text("PAN is ABCDE1234F") == "PAN is [PAN]"


def test_redacts_card_number():
    result = redact_text("card number 4111 1111 1111 1111 expires soon")
    assert "[CARD]" in result
    assert "4111" not in result


def test_redacts_customer_name_pattern():
    result = redact_text("Hi, my name is Rohan Verma, calling about the trial")
    assert "[CUSTOMER_NAME]" in result
    assert "Rohan" not in result


def test_leaves_ordinary_text_untouched():
    text = "I wanted to ask about the evening batch timings"
    assert redact_text(text) == text


def test_redact_transcript_segments_in_place():
    segments = [
        {"text": "Call me at 9876543210", "start_ts": 0.0, "end_ts": 2.0},
        {"text": "Sure, no problem", "start_ts": 2.0, "end_ts": 3.5},
    ]
    result = redact_transcript_segments(segments)
    assert result[0]["text"] == "Call me at [PHONE]"
    assert result[1]["text"] == "Sure, no problem"
    # mutated in place, same list returned
    assert result is segments
