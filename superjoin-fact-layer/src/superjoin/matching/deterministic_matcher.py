from typing import List, Tuple, Optional
from superjoin.extraction.models import Fact
from .models import (
    CandidatePair,
    MatchSignals,
    MatchResult,
    MatchClassification
)
from .index import normalize_key
from .candidate_generator import (
    GENERIC_UNCERTAIN_SUBJECTS,
    COMPATIBLE_PREDICATES,
    are_fact_types_compatible
)
from .value_comparator import ValueComparator, ValueComparisonResult
from .temporal_comparator import TemporalComparator, TemporalComparisonResult

STATUS_TRANSITION_PAIRS = {
    ("appointed", "resigned"),
    ("joined", "left"),
    ("started", "ended"),
    ("opened", "closed"),
    ("appointed_ceo", "resigned_ceo"),
}


def compare_scopes(scope_a: Optional[str], scope_b: Optional[str]) -> Tuple[str, str]:
    """Compare scopes: returns (status, explanation)."""
    norm_a = normalize_key(scope_a)
    norm_b = normalize_key(scope_b)

    if not norm_a and not norm_b:
        return "same", "Both facts have default/unspecified scope."
    if norm_a == norm_b:
        return "same", f"Identical reporting scope: '{scope_a}'"
    if not norm_a or not norm_b:
        specified = scope_a or scope_b
        return "different", f"Scope asymmetry: one fact is specified as '{specified}' while the other is unspecified."
    return "different", f"Different reporting scopes: '{scope_a}' vs '{scope_b}'"


def compare_qualifiers(
    qual_a: List[str],
    qual_b: List[str],
    val_status: str
) -> Tuple[str, str]:
    """Compare semantic qualifiers between two facts."""
    set_a = {normalize_key(q) for q in qual_a if q}
    set_b = {normalize_key(q) for q in qual_b if q}

    if not set_a and not set_b:
        return "exact", "No qualifiers on either fact."
    if set_a == set_b:
        return "exact", f"Identical qualifiers: {list(set_a)}"

    # Check for conflicting accounting or audit states
    audit_conflicts = (
        ("audited" in set_a and "unaudited" in set_b) or
        ("unaudited" in set_a and "audited" in set_b) or
        ("estimated" in set_a and "audited" in set_b) or
        ("audited" in set_a and "estimated" in set_b)
    )
    if audit_conflicts:
        return "different", f"Conflicting audit/certainty qualifiers: {list(set_a)} vs {list(set_b)}"

    if "approximate" in set_a or "approximate" in set_b or "approximately" in set_a or "approximately" in set_b:
        if val_status in {"compatible", "equivalent", "equal"}:
            return "compatible", "Compatible approximate qualifiers."

    return "different", f"Differing qualifiers: {list(set_a)} vs {list(set_b)}"


