from typing import Optional, Tuple
from .compatibility import ComparisonContext


class ContextualReconciliationEvaluator:
    """Evaluates whether differing facts are reconciled by context (time, scope, status, qualifiers, metric dimensions)."""

    def evaluate(self, ctx: ComparisonContext) -> Optional[Tuple[float, str, str]]:
        """Evaluate if the pair represents CONTEXTUALLY_RECONCILED.
        
        Returns (confidence, reason, explanation) if reconciled, else None.
        """
        # Prerequisites: must be about same entity or compatible predicates/transition
        if not ctx.is_same_entity:
            return None
        if not (ctx.is_same_predicate or ctx.is_status_transition):
            return None
        if not ctx.is_compatible_fact_type:
            return None

        base_conf = ctx.match.confidence
        if ctx.fact_a and ctx.fact_b:
            base_conf = min(ctx.fact_a.confidence, ctx.fact_b.confidence)

        subject = ctx.get_subject_name()
        predicate = ctx.get_predicate_name()
        val_a = ctx.get_val_a_str()
        val_b = ctx.get_val_b_str()
        time_a = ctx.get_time_a_str()
        time_b = ctx.get_time_b_str()
        scope_a = ctx.get_scope_a_str()
        scope_b = ctx.get_scope_b_str()

        # Case 1: Status Transition (e.g. Alice appointed CEO in 2021 vs resigned CEO in 2024)
        if ctx.is_status_transition:
            confidence = min(0.92, max(0.5, base_conf * 0.90))
            pred_a = ctx.fact_a.predicate if ctx.fact_a else "initial status"
            pred_b = ctx.fact_b.predicate if ctx.fact_b else "subsequent status"
            reason = "The statements describe different points in a status timeline and represent a status transition rather than a contradiction."
            explanation = (
                f"The statements describe different milestones in {subject}'s status timeline: "
                f"'{pred_a}' ({time_a}) and '{pred_b}' ({time_b}). This represents a valid status transition."
            )
            return round(confidence, 4), reason, explanation

        # Case 2: Different Reporting Periods (e.g. Revenue FY2023 vs FY2024)
        if ctx.is_different_time:
            confidence = min(0.94, max(0.5, base_conf * 0.92))
            reason = "The values differ because the facts describe different reporting periods."
            explanation = (
                f"The reported figures for {subject}'s {predicate} differ because they correspond to different reporting periods: "
                f"'{val_a}' in {time_a} versus '{val_b}' in {time_b}."
            )
            return round(confidence, 4), reason, explanation

        # Case 3: Overlapping or Contained Reporting Periods (e.g. Q4 vs FY, or calendar year vs fiscal year)
        if ctx.is_overlapping_or_contained_time:
            confidence = min(0.88, max(0.5, base_conf * 0.85))
            reason = "The figures reflect differing reporting durations or overlapping temporal periods."
            explanation = (
                f"The figures for {subject}'s {predicate} differ due to differing reporting interval lengths: "
                f"'{val_a}' ({time_a}) versus '{val_b}' ({time_b})."
            )
            return round(confidence, 4), reason, explanation

        # Case 4: Different Scope (e.g. Consolidated vs India Segment)
        if ctx.is_different_scope:
            confidence = min(0.92, max(0.5, base_conf * 0.90))
            reason = "The figures use different reporting scopes and are not directly contradictory."
            explanation = (
                f"The figures for {subject}'s {predicate} reflect different organizational or geographic scopes: "
                f"'{val_a}' ({scope_a}) versus '{val_b}' ({scope_b})."
            )
            return round(confidence, 4), reason, explanation

        # Case 5: Conflicting or Distinct Qualifiers (e.g. audited vs unaudited, pro forma vs reported, continuing operations)
        if ctx.signals.qualifiers == "different":
            confidence = min(0.85, max(0.5, base_conf * 0.82))
            reason = "The difference is explained by differing reporting qualifiers or accounting definitions."
            explanation = (
                f"The figures for {subject}'s {predicate} ({val_a} vs {val_b}) reflect differing qualifiers or accounting definitions."
            )
            return round(confidence, 4), reason, explanation

        # Case 6: Metric Dimension Divergence (Number vs Percentage) (Breakpoint 2)
        # E.g. total_income = 49114.06 (rupees) vs 13.5% (percentage growth / margin rate)
        if ctx.fact_a and ctx.fact_b and ctx.fact_a.object and ctx.fact_b.object:
            obj_a = ctx.fact_a.object
            obj_b = ctx.fact_b.object
            is_pct_a = obj_a.value_type == "percentage" or bool(obj_a.unit and "%" in obj_a.unit)
            is_pct_b = obj_b.value_type == "percentage" or bool(obj_b.unit and "%" in obj_b.unit)
            if is_pct_a != is_pct_b:
                confidence = min(0.86, max(0.5, base_conf * 0.82))
                reason = "The figures represent different metric dimensions (absolute figure vs percentage rate)."
                explanation = (
                    f"The reported figures for {subject}'s {predicate} differ because one fact reports an absolute amount "
                    f"('{val_a}') while the other reports a percentage ('{val_b}'). These reflect differing metric definitions rather than a direct contradiction."
                )
                return round(confidence, 4), reason, explanation

        return None
