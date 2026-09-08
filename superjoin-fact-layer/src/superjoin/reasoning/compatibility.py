from typing import Optional, List, Dict, Any, Tuple
from superjoin.extraction.models import Fact
from superjoin.matching.models import MatchResult, MatchSignals
from .models import ComparisonSignals

STATUS_TRANSITION_PAIRS = {
    ("appointed", "resigned"),
    ("joined", "left"),
    ("started", "ended"),
    ("opened", "closed"),
    ("appointed_ceo", "resigned_ceo"),
    ("acquired", "divested"),
    ("launched", "closed"),
}


def normalize_key(val: Optional[str]) -> str:
    """Normalize a string key for deterministic comparison."""
    if not val:
        return ""
    import re
    return re.sub(r"[\s_-]+", "_", val.strip().lower())


def format_fact_value(fact: Optional[Fact]) -> str:
    """Format a human-readable display string of a fact's value, unit, and qualifiers."""
    if not fact or not fact.object:
        return "unspecified"
    obj = fact.object
    curr = f"{obj.currency} " if obj.currency else ""
    unit = f" {obj.unit}" if obj.unit else ""
    scale = f" {obj.scale}" if obj.scale else ""
    qual = f"{obj.qualifier} " if obj.qualifier else ""
    val = f"{obj.value}"
    return f"{qual}{curr}{val}{unit}{scale}".strip()


def format_fact_time(fact: Optional[Fact]) -> str:
    """Format a human-readable representation of a fact's temporal context."""
    if not fact or not fact.time:
        return "unspecified period"
    t = fact.time
    if t.value:
        return t.value
    if t.start_date and t.end_date:
        return f"{t.start_date} to {t.end_date}"
    if t.start_date:
        return f"from {t.start_date}"
    if t.end_date:
        return f"until {t.end_date}"
    return "unspecified period"


def format_fact_scope(fact: Optional[Fact]) -> str:
    """Format a human-readable representation of a fact's scope."""
    if not fact or not fact.scope:
        return "default scope"
    return fact.scope


class ComparisonContext:
    """Encapsulates and evaluates the multi-dimensional comparison between two facts."""

    def __init__(
        self,
        match: MatchResult,
        fact_a: Optional[Fact] = None,
        fact_b: Optional[Fact] = None,
    ):
        self.match = match
        self.fact_a = fact_a or match.fact_a
        self.fact_b = fact_b or match.fact_b
        self.signals = match.signals

        self.doc_a_id = match.document_a_id or (self.fact_a.fact_id.split(":")[0] if self.fact_a and ":" in self.fact_a.fact_id else None)
        self.doc_b_id = match.document_b_id or (self.fact_b.fact_id.split(":")[0] if self.fact_b and ":" in self.fact_b.fact_id else None)

        self.source_independence = (
            "same_document"
            if self.doc_a_id and self.doc_b_id and self.doc_a_id == self.doc_b_id
            else "cross_document"
        )

        self._evaluate_status()

    def _evaluate_status(self) -> None:
        """Evaluate semantic transition and status signals."""
        pred_a = normalize_key(self.fact_a.predicate if self.fact_a else "")
        pred_b = normalize_key(self.fact_b.predicate if self.fact_b else "")

        if (pred_a, pred_b) in STATUS_TRANSITION_PAIRS or (pred_b, pred_a) in STATUS_TRANSITION_PAIRS:
            self.status = "status_transition"
        else:
            self.status = None

    @property
    def is_same_entity(self) -> bool:
        return self.signals.subject in {"exact", "alias"}

    @property
    def is_different_entity(self) -> bool:
        return self.signals.subject == "different"

    @property
    def is_unknown_entity(self) -> bool:
        return self.signals.subject == "unknown"

    @property
    def is_same_predicate(self) -> bool:
        return self.signals.predicate in {"exact", "compatible"} and not self.is_status_transition

    @property
    def is_status_transition(self) -> bool:
        return self.status == "status_transition"

    @property
    def is_different_predicate(self) -> bool:
        return self.signals.predicate == "different"

    @property
    def is_unknown_predicate(self) -> bool:
        return self.signals.predicate == "unknown"

    @property
    def is_compatible_fact_type(self) -> bool:
        return self.signals.fact_type == "compatible"

    @property
    def is_same_time(self) -> bool:
        return self.signals.time == "same"

    @property
    def is_different_time(self) -> bool:
        return self.signals.time == "different"

    @property
    def is_overlapping_or_contained_time(self) -> bool:
        return self.signals.time in {"overlapping", "contained"}

    @property
    def is_unknown_time(self) -> bool:
        return self.signals.time == "unknown"

    @property
    def is_same_scope(self) -> bool:
        return self.signals.scope == "same"

    @property
    def is_different_scope(self) -> bool:
        return self.signals.scope == "different"

    @property
    def is_unknown_scope(self) -> bool:
        return self.signals.scope == "unknown"

    @property
    def is_value_agreeing(self) -> bool:
        return self.signals.value in {"equal", "equivalent", "compatible"}

    @property
    def is_value_different(self) -> bool:
        return self.signals.value == "different"

    @property
    def is_value_unknown(self) -> bool:
        return self.signals.value in {"unknown", "not_applicable"}

    @property
    def has_qualifier_divergence(self) -> bool:
        return self.signals.qualifiers == "different"

    def to_comparison_signals(self) -> ComparisonSignals:
        """Convert internal signals to public ComparisonSignals model."""
        return ComparisonSignals(
            subject=self.signals.subject,
            predicate=self.signals.predicate,
            fact_type=self.signals.fact_type,
            value=self.signals.value,
            unit=self.signals.unit,
            time=self.signals.time,
            scope=self.signals.scope,
            qualifiers=self.signals.qualifiers,
            status=self.status,
        )

    def get_subject_name(self) -> str:
        """Get best subject name representation."""
        if self.fact_a and self.fact_a.subject and self.fact_a.subject.name:
            return self.fact_a.subject.name
        if self.fact_b and self.fact_b.subject and self.fact_b.subject.name:
            return self.fact_b.subject.name
        return "the entity"

    def get_predicate_name(self) -> str:
        """Get best predicate name representation."""
        if self.fact_a and self.fact_a.predicate:
            return self.fact_a.predicate
        if self.fact_b and self.fact_b.predicate:
            return self.fact_b.predicate
        return "claim"

    def get_val_a_str(self) -> str:
        return format_fact_value(self.fact_a)

    def get_val_b_str(self) -> str:
        return format_fact_value(self.fact_b)

    def get_time_a_str(self) -> str:
        return format_fact_time(self.fact_a)

    def get_time_b_str(self) -> str:
        return format_fact_time(self.fact_b)

    def get_scope_a_str(self) -> str:
        return format_fact_scope(self.fact_a)

    def get_scope_b_str(self) -> str:
        return format_fact_scope(self.fact_b)
