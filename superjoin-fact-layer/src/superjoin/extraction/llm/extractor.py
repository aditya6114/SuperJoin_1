import json
from typing import List, Optional
from ..models import Fact, FactList
from .client import LLMClient
from .prompts import (
    TEXT_EXTRACTION_PROMPT,
    TABLE_EXTRACTION_PROMPT,
    FIGURE_EXTRACTION_PROMPT,
)

def extract_with_llm(
    context: str, 
    mode: str, 
    client: LLMClient
) -> List[Fact]:
    """
    Given an extraction context and mode ('text', 'table', 'figure'),
    invokes the LLM client with appropriate prompts and returns structured Fact objects.
    """
    # Parse context to determine fallback evidence IDs
    try:
        ctx_dict = json.loads(context)
    except Exception:
        ctx_dict = {}

    fallback_evidence_ids = ctx_dict.get("evidence_ids") or []
    element_id = ctx_dict.get("element_id")
    if element_id and element_id not in fallback_evidence_ids:
        fallback_evidence_ids.append(element_id)

    # Select prompt by mode
    if mode == "table":
        prompt = TABLE_EXTRACTION_PROMPT
    elif mode == "figure":
        prompt = FIGURE_EXTRACTION_PROMPT
    else:
        prompt = TEXT_EXTRACTION_PROMPT

    result: FactList = client.extract_structured(
        prompt=prompt,
        context=context,
        schema=FactList
    )

    extracted_facts: List[Fact] = []
    if result and getattr(result, "facts", None):
        for f in result.facts:
            # Enforce evidence IDs grounding if omitted by LLM
            if not f.evidence_ids and fallback_evidence_ids:
                f.evidence_ids = list(fallback_evidence_ids)
            extracted_facts.append(f)

    return extracted_facts
