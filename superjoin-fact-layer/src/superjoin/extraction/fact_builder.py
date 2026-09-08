from typing import List, Optional, Union
from .models import Fact, FactSubject, FactObject, TemporalContext

def build_fact(
    subject: Union[FactSubject, str],
    predicate: str,
    object_val: Union[FactObject, int, float, str],
    evidence_ids: List[str],
    confidence: float = 0.90,
    time: Optional[TemporalContext] = None,
    scope: Optional[str] = None,
    qualifiers: Optional[List[str]] = None,
    fact_type: Optional[str] = None,
    subject_type: str = "entity"
) -> Fact:
    """
    Composes extracted components into a strongly-typed, validated Fact representation.
    """
    # 1. Normalize subject
    if isinstance(subject, str):
        fact_subject = FactSubject(name=subject.strip(), type=subject_type)
    else:
        fact_subject = subject

    # 2. Normalize object
    if isinstance(object_val, FactObject):
        fact_object = object_val
    elif isinstance(object_val, (int, float)):
        fact_object = FactObject(value_type="number", value=object_val)
    else:
        fact_object = FactObject(value_type="text", value=str(object_val).strip())

    # 3. Determine fact_type if not explicitly provided
    if not fact_type:
        if fact_object.value_type in ("number", "currency", "percentage", "quantity"):
            fact_type = "numerical"
        elif predicate in ("appointed_as", "resigned_as", "acquired", "launched"):
            fact_type = "event"
        elif predicate in ("operates", "owns", "located_at", "serves", "provides"):
            fact_type = "relationship"
        else:
            fact_type = "attribute"

    # 4. Normalize time
    temporal_ctx = time if time is not None else TemporalContext(time_type="unknown")

    # 5. Normalize qualifiers
    quals = list(qualifiers) if qualifiers else []
    if fact_object.qualifier and fact_object.qualifier not in quals:
        # Include object comparison qualifier if not already present
        quals.append(fact_object.qualifier)

    # 6. Build and return Fact
    return Fact(
        fact_type=fact_type,  # type: ignore
        subject=fact_subject,
        predicate=predicate.strip().lower(),
        object=fact_object,
        time=temporal_ctx,
        scope=scope,
        qualifiers=quals,
        confidence=max(0.0, min(1.0, confidence)),
        evidence_ids=list(evidence_ids) if evidence_ids else []
    )
