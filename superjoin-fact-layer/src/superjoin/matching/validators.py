from typing import List, Tuple
from .models import MatchResult, CandidatePair, MatchClassification


class MatchValidationError(Exception):
    """Raised when a match result or candidate violates schema or consistency rules."""
    pass


def validate_candidate_pair(candidate: CandidatePair) -> None:
    """Validate candidate pair integrity."""
    if not candidate.fact_a_id or not candidate.fact_b_id:
        raise MatchValidationError("Candidate pair must contain both fact_a_id and fact_b_id.")
    if candidate.fact_a_id == candidate.fact_b_id:
        raise MatchValidationError("Candidate pair cannot compare a fact with itself.")


def validate_match_result(result: MatchResult) -> List[str]:
    """Validate a MatchResult for required fields, consistency, and constraints.
    Returns a list of validation warning/error strings (empty if valid).
    """
    errors: List[str] = []

    if not result.fact_a_id or not result.fact_b_id:
        errors.append("MatchResult missing fact_a_id or fact_b_id.")

    if result.fact_a_id == result.fact_b_id:
        errors.append("MatchResult cannot compare a fact with itself.")

    if not isinstance(result.classification, MatchClassification):
        try:
            MatchClassification(result.classification)
        except ValueError:
            errors.append(f"Invalid classification: {result.classification}")

    if not (0.0 <= result.confidence <= 1.0):
        errors.append(f"Confidence {result.confidence} out of range [0.0, 1.0].")

    if not result.reasons:
        errors.append("MatchResult must include explainable reasons.")

    if not result.signals:
        errors.append("MatchResult must include structured comparison signals.")

    return errors
