import json
from typing import List
from ..models import Fact, FactList
from ..llm.client import LLMClient
from ..prompts.figure_prompt import FIGURE_EXTRACTION_PROMPT

def extract_figure_facts(context: str, llm_client: LLMClient) -> List[Fact]:
    """
    Conservatively extracts facts from figure/chart contexts.
    Rejects noisy or disconnected OCR fragments without verified semantic links.
    """
    try:
        ctx_dict = json.loads(context)
    except Exception:
        ctx_dict = {}

    fallback_evidence_ids = ctx_dict.get("evidence_ids") or []
    element_id = ctx_dict.get("element_id")
    if element_id and element_id not in fallback_evidence_ids:
        fallback_evidence_ids.append(element_id)

    # If the figure has neither caption nor text fragments, skip immediately
    if not ctx_dict.get("figure_caption") and not ctx_dict.get("figure_text_fragments"):
        return []

    result: FactList = llm_client.extract_structured(
        prompt=FIGURE_EXTRACTION_PROMPT,
        context=context,
        schema=FactList
    )

    extracted_facts: List[Fact] = []
    if result and result.facts:
        for f in result.facts:
            # Conservative check: require confidence >= 0.5 for visual/figure claims
            if f.confidence >= 0.5:
                if not f.evidence_ids and fallback_evidence_ids:
                    f.evidence_ids = list(fallback_evidence_ids)
                extracted_facts.append(f)

    return extracted_facts
