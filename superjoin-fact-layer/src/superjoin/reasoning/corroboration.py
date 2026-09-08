from typing import Optional, Tuple
from .compatibility import ComparisonContext


class CorroborationEvaluator:
    """Evaluates whether two facts corroborate each other deterministically."""

    def evaluate(self, ctx: ComparisonContext) -> Optional[Tuple[float, str, str]]:
        """Evaluate if the pair represents CORROBORATES.
        
        Returns (confidence, reason, explanation) if corroborating, else None.
        """
        # 1. Fundamental prerequisites
        if not ctx.is_same_entity:
            return None
        if not ctx.is_same_predicate:
            return None
        if not ctx.is_compatible_fact_type:
            return None

        # 2. Context must not be divergent
        if ctx.is_different_time or ctx.is_different_scope:
            return None

        # 3. Qualifiers must not be in conflict
        if ctx.signals.qualifiers == "different" and "conflicting" in ctx.signals.qualifiers:
            return None

        # 4. Value agreement check
        if not ctx.is_value_agreeing:
            return None

        # Base confidence from underlying facts/match
        base_conf = ctx.match.confidence
        if ctx.fact_a and ctx.fact_b:
            base_conf = min(ctx.fact_a.confidence, ctx.fact_b.confidence)

        subject = ctx.get_subject_name()
        predicate = ctx.get_predicate_name()
        val_a = ctx.get_val_a_str()
        val_b = ctx.get_val_b_str()
        time_str = ctx.get_time_a_str()
        scope_str = ctx.get_scope_a_str()

        independence_clause = (
            "Cross-document corroboration confirmed across independent sources."
            if ctx.source_independence == "cross_document"
            else "Internal corroboration confirmed within the same source document."
        )

        # 5. Distinguish unit conversion, approximate bounds, and exact equality
        if ctx.signals.value == "equivalent" or ctx.signals.unit == "converted":
            confidence = min(0.98, max(0.5, base_conf * 0.96))
            reason = "Both facts describe the same claim for the same period and report numerically equivalent values after unit conversion."
            explanation = (
                f"Both facts describe {subject}'s {predicate} for {time_str} ({scope_str}) "
                f"with reported values '{val_a}' and '{val_b}', which are numerically equivalent after converting units. "
                f"{independence_clause}"
            )
            return round(confidence, 4), reason, explanation

        if ctx.signals.value == "compatible":
            confidence = min(0.95, max(0.5, base_conf * 0.90))
            reason = "Both facts describe the same claim with compatible values within supported approximation tolerance or bounds."
            explanation = (
                f"Both facts describe {subject}'s {predicate} for {time_str} ({scope_str}) "
                f"with reported values '{val_a}' and '{val_b}', which are compatible within supported bounds or approximation tolerance. "
                f"{independence_clause}"
            )
            return round(confidence, 4), reason, explanation

        if ctx.signals.value == "equal":
            confidence = min(0.99, max(0.5, base_conf * 0.98))
            reason = "Both facts make the same claim in identical context and report matching values."
            explanation = (
                f"Both facts state that {subject}'s {predicate} for {time_str} ({scope_str}) is '{val_a}'. "
                f"{independence_clause}"
            )
            return round(confidence, 4), reason, explanation

        # Fallback for semantic / assertion matches
        confidence = min(0.92, max(0.5, base_conf * 0.88))
        reason = "Both facts assert consistent information for the same entity and predicate."
        explanation = (
            f"Both facts assert that {subject} has {predicate} '{val_a}' for {time_str} ({scope_str}). "
            f"{independence_clause}"
        )
        return round(confidence, 4), reason, explanation
