import json
from typing import List
from ..models import Fact, FactList
from ..llm.client import LLMClient
from ..prompts.table_prompt import TABLE_EXTRACTION_PROMPT

def extract_table_facts(context: str, llm_client: LLMClient) -> List[Fact]:
    """
    Extracts atomic, evidence-grounded facts from table context using an LLM.
    Preserves row/column intersections, unit/currency inheritance, and temporal scope.
    """
    try:
        ctx_dict = json.loads(context)
    except Exception:
        ctx_dict = {}

    fallback_evidence_ids = ctx_dict.get("evidence_ids") or []
    element_id = ctx_dict.get("element_id")
    if element_id and element_id not in fallback_evidence_ids:
        fallback_evidence_ids.append(element_id)

    # Call LLM with table-specific prompt
    result: FactList = llm_client.extract_structured(
        prompt=TABLE_EXTRACTION_PROMPT,
        context=context,
        schema=FactList
    )

    extracted_facts: List[Fact] = []
    if result and result.facts:
        for f in result.facts:
            if not f.evidence_ids and fallback_evidence_ids:
                f.evidence_ids = list(fallback_evidence_ids)
            extracted_facts.append(f)

    return extracted_facts
