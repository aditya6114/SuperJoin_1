from typing import List, Optional
from .models import RelationshipResult, RelationshipType


class RelationshipValidationError(Exception):
    """Raised when a RelationshipResult violates integrity or validation rules."""
    pass


def validate_relationship_result(result: RelationshipResult) -> List[str]:
    """Validate a RelationshipResult for required fields, constraints, and data consistency.
    
    Returns a list of validation error/warning strings (empty if completely valid).
    Raises RelationshipValidationError if strict validation is desired.
    """
    errors: List[str] = []

    if not result.fact_a_id or not result.fact_b_id:
        errors.append("RelationshipResult must contain both fact_a_id and fact_b_id.")

    if result.fact_a_id == result.fact_b_id:
        errors.append("RelationshipResult cannot compare a fact with itself.")

    if not isinstance(result.relationship, RelationshipType):
        try:
            RelationshipType(result.relationship)
        except ValueError:
            errors.append(f"Invalid relationship type: {result.relationship}")

    if not (0.0 <= result.confidence <= 1.0):
        errors.append(f"Confidence {result.confidence} is out of bounds [0.0, 1.0].")

    if not result.reason or not result.reason.strip():
        errors.append("RelationshipResult must include a non-empty summary reason.")

    if not result.explanation or not result.explanation.strip():
        errors.append("RelationshipResult must include a non-empty human-readable explanation.")

    if not result.comparison:
        errors.append("RelationshipResult must preserve structured comparison signals.")

    if not result.evidence:
        errors.append("RelationshipResult must preserve provenance evidence references.")

    # Check evidence consistency against underlying facts if available
    if result.fact_a and result.fact_a.evidence_ids:
        for ev_id in result.evidence.fact_a_evidence:
            if ev_id not in result.fact_a.evidence_ids:
                errors.append(f"Evidence ID '{ev_id}' in RelationshipResult not found in Fact A evidence.")

    if result.fact_b and result.fact_b.evidence_ids:
        for ev_id in result.evidence.fact_b_evidence:
            if ev_id not in result.fact_b.evidence_ids:
                errors.append(f"Evidence ID '{ev_id}' in RelationshipResult not found in Fact B evidence.")

    return errors
