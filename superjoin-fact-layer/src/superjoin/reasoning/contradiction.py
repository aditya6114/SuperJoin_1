from typing import Optional, Tuple
from .compatibility import ComparisonContext


class ContradictionEvaluator:
    """Evaluates whether two facts represent a genuine or likely contradiction."""

    def evaluate(self, ctx: ComparisonContext) -> Optional[Tuple[float, str, str]]:
        """Evaluate if the pair represents CONTRADICTS.
        
        Returns (confidence, reason, explanation) if contradictory, else None.
        """
        # 1. Fundamental prerequisites
        if not ctx.is_same_entity:
            return None
        if not ctx.is_same_predicate:
            return None
        if not ctx.is_compatible_fact_type:
            return None

        # 2. Context must be identical (not divergent and NOT unknown)
        # If time is unknown or different, it cannot safely be called a contradiction
        if not ctx.is_same_time:
            return None
        if not ctx.is_same_scope:
            return None

        # 3. Value must be materially different
        if not ctx.is_value_different:
            return None

        # 4. Check if a qualifier explains the difference
        if ctx.signals.qualifiers == "different" and "conflicting" in ctx.signals.qualifiers:
            # Qualifier divergence might explain it (e.g. audited vs estimated)
            return None

        base_conf = ctx.match.confidence
        if ctx.fact_a and ctx.fact_b:
            base_conf = min(ctx.fact_a.confidence, ctx.fact_b.confidence)

        subject = ctx.get_subject_name()
        predicate = ctx.get_predicate_name()
        val_a = ctx.get_val_a_str()
        val_b = ctx.get_val_b_str()
        time_str = ctx.get_time_a_str()
        scope_str = ctx.get_scope_a_str()

        confidence = min(0.96, max(0.5, base_conf * 0.94))
        reason = "Both facts refer to the same entity, metric, reporting period and scope, but report materially different values."
        explanation = (
            f"Both facts refer to {subject}'s {predicate} for {time_str} with {scope_str}, "
            f"but report mutually incompatible values: '{val_a}' versus '{val_b}'."
        )

        return round(confidence, 4), reason, explanation
