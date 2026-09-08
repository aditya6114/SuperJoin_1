from typing import Optional, Tuple
from .compatibility import ComparisonContext


def are_value_dimensions_compatible(ctx: ComparisonContext) -> bool:
    """Verify value dimensional compatibility before declaring contradiction.
    
    Number vs Number: compatible (e.g. ₹500 Cr vs ₹600 Cr, 1320.19 vs 242).
    Percentage vs Percentage: compatible (e.g. 5% vs 8%).
    Number vs Percentage: INCOMPATIBLE (e.g. 49,114.06 vs 13.5%).
    """
    if not ctx.fact_a or not ctx.fact_b or not ctx.fact_a.object or not ctx.fact_b.object:
        return ctx.signals.fact_type == "compatible"

    obj_a = ctx.fact_a.object
    obj_b = ctx.fact_b.object

    is_pct_a = obj_a.value_type == "percentage" or bool(obj_a.unit and "%" in obj_a.unit)
    is_pct_b = obj_b.value_type == "percentage" or bool(obj_b.unit and "%" in obj_b.unit)

    if is_pct_a != is_pct_b:
        return False

    return True


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

        # 2. Scope must be the same (not different)
        if not ctx.is_same_scope:
            return None

        # 3. Time handling:
        # Case B: Explicitly different time -> do NOT classify as contradiction (belongs to contextual reconciliation)
        if ctx.is_different_time:
            return None

        # Overlapping or contained periods (e.g. Q4 vs FY) indicate differing reporting duration -> reconciliation
        if ctx.is_overlapping_or_contained_time:
            return None

        # 4. Value must be materially different
        if not ctx.is_value_different:
            return None

        # 5. Value Dimensional Compatibility (Breakpoint 2):
        # Do NOT treat number-vs-percentage as a normal numeric contradiction!
        # E.g. total_income = 49114.06 vs 13.5% must not blindly become CONTRADICTS.
        if not are_value_dimensions_compatible(ctx):
            return None

        # 6. Check if a qualifier explains the difference
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

        independence_prefix = (
            "Internal document contradiction"
            if ctx.source_independence == "same_document"
            else "Contradiction across sources"
        )

        # Case A: Same explicit time period
        if ctx.is_same_time:
            confidence = min(0.96, max(0.5, base_conf * 0.94))
            reason = "Both facts refer to the same entity, metric, reporting period and scope, but report materially different values."
            explanation = (
                f"{independence_prefix}: both facts refer to {subject}'s {predicate} for {time_str} with {scope_str}, "
                f"but report mutually incompatible values: '{val_a}' versus '{val_b}'."
            )
            return round(confidence, 4), reason, explanation

        # Case C: Unknown time on otherwise strong same claim
        # When subject, predicate, and scope are same, and values are materially different numbers,
        # but time is unspecified, classify as contradiction with somewhat lower confidence.
        confidence = min(0.88, max(0.5, base_conf * 0.82))
        reason = "Both facts refer to the same entity, metric and scope with materially different values, though reporting period is unspecified."
        explanation = (
            f"{independence_prefix}: both facts describe {subject}'s {predicate} with {scope_str}, "
            f"but report conflicting values: '{val_a}' versus '{val_b}' (reporting period is unspecified for one or both facts)."
        )
        return round(confidence, 4), reason, explanation
