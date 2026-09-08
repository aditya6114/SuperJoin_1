from typing import List, Dict, Tuple
from .models import Fact

def _generate_fact_dedup_key(fact: Fact) -> Tuple:
    """
    Generates a conservative identity key for a Fact.
    Only facts with identical semantics, values, time, scope, and qualifiers are merged.
    """
    subj_name = fact.subject.name.strip().lower()
    subj_type = fact.subject.type.strip().lower()
    pred = fact.predicate.strip().lower()
    
    val_type = fact.object.value_type
    val_str = str(fact.object.value).strip().lower()
    val_unit = (fact.object.unit or "").strip().lower()
    val_curr = (fact.object.currency or "").strip().lower()
    val_scale = (fact.object.scale or "").strip().lower()
    val_qual = (fact.object.qualifier or "").strip().lower()
    
    t_type = fact.time.time_type
    t_val = (fact.time.value or "").strip().lower()
    
    scope = (fact.scope or "").strip().lower()
    qualifiers = tuple(sorted(q.strip().lower() for q in fact.qualifiers))
    
    return (
        subj_name,
        subj_type,
        pred,
        val_type,
        val_str,
        val_unit,
        val_curr,
        val_scale,
        val_qual,
        t_type,
        t_val,
        scope,
        qualifiers
    )

def deduplicate_facts(facts: List[Fact]) -> List[Fact]:
    """
    Performs conservative document-level deduplication of facts.
    When an identical claim appears in multiple locations (e.g. summary, table, paragraph),
    merges the evidence IDs into a single representative fact.
    Retains both facts if there is any semantic, temporal, scope, or qualifier difference.
    """
    dedup_map: Dict[Tuple, Fact] = {}
    ordered_keys: List[Tuple] = []

    for fact in facts:
        key = _generate_fact_dedup_key(fact)
        if key in dedup_map:
            existing = dedup_map[key]
            # Merge evidence IDs while preserving order and uniqueness
            merged_ids = list(existing.evidence_ids)
            for eid in fact.evidence_ids:
                if eid not in merged_ids:
                    merged_ids.append(eid)
            existing.evidence_ids = merged_ids
            # Keep highest confidence
            existing.confidence = max(existing.confidence, fact.confidence)
        else:
            # Create a copy so mutations don't affect original
            fact_copy = fact.model_copy(deep=True)
            dedup_map[key] = fact_copy
            ordered_keys.append(key)

    return [dedup_map[k] for k in ordered_keys]