class DeterministicMatcher:
    """Compares candidate pairs across structured dimensions to classify factual relationships."""

    def __init__(
        self,
        value_comparator: Optional[ValueComparator] = None,
        temporal_comparator: Optional[TemporalComparator] = None
    ):
        self.value_comparator = value_comparator or ValueComparator()
        self.temporal_comparator = temporal_comparator or TemporalComparator()

    def compare(self, fact_a: Fact, fact_b: Fact, candidate: Optional[CandidatePair] = None) -> MatchResult:
        """Perform comprehensive deterministic comparison of two facts."""
        reasons: List[str] = []

        # 1. Subject comparison
        subj_a = fact_a.subject.name if fact_a.subject else ""
        subj_b = fact_b.subject.name if fact_b.subject else ""
        norm_subj_a = normalize_key(subj_a)
        norm_subj_b = normalize_key(subj_b)

        is_uncertain_a = not norm_subj_a or norm_subj_a in GENERIC_UNCERTAIN_SUBJECTS
        is_uncertain_b = not norm_subj_b or norm_subj_b in GENERIC_UNCERTAIN_SUBJECTS

        is_same_doc = bool(candidate and candidate.document_a_id and candidate.document_a_id == candidate.document_b_id)

        if norm_subj_a == norm_subj_b and is_same_doc:
            subj_signal = "exact"
            reasons.append(f"Same subject within document: '{subj_a}'")
        elif is_uncertain_a or is_uncertain_b:
            subj_signal = "unknown"
            reasons.append(f"Subject unresolved or pronoun: '{subj_a}' vs '{subj_b}'")
        elif norm_subj_a == norm_subj_b:
            subj_signal = "exact"
            reasons.append(f"Same subject: '{subj_a}'")
        elif norm_subj_a.replace(" limited", "").replace(" ltd", "").strip() == norm_subj_b.replace(" limited", "").replace(" ltd", "").strip():
            subj_signal = "alias"
            reasons.append(f"Subject canonical alias: '{subj_a}' == '{subj_b}'")
        else:
            subj_signal = "different"
            reasons.append(f"Different subjects: '{subj_a}' vs '{subj_b}'")

        # 2. Predicate comparison
        pred_a = fact_a.predicate
        pred_b = fact_b.predicate
        norm_pred_a = normalize_key(pred_a)
        norm_pred_b = normalize_key(pred_b)

        if not norm_pred_a or not norm_pred_b:
            pred_signal = "unknown"
            reasons.append("Missing predicate on one or both facts.")
        elif norm_pred_a == norm_pred_b:
            pred_signal = "exact"
            reasons.append(f"Same predicate: '{pred_a}'")
        elif norm_pred_b in COMPATIBLE_PREDICATES.get(norm_pred_a, set()) or norm_pred_a in COMPATIBLE_PREDICATES.get(norm_pred_b, set()):
            pred_signal = "compatible"
            reasons.append(f"Compatible predicates: '{pred_a}' ~ '{pred_b}'")
        else:
            # Check for status transition pairs (e.g. appointed vs resigned)
            pair_key = (norm_pred_a, norm_pred_b)
            rev_pair_key = (norm_pred_b, norm_pred_a)
            if pair_key in STATUS_TRANSITION_PAIRS or rev_pair_key in STATUS_TRANSITION_PAIRS:
                pred_signal = "compatible"
                reasons.append(f"Status transition predicates: '{pred_a}' and '{pred_b}'")
            else:
                pred_signal = "different"
                reasons.append(f"Different predicates: '{pred_a}' vs '{pred_b}'")

        # 3. Fact Type comparison
        type_compat = are_fact_types_compatible(fact_a, fact_b)
        type_signal = "compatible" if type_compat else "incompatible"
        if not type_compat:
            reasons.append(f"Incompatible fact types: '{fact_a.fact_type}' vs '{fact_b.fact_type}'")

        # 4. Temporal comparison
        temp_res: TemporalComparisonResult = self.temporal_comparator.compare(fact_a.time, fact_b.time)
        time_signal = temp_res.status
        reasons.append(f"Time comparison ({time_signal}): {temp_res.details}")

        # 5. Scope comparison
        scope_signal, scope_details = compare_scopes(fact_a.scope, fact_b.scope)
        reasons.append(f"Scope comparison ({scope_signal}): {scope_details}")

        # 6. Value comparison
        val_res: ValueComparisonResult = self.value_comparator.compare(
            fact_a.object,
            fact_b.object,
            fact_a.qualifiers,
            fact_b.qualifiers
        )
        val_signal = val_res.value_status
        unit_signal = val_res.unit_status
        reasons.append(f"Value comparison ({val_signal}): {val_res.details}")

        # 7. Qualifier comparison
        qual_signal, qual_details = compare_qualifiers(
            fact_a.qualifiers,
            fact_b.qualifiers,
            val_signal
        )
        reasons.append(f"Qualifier comparison ({qual_signal}): {qual_details}")

        signals = MatchSignals(
            subject=subj_signal,
            predicate=pred_signal,
            fact_type=type_signal,
            value=val_signal,
            unit=unit_signal,
            time=time_signal,
            scope=scope_signal,
            qualifiers=qual_signal
        )

        # Classification Logic
        classification, confidence = self._classify(
            signals=signals,
            fact_a=fact_a,
            fact_b=fact_b
        )

        doc_a_id = candidate.document_a_id if candidate else None
        doc_b_id = candidate.document_b_id if candidate else None

        return MatchResult(
            fact_a_id=fact_a.fact_id,
            fact_b_id=fact_b.fact_id,
            document_a_id=doc_a_id,
            document_b_id=doc_b_id,
            classification=classification,
            confidence=round(confidence, 4),
            signals=signals,
            reasons=reasons,
            fact_a=fact_a,
            fact_b=fact_b
        )

    def _classify(
        self,
        signals: MatchSignals,
        fact_a: Fact,
        fact_b: Fact
    ) -> Tuple[MatchClassification, float]:
        """Apply conservative deterministic rules to categorize the match."""
        # 1. Unambiguous non-match: different entities or incompatible types or different predicates
        if signals.subject == "different" or signals.predicate == "different" or signals.fact_type == "incompatible":
            return MatchClassification.NOT_MATCH, 1.0

        # 2. Uncertain subject or predicate
        if signals.subject == "unknown" or signals.predicate == "unknown":
            return MatchClassification.UNCERTAIN, 0.50

        base_conf = min(fact_a.confidence, fact_b.confidence)

        # 3. Status transition check (e.g. appointed CEO vs resigned CEO)
        norm_pred_a = normalize_key(fact_a.predicate)
        norm_pred_b = normalize_key(fact_b.predicate)
        is_status_transition = (
            (norm_pred_a, norm_pred_b) in STATUS_TRANSITION_PAIRS or
            (norm_pred_b, norm_pred_a) in STATUS_TRANSITION_PAIRS
        )
        if is_status_transition:
            return MatchClassification.RELATED_CLAIM, base_conf * 0.90

        # 4. Same subject and same/compatible predicate
        # Check if context dimensions differ (time, scope, audit qualifiers)
        is_context_divergent = (
            signals.time == "different" or
            signals.time in {"contained", "overlapping"} or
            signals.scope == "different" or
            (signals.qualifiers == "different" and "conflicting" in signals.qualifiers)
        )

        if is_context_divergent:
            # Different time period (FY2023 vs FY2024), different scope (Consolidated vs India segment) -> RELATED_CLAIM
            return MatchClassification.RELATED_CLAIM, base_conf * 0.88

        # 5. Same context (same time or both unknown, same scope):
        # Section 15 Requirement:
        # Same subject + same predicate + same time + same scope
        # If value is equal/equivalent -> SAME_CLAIM (corroboration candidate downstream)
        # If value is compatible (bounds/approx) -> SAME_CLAIM
        # If value is DIFFERENT -> STILL SAME_CLAIM! (contradiction candidate downstream for Module 5)
        if signals.value in {"equal", "equivalent"}:
            return MatchClassification.SAME_CLAIM, base_conf * 0.98
        elif signals.value == "compatible":
            return MatchClassification.SAME_CLAIM, base_conf * 0.92
        elif signals.value == "different":
            # Section 15: Same claim propositions with conflicting values
            return MatchClassification.SAME_CLAIM, base_conf * 0.90
        else:
            # Unknown value comparison
            return MatchClassification.SAME_CLAIM, base_conf * 0.75
