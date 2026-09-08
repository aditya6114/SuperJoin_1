import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Union

from superjoin.extraction.models import Fact, FactExtractionResult
from superjoin.matching.models import MatchingSessionResult, MatchResult, MatchClassification
from .models import (
    RelationshipType,
    RelationshipResult,
    RelationshipStatistics,
    RelationshipSessionResult,
    ProvenanceEvidence,
)
from .compatibility import ComparisonContext
from .corroboration import CorroborationEvaluator
from .contradiction import ContradictionEvaluator
from .reconciliation import ContextualReconciliationEvaluator
from .semantic_reasoner import SemanticReasoner
from .validators import validate_relationship_result, RelationshipValidationError


class RelationshipReasoningService:
    """End-to-end orchestrator for determining semantic relationships and conflicts between facts."""

    def __init__(
        self,
        corroboration_evaluator: Optional[CorroborationEvaluator] = None,
        contradiction_evaluator: Optional[ContradictionEvaluator] = None,
        reconciliation_evaluator: Optional[ContextualReconciliationEvaluator] = None,
        semantic_reasoner: Optional[SemanticReasoner] = None,
        output_dir: Optional[Union[str, Path]] = "data/relationships",
        use_llm: bool = False,
    ):
        self.corroboration_evaluator = corroboration_evaluator or CorroborationEvaluator()
        self.contradiction_evaluator = contradiction_evaluator or ContradictionEvaluator()
        self.reconciliation_evaluator = reconciliation_evaluator or ContextualReconciliationEvaluator()
        self.semantic_reasoner = semantic_reasoner or SemanticReasoner(enabled=use_llm)
        self.output_dir = Path(output_dir) if output_dir else Path("data/relationships")
        self.use_llm = use_llm

    def load_matches_from_file(self, file_path: Union[str, Path]) -> MatchingSessionResult:
        """Load MatchingSessionResult from a JSON file."""
        p = Path(file_path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return MatchingSessionResult.model_validate(data)

    def load_facts_from_dir(self, dir_path: Union[str, Path]) -> Dict[str, Fact]:
        """Load all facts from JSON files in a directory into a lookup dict keyed by fact_id."""
        p = Path(dir_path)
        facts_map: Dict[str, Fact] = {}
        if not p.exists():
            return facts_map

        json_files = sorted(list(p.glob("*.json"))) if p.is_dir() else [p]
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                res = FactExtractionResult.model_validate(data)
                for f in res.facts:
                    facts_map[f.fact_id] = f
            except Exception:
                continue
        return facts_map

    def reason_match(
        self,
        match: MatchResult,
        fact_a: Optional[Fact] = None,
        fact_b: Optional[Fact] = None,
    ) -> RelationshipResult:
        """Deterministically determine the semantic relationship for a single MatchResult."""
        f_a = fact_a or match.fact_a
        f_b = fact_b or match.fact_b
        ctx = ComparisonContext(match=match, fact_a=f_a, fact_b=f_b)

        relationship: RelationshipType
        confidence: float
        reason: str
        explanation: str

        # 1. Unrelated claims (different entities, different predicates, or incompatible fact types)
        if (
            match.classification == MatchClassification.NOT_MATCH
            or ctx.is_different_entity
            or ctx.is_different_predicate
            or not ctx.is_compatible_fact_type
        ):
            relationship = RelationshipType.UNRELATED
            confidence = 0.98
            reason = "The facts describe different entities, predicates, or incompatible fact types."
            explanation = (
                f"Fact A concerns {ctx.get_subject_name()} ({ctx.get_predicate_name()}) "
                f"while Fact B concerns a different entity or unrelated metric. They do not describe comparable claims."
            )

        # 2. Unresolved / ambiguous subject (e.g. pronoun 'It', unknown entity, or UNCERTAIN match)
        elif ctx.is_unknown_entity or match.classification == MatchClassification.UNCERTAIN:
            relationship = RelationshipType.UNRESOLVED
            confidence = 0.50
            subj_a = f_a.subject.name if f_a and f_a.subject else "Fact A"
            subj_b = f_b.subject.name if f_b and f_b.subject else "Fact B"
            reason = "The subject is unresolved or generic, preventing safe entity attribution."
            explanation = (
                f"The subject of one or both statements is unresolved ('{subj_a}' vs '{subj_b}'). "
                f"The system cannot safely establish that both statements refer to the same entity."
            )

        else:
            # 3. Check Corroboration (value = equivalent or compatible)
            corroboration = self.corroboration_evaluator.evaluate(ctx)
            if corroboration:
                confidence, reason, explanation = corroboration
                relationship = RelationshipType.CORROBORATES

            else:
                # 4. Check Contextual Reconciliation (explicit time, scope, status, qualifiers, metric divergence)
                reconciliation = self.reconciliation_evaluator.evaluate(ctx)
                if reconciliation:
                    confidence, reason, explanation = reconciliation
                    relationship = RelationshipType.CONTEXTUALLY_RECONCILED

                else:
                    # 5. Check Contradiction (same period or unknown period with strong same-claim identity)
                    contradiction = self.contradiction_evaluator.evaluate(ctx)
                    if contradiction:
                        confidence, reason, explanation = contradiction
                        relationship = RelationshipType.CONTRADICTS

                    # 6. Differing values with inadequate context / missing evidence (Breakpoint 3)
                    elif ctx.is_value_different:
                        relationship = RelationshipType.UNRESOLVED
                        confidence = 0.55
                        reason = "The values differ, but available evidence does not establish sufficient reporting context."
                        explanation = (
                            f"Fact A reports '{ctx.get_val_a_str()}' ({ctx.get_time_a_str()}, {ctx.get_scope_a_str()}) "
                            f"while Fact B reports '{ctx.get_val_b_str()}' ({ctx.get_time_b_str()}, {ctx.get_scope_b_str()}). "
                            f"Because contextual scope or temporal definitions are insufficient to establish direct conflict, "
                            f"the system treats this as unresolved."
                        )

                    # 7. Fallback / Optional LLM reasoning
                    else:
                        if self.use_llm and self.semantic_reasoner.is_available() and f_a and f_b:
                            llm_res = self.semantic_reasoner.reason(f_a, f_b, ctx)
                            if llm_res:
                                relationship = llm_res.relationship
                                confidence = llm_res.confidence
                                reason = llm_res.reason
                                explanation = llm_res.explanation
                            else:
                                relationship = RelationshipType.UNRESOLVED
                                confidence = 0.50
                                reason = "Insufficient evidence to safely determine relationship."
                                explanation = "Available signals are insufficient to conclusively establish corroboration, contradiction, or contextual reconciliation."
                        else:
                            relationship = RelationshipType.UNRESOLVED
                            confidence = 0.50
                            reason = "Insufficient evidence to safely determine relationship."
                            explanation = "Available signals are insufficient to conclusively establish corroboration, contradiction, or contextual reconciliation."

        # Extract provenance evidence
        ev_a = f_a.evidence_ids if f_a else []
        ev_b = f_b.evidence_ids if f_b else []
        evidence = ProvenanceEvidence(
            fact_a_evidence=list(ev_a),
            fact_b_evidence=list(ev_b)
        )

        result = RelationshipResult(
            fact_a_id=match.fact_a_id,
            fact_b_id=match.fact_b_id,
            document_a_id=match.document_a_id,
            document_b_id=match.document_b_id,
            relationship=relationship,
            confidence=round(confidence, 4),
            reason=reason,
            explanation=explanation,
            comparison=ctx.to_comparison_signals(),
            evidence=evidence,
            source_independence=ctx.source_independence,
            fact_a=f_a,
            fact_b=f_b,
            metadata=dict(match.metadata),
        )

        validation_errors = validate_relationship_result(result)
        if validation_errors:
            raise RelationshipValidationError(f"Validation failed for relationship: {validation_errors}")

        return result

    def reason_matches(
        self,
        matches: List[MatchResult],
        facts_map: Optional[Dict[str, Fact]] = None,
    ) -> RelationshipSessionResult:
        """Execute relationship reasoning across a list of MatchResults."""
        start_time = time.perf_counter()
        facts_map = facts_map or {}

        relationships: List[RelationshipResult] = []
        stats = RelationshipStatistics(total_pairs=len(matches))
        total_conf = 0.0

        for m in matches:
            f_a = m.fact_a or facts_map.get(m.fact_a_id)
            f_b = m.fact_b or facts_map.get(m.fact_b_id)

            rel_res = self.reason_match(m, fact_a=f_a, fact_b=f_b)
            relationships.append(rel_res)

            total_conf += rel_res.confidence
            if rel_res.relationship == RelationshipType.CORROBORATES:
                stats.corroborates += 1
            elif rel_res.relationship == RelationshipType.CONTRADICTS:
                stats.contradicts += 1
            elif rel_res.relationship == RelationshipType.CONTEXTUALLY_RECONCILED:
                stats.contextually_reconciled += 1
            elif rel_res.relationship == RelationshipType.UNRELATED:
                stats.unrelated += 1
            elif rel_res.relationship == RelationshipType.UNRESOLVED:
                stats.unresolved += 1

            if rel_res.source_independence == "cross_document":
                stats.cross_document_count += 1
            else:
                stats.same_document_count += 1

        if matches:
            stats.average_confidence = round(total_conf / len(matches), 4)
        stats.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return RelationshipSessionResult(
            relationships=relationships,
            statistics=stats,
        )

    def reason_session(
        self,
        match_session: MatchingSessionResult,
        facts_map: Optional[Dict[str, Fact]] = None,
    ) -> RelationshipSessionResult:
        """Execute relationship reasoning over an entire MatchingSessionResult."""
        return self.reason_matches(match_session.matches, facts_map=facts_map)

    def save_results(
        self,
        session_result: RelationshipSessionResult,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Persist relationship session results to JSON."""
        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            out_file = self.output_dir / "relationships_session.json"

        data = session_result.model_dump(mode="json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out_file
