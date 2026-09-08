import json
from typing import List, Tuple
from ..models import Fact, FactList, Subject, FactValue, TimeContext
from ..llm.client import LLMClient
from ..prompts.text_prompt import TEXT_EXTRACTION_PROMPT

def extract_text_facts(context: str, llm_client: LLMClient) -> List[Fact]:
    """
    Extracts atomic, evidence-grounded facts from text context using an LLM.
    """
    # Parse context JSON to get element and evidence IDs for fallback grounding
    try:
        ctx_dict = json.loads(context)
    except Exception:
        ctx_dict = {}
        
    fallback_evidence_ids = ctx_dict.get("evidence_ids") or []
    element_id = ctx_dict.get("element_id")
    if element_id and element_id not in fallback_evidence_ids:
        fallback_evidence_ids.append(element_id)

    # Call LLM
    result: FactList = llm_client.extract_structured(
        prompt=TEXT_EXTRACTION_PROMPT,
        context=context,
        schema=FactList
    )
    
    extracted_facts: List[Fact] = []
    if result and result.facts:
        for f in result.facts:
            # Enforce evidence grounding: if LLM omitted evidence_ids, attach element evidence
            if not f.evidence_ids and fallback_evidence_ids:
                f.evidence_ids = list(fallback_evidence_ids)
            extracted_facts.append(f)
            
    return extracted_facts
