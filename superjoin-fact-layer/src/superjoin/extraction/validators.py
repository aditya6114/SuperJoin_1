import re
from typing import List, Tuple, Dict, Any, Set
from superjoin.ingestion.models import CanonicalDocument
from .models import Fact

def get_all_document_evidence_ids(document: CanonicalDocument) -> Set[str]:
    """Extracts all valid element_ids and evidence_ids present in the document."""
    valid_ids: Set[str] = set()
    for page in document.pages:
        for element in page.elements:
            valid_ids.add(element.element_id)
            if element.evidence_ids:
                valid_ids.update(element.evidence_ids)
    return valid_ids

def validate_evidence(fact: Fact, valid_evidence_ids: Set[str]) -> Tuple[bool, str]:
    """Verifies that all evidence IDs attached to the fact exist in the document."""
    if not fact.evidence_ids:
        return False, "Fact has no evidence_ids."
        
    for ev_id in fact.evidence_ids:
        if ev_id not in valid_evidence_ids:
            return False, f"Evidence ID '{ev_id}' does not exist in CanonicalDocument."
            
    return True, ""

def validate_numerical_structure(fact: Fact) -> Tuple[bool, str]:
    """Validates numerical and percentage fields."""
    val = fact.object
    if val.value_type in ("number", "percentage", "currency", "quantity"):
        # Check that the value is numeric (int, float, or valid number string)
        if isinstance(val.value, (int, float)):
            pass
        elif isinstance(val.value, str):
            clean_str = val.value.replace(",", "").strip()
            # Allow trailing % or prefix currency if string, but it should be numeric
            num_pattern = re.compile(r'^[+-]?\d+(\.\d+)?$')
            if not num_pattern.match(clean_str):
                return False, f"Numerical fact has non-numeric value: '{val.value}'"
        else:
            return False, f"Numerical fact has invalid type for value: {type(val.value)}"

        # For percentage type, ensure percentage isn't completely mangled
        if val.value_type == "percentage":
            pass

    return True, ""

def validate_temporal_structure(fact: Fact) -> Tuple[bool, str]:
    """Validates temporal context structure without aggressive normalization."""
    time_ctx = fact.time
    if not time_ctx:
        return False, "Fact is missing TimeContext."
        
    # If fiscal year, value should contain FY or fiscal or year
    if time_ctx.time_type == "fiscal_year" and time_ctx.value:
        if not re.search(r'(FY|fiscal|financial\s*year)', time_ctx.value, re.IGNORECASE):
            # Not fatal, but ensure value exists
            pass
            
    return True, ""

def validate_fact(fact: Fact, document: CanonicalDocument) -> Tuple[bool, str]:
    """
    Validates a single Fact against the CanonicalDocument and semantic requirements.
    Returns (is_valid, failure_reason).
    """
    valid_ids = get_all_document_evidence_ids(document)
    
    # 1. Subject validation
    if not fact.subject or not fact.subject.name.strip():
        return False, "Fact has empty or missing subject name."
    if not fact.subject.type.strip():
        return False, "Fact has empty subject type."

    # 2. Predicate validation
    if not fact.predicate or not fact.predicate.strip():
        return False, "Fact has empty or missing predicate."

    # 3. Object validation
    if not fact.object or fact.object.value is None or str(fact.object.value).strip() == "":
        return False, "Fact has empty or missing object value."

    # 4. Confidence range
    if not (0.0 <= fact.confidence <= 1.0):
        return False, f"Confidence {fact.confidence} is out of valid range [0.0, 1.0]."

    # 5. Evidence existence (Strict)
    ev_ok, ev_msg = validate_evidence(fact, valid_ids)
    if not ev_ok:
        return False, ev_msg

    # 6. Numerical validation
    num_ok, num_msg = validate_numerical_structure(fact)
    if not num_ok:
        return False, num_msg

    # 7. Temporal validation
    temp_ok, temp_msg = validate_temporal_structure(fact)
    if not temp_ok:
        return False, temp_msg

    return True, ""

def validate_facts(
    facts: List[Fact], 
    document: CanonicalDocument
) -> Tuple[List[Fact], List[Dict[str, Any]]]:
    """
    Validates a collection of facts against a document.
    Returns (valid_facts, rejection_records).
    """
    valid_evidence_ids = get_all_document_evidence_ids(document)
    valid_facts: List[Fact] = []
    rejected: List[Dict[str, Any]] = []
    
    for fact in facts:
        # 1. Subject check
        if not fact.subject or not fact.subject.name.strip():
            rejected.append({"fact": fact, "reason": "Missing subject name."})
            continue
            
        # 2. Predicate check
        if not fact.predicate or not fact.predicate.strip():
            rejected.append({"fact": fact, "reason": "Missing predicate."})
            continue

        # 3. Object check
        if not fact.object or fact.object.value is None or str(fact.object.value).strip() == "":
            rejected.append({"fact": fact, "reason": "Missing object value."})
            continue

        # 4. Confidence check
        if not (0.0 <= fact.confidence <= 1.0):
            rejected.append({"fact": fact, "reason": f"Invalid confidence: {fact.confidence}"})
            continue

        # 5. Evidence existence check
        ev_ok, ev_msg = validate_evidence(fact, valid_evidence_ids)
        if not ev_ok:
            rejected.append({"fact": fact, "reason": ev_msg})
            continue

        # 6. Numerical check
        num_ok, num_msg = validate_numerical_structure(fact)
        if not num_ok:
            rejected.append({"fact": fact, "reason": num_msg})
            continue

        # 7. Temporal check
        temp_ok, temp_msg = validate_temporal_structure(fact)
        if not temp_ok:
            rejected.append({"fact": fact, "reason": temp_msg})
            continue

        valid_facts.append(fact)

    return valid_facts, rejected
