from typing import List, Dict, Set, Tuple, Optional
from superjoin.extraction.models import Fact
from .models import CandidatePair
from .index import FactIndex, normalize_key, IndexedFact

# Generic references where entity identity is ungrounded or ambiguous
GENERIC_UNCERTAIN_SUBJECTS: Set[str] = {
    "it", "its", "they", "them", "we", "us", "our company",
    "the company", "company", "this company", "which we",
    "the following table", "he", "she"
}

# Controlled predicate compatibility map (conservative)
COMPATIBLE_PREDICATES: Dict[str, Set[str]] = {
    "revenue": {"total_revenue", "revenue_from_operations"},
    "total_revenue": {"revenue", "revenue_from_operations"},
    "revenue_from_operations": {"revenue", "total_revenue"},
    "employee_count": {"workforce", "employees", "total_employees"},
    "workforce": {"employee_count", "employees", "total_employees"},
    "employees": {"employee_count", "workforce", "total_employees"},
    "operates": {"fulfilment_centres", "facilities"},
}


def are_fact_types_compatible(fact_a: Fact, fact_b: Fact) -> bool:
    """Determine if two facts have compatible factual/value types for comparison."""
    if fact_a.fact_type == fact_b.fact_type:
        return True

    # Numeric types
    numeric_types = {"number", "percentage", "currency", "quantity"}
    val_a_type = getattr(fact_a.object, "value_type", None)
    val_b_type = getattr(fact_b.object, "value_type", None)

    if val_a_type in numeric_types and val_b_type in numeric_types:
        return True

    # Textual / entity types
    text_types = {"text", "entity"}
    if val_a_type in text_types and val_b_type in text_types:
        return True

    # Attribute and semantic can be compatible if values align
    if {fact_a.fact_type, fact_b.fact_type} <= {"attribute", "semantic"}:
        return True

    return False


def are_predicates_compatible(pred_a: str, pred_b: str) -> Tuple[bool, str]:
    """Check predicate relationship: (compatible, signal) -> exact, compatible, or different."""
    norm_a = normalize_key(pred_a)
    norm_b = normalize_key(pred_b)
    if norm_a == norm_b:
        return True, "exact"

    if norm_b in COMPATIBLE_PREDICATES.get(norm_a, set()) or norm_a in COMPATIBLE_PREDICATES.get(norm_b, set()):
        return True, "compatible"

    return False, "different"


def are_subjects_compatible(subj_a: str, subj_b: str) -> Tuple[bool, str]:
    """Check subject relationship: (compatible, signal) -> exact, alias, uncertain, or different."""
    norm_a = normalize_key(subj_a)
    norm_b = normalize_key(subj_b)

    if not norm_a or not norm_b or norm_a in GENERIC_UNCERTAIN_SUBJECTS or norm_b in GENERIC_UNCERTAIN_SUBJECTS:
        return True, "uncertain"

    if norm_a == norm_b:
        return True, "exact"

    # Conservative alias checking (e.g. 'delhivery' and 'delhivery limited')
    if norm_a.replace(" limited", "").replace(" ltd", "").strip() == norm_b.replace(" limited", "").replace(" ltd", "").strip():
        return True, "alias"

    return False, "different"


class CandidateGenerator:
    """Generates candidate pairs from FactIndex using blocking strategies to avoid O(N^2)."""

    def __init__(
        self,
        cross_document_only: bool = True,
        allow_uncertain_subject: bool = True
    ):
        self.cross_document_only = cross_document_only
        self.allow_uncertain_subject = allow_uncertain_subject

    def generate_candidates(self, index: FactIndex) -> List[CandidatePair]:
        """Generate candidate pairs using multi-pass blocking across index keys."""
        pairs: List[CandidatePair] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        def add_candidate(idx_a: IndexedFact, idx_b: IndexedFact, subj_signal: str, pred_signal: str):
            if idx_a.fact.fact_id == idx_b.fact.fact_id:
                return

            if self.cross_document_only and idx_a.document_id == idx_b.document_id:
                return

            # Canonical order
            id_a, id_b = idx_a.fact.fact_id, idx_b.fact.fact_id
            canon_key = (min(id_a, id_b), max(id_a, id_b))
            if canon_key in seen_pairs:
                return

            if not are_fact_types_compatible(idx_a.fact, idx_b.fact):
                return

            seen_pairs.add(canon_key)
            pairs.append(CandidatePair(
                fact_a_id=id_a,
                fact_b_id=id_b,
                document_a_id=idx_a.document_id,
                document_b_id=idx_b.document_id,
                signals={
                    "subject": subj_signal,
                    "predicate": pred_signal,
                    "fact_type": "compatible"
                }
            ))

        # Pass 1: Exact (subject, predicate) blocks
        for (subj, pred) in index.subject_predicate_keys():
            if self.cross_document_only and subj in GENERIC_UNCERTAIN_SUBJECTS:
                continue

            facts_in_block = index.indexed_by_subject_predicate(subj, pred)
            n = len(facts_in_block)
            for i in range(n):
                for j in range(i + 1, n):
                    is_same_doc = facts_in_block[i].document_id == facts_in_block[j].document_id
                    subj_sig = "exact" if (subj not in GENERIC_UNCERTAIN_SUBJECTS or is_same_doc) else "uncertain"
                    add_candidate(facts_in_block[i], facts_in_block[j], subj_sig, "exact")

        # Pass 2: Same subject, compatible predicates
        for subj in index.subjects():
            if subj in GENERIC_UNCERTAIN_SUBJECTS:
                continue

            subj_facts = index.indexed_by_subject(subj)
            n = len(subj_facts)
            for i in range(n):
                for j in range(i + 1, n):
                    f_a = subj_facts[i]
                    f_b = subj_facts[j]
                    if f_a.normalized_predicate == f_b.normalized_predicate:
                        continue  # already covered in Pass 1
                    is_compat, pred_sig = are_predicates_compatible(f_a.normalized_predicate, f_b.normalized_predicate)
                    if is_compat:
                        add_candidate(f_a, f_b, "exact", pred_sig)

        # Pass 3: Uncertain / pronoun subjects with matching/compatible predicates
        if self.allow_uncertain_subject:
            for pred in index.predicates():
                pred_facts = index.indexed_by_predicate(pred)
                uncertain_facts = [
                    f for f in pred_facts
                    if not f.normalized_subject or f.normalized_subject in GENERIC_UNCERTAIN_SUBJECTS
                ]
                other_facts = [
                    f for f in pred_facts
                    if f.normalized_subject and f.normalized_subject not in GENERIC_UNCERTAIN_SUBJECTS
                ]

                # Pair uncertain with known entities across documents
                for u_fact in uncertain_facts:
                    for o_fact in other_facts:
                        add_candidate(u_fact, o_fact, "uncertain", "exact")

                # Also pair uncertain with uncertain across documents
                u_n = len(uncertain_facts)
                for i in range(u_n):
                    for j in range(i + 1, u_n):
                        add_candidate(uncertain_facts[i], uncertain_facts[j], "uncertain", "exact")

        return pairs
