import pytest
from superjoin.matching.models import CandidatePair, MatchResult, MatchSignals, MatchClassification
from superjoin.matching.validators import validate_candidate_pair, validate_match_result, MatchValidationError


def test_candidate_pair_validation():
    valid = CandidatePair(fact_a_id="F1", fact_b_id="F2")
    validate_candidate_pair(valid)

    invalid_same = CandidatePair(fact_a_id="F1", fact_b_id="F1")
    with pytest.raises(MatchValidationError):
        validate_candidate_pair(invalid_same)

    invalid_empty = CandidatePair(fact_a_id="", fact_b_id="F2")
    with pytest.raises(MatchValidationError):
        validate_candidate_pair(invalid_empty)


def test_match_result_validation():
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="equal",
        unit="same",
        time="same",
        scope="same",
        qualifiers="exact"
    )
    valid_res = MatchResult(
        fact_a_id="F1",
        fact_b_id="F2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.95,
        signals=signals,
        reasons=["Same subject", "Same predicate"]
    )
    errors = validate_match_result(valid_res)
    assert len(errors) == 0

    # Invalid: same fact ID
    invalid_res = MatchResult(
        fact_a_id="F1",
        fact_b_id="F1",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.95,
        signals=signals,
        reasons=["reason"]
    )
    errors = validate_match_result(invalid_res)
    assert any("cannot compare a fact with itself" in e for e in errors)
