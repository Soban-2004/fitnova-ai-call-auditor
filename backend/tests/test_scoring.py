from app.services.scoring import compute_score


def test_matches_spec_worked_example():
    # FitNova_Implementation_Spec.md Section 9, Step 3.6 eyeballs this as
    # "base ~72 - 15 critical = 57", but that's approximate mental math, not
    # the exact weighted sum. Precise calculation:
    #   7*10*.25 + 8*10*.15 + 5*10*.15 + 9*10*.20 + 6*10*.15 + 7*10*.10
    #   = 17.5 + 12 + 7.5 + 18 + 9 + 7 = 71.0 (not 72)
    # 71.0 - 15 = 56 (not 57). Asserting the exact value, not the spec's
    # rounded approximation.
    dimensions = {
        "needs_discovery": {"score": 7},
        "product_knowledge": {"score": 8},
        "objection_handling": {"score": 5},
        "compliance": {"score": 9},
        "trial_booking": {"score": 6},
        "rapport_building": {"score": 7},
    }
    tags = [{"severity": "critical", "status": "open"}]
    result = compute_score(dimensions, tags)
    assert result.base_score == 71.0
    assert result.final_score == 56


def test_no_issues_no_deductions():
    dimensions = {name: {"score": 8} for name in [
        "needs_discovery", "product_knowledge", "objection_handling",
        "compliance", "trial_booking", "rapport_building",
    ]}
    result = compute_score(dimensions, [])
    assert result.deductions_total == 0
    assert result.final_score == 80


def test_dismissed_and_needs_review_tags_never_deduct():
    dimensions = {name: {"score": 8} for name in [
        "needs_discovery", "product_knowledge", "objection_handling",
        "compliance", "trial_booking", "rapport_building",
    ]}
    tags = [
        {"severity": "critical", "status": "dismissed"},
        {"severity": "critical", "status": "needs_review"},
        {"severity": "critical", "status": "contested"},
    ]
    result = compute_score(dimensions, tags)
    assert result.deductions_total == 0
    assert result.final_score == 80


def test_confirmed_tag_still_deducts():
    # "confirmed" means a human agreed the tag is valid — it stays a
    # deduction. Only status flips to 'open' -> deduct in scoring; the tag's
    # lifecycle state itself (open vs confirmed) both still count. See
    # services/scoring.py docstring.
    dimensions = {name: {"score": 8} for name in [
        "needs_discovery", "product_knowledge", "objection_handling",
        "compliance", "trial_booking", "rapport_building",
    ]}
    tags = [{"severity": "major", "status": "open"}]
    result = compute_score(dimensions, tags)
    assert result.deductions_total == 8
    assert result.final_score == 72


def test_score_never_goes_below_zero():
    dimensions = {name: {"score": 0} for name in [
        "needs_discovery", "product_knowledge", "objection_handling",
        "compliance", "trial_booking", "rapport_building",
    ]}
    tags = [{"severity": "critical", "status": "open"} for _ in range(10)]
    result = compute_score(dimensions, tags)
    assert result.final_score == 0


def test_repeated_tag_type_deducts_once_not_per_instance():
    # Real bug found via live testing: an advisor using 4 separate
    # pressure-selling lines produced 4 separate PRESSURE_SELLING tags,
    # stacking 4x15=60 deduction and flooring an otherwise-mediocre call to
    # 0. A recurring behavior should deduct once per call, not once per
    # utterance it appears in.
    dimensions = {name: {"score": 6} for name in [
        "needs_discovery", "product_knowledge", "objection_handling",
        "compliance", "trial_booking", "rapport_building",
    ]}
    tags = [
        {"tag_type": "PRESSURE_SELLING", "severity": "critical", "status": "open"},
        {"tag_type": "PRESSURE_SELLING", "severity": "critical", "status": "open"},
        {"tag_type": "PRESSURE_SELLING", "severity": "critical", "status": "open"},
        {"tag_type": "PRESSURE_SELLING", "severity": "critical", "status": "open"},
    ]
    result = compute_score(dimensions, tags)
    assert result.deductions_total == 15  # one critical, not four
    assert result.final_score == 45  # 60 base - 15, not floored to 0


def test_different_tag_types_each_still_deduct():
    dimensions = {name: {"score": 6} for name in [
        "needs_discovery", "product_knowledge", "objection_handling",
        "compliance", "trial_booking", "rapport_building",
    ]}
    tags = [
        {"tag_type": "PRESSURE_SELLING", "severity": "critical", "status": "open"},
        {"tag_type": "NO_NEEDS_DISCOVERY", "severity": "critical", "status": "open"},
        {"tag_type": "PRICE_BEFORE_VALUE", "severity": "major", "status": "open"},
    ]
    result = compute_score(dimensions, tags)
    assert result.deductions_total == 15 + 15 + 8


def test_missing_dimension_defaults_to_neutral_five():
    dimensions = {"needs_discovery": {"score": 10}}  # all others missing
    result = compute_score(dimensions, [])
    # 10*10*0.25 + 5*10*0.75 (defaults) = 25 + 37.5 = 62.5
    assert result.base_score == 62.5
