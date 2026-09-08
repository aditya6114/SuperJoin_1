import json
from typing import List, Optional, Tuple, Dict, Any
from ..models import Fact, FactSubject, FactObject, TemporalContext
from .semantic_extractor import extract_semantic_relations
from .numerical_extractor import extract_quantities
from .temporal_extractor import extract_temporal_context
from ..rules.qualifiers import extract_qualifiers
from ..fact_builder import build_fact

def extract_text_facts_deterministic(
    context_dict: Dict[str, Any]
) -> Tuple[List[Fact], List[str]]:
    """
    Deterministically extracts facts from text content using rule-based
    semantic, numerical, and temporal extractors.
    Returns (facts, uncertainties).
    """
    content = context_dict.get("content") or ""
    if not content.strip():
        return [], []

    evidence_ids = context_dict.get("evidence_ids") or []
    element_id = context_dict.get("element_id")
    if element_id and element_id not in evidence_ids:
        evidence_ids.append(element_id)

    relations, uncertainties = extract_semantic_relations(content, context_dict)
    facts: List[Fact] = []

    for rel in relations:
        fact = build_fact(
            subject=rel["subject"],
            predicate=rel["predicate"],
            object_val=rel["object"],
            time=rel["time"],
            qualifiers=rel.get("qualifiers", []),
            evidence_ids=evidence_ids,
            confidence=rel.get("confidence", 0.90),
            fact_type=rel.get("fact_type")
        )
        facts.append(fact)

    return facts, uncertainties

def extract_text_facts(context: str, llm_client: Any = None) -> List[Fact]:
    """
    Extracts atomic, evidence-grounded facts from text context using hybrid extraction:
    1. Deterministic NLP extraction (numerical + temporal + semantic)
    2. If no deterministic facts found or complex/ambiguous, and LLM is enabled, use LLM
    """
    try:
        ctx_dict = json.loads(context)
    except Exception:
        ctx_dict = {}

    fallback_evidence_ids = ctx_dict.get("evidence_ids") or []
    element_id = ctx_dict.get("element_id")
    if element_id and element_id not in fallback_evidence_ids:
        fallback_evidence_ids.append(element_id)

    # 1. Deterministic extraction
    det_facts, uncertainties = extract_text_facts_deterministic(ctx_dict)
    if det_facts:
        return det_facts

    # 2. If no deterministic facts found and LLM is available, call LLM
    if llm_client is not None:
        try:
            from ..llm.extractor import extract_with_llm
            llm_facts = extract_with_llm(context, mode="text", client=llm_client)
            if llm_facts:
                for f in llm_facts:
                    if not f.evidence_ids and fallback_evidence_ids:
                        f.evidence_ids = list(fallback_evidence_ids)
                return llm_facts
        except Exception:
            return []

    return []
