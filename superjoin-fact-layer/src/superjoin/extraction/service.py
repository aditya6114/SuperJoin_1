import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from superjoin.ingestion.models import (
    CanonicalDocument, 
    CanonicalTable, 
    CanonicalFigure
)
from .models import (
    Fact,
    FactExtractionResult,
    ExtractionFailure,
    ExtractionStatistics
)
from .candidate_selector import select_candidates
from .context_builder import build_context
from .extractors.text_extractor import extract_text_facts
from .extractors.table_extractor import extract_table_facts
from .extractors.figure_extractor import extract_figure_facts
from .validators import validate_facts
from .deduplicator import deduplicate_facts
from .llm.client import LLMClient
from .llm.provider import DefaultLLMProvider

class FactExtractionService:
    """
    Main entry point for extracting atomic, evidence-grounded facts from CanonicalDocuments.
    """
    
    def __init__(
        self, 
        llm_client: Optional[LLMClient] = None,
        output_dir: Optional[str] = "data/facts"
    ):
        self.llm_client = llm_client or DefaultLLMProvider()
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def _find_page_number_for_element(self, document: CanonicalDocument, element_id: str) -> int:
        for page in document.pages:
            if any(el.element_id == element_id for el in page.elements):
                return page.pdf_page_number
        return 1

    def save_result(self, result: FactExtractionResult) -> Path:
        """Persists the extraction result to JSON storage."""
        if not self.output_dir:
            raise ValueError("output_dir not configured for FactExtractionService.")
        output_file = self.output_dir / f"{result.document_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        return output_file

    def extract(self, document: CanonicalDocument) -> FactExtractionResult:
        """
        Executes the fact extraction pipeline:
        1. Candidate selection
        2. Context building
        3. Extractor routing (Text / Table / Figure)
        4. Structured LLM extraction
        5. Schema & evidence validation
        6. Local document deduplication
        7. Persistence & metrics computation
        """
        stats = ExtractionStatistics()
        failures: List[ExtractionFailure] = []
        warnings: List[str] = []
        raw_facts: List[Fact] = []
        uncertain_candidates: List[Dict[str, Any]] = []

        # 1. Candidate Selection
        candidates = select_candidates(document)
        stats.candidate_count = len(candidates)

        for cand in candidates:
            page_num = self._find_page_number_for_element(document, cand.element_id)
            
            # Count candidate by type
            if cand.type == "table":
                stats.table_candidate_count += 1
            elif cand.type in ("figure", "image"):
                stats.figure_candidate_count += 1
            else:
                stats.text_candidate_count += 1

            # 2. Context Building
            try:
                context = build_context(document, cand)
            except Exception as e:
                failures.append(ExtractionFailure(
                    document_id=document.metadata.document_id,
                    page_number=page_num,
                    candidate_id=cand.element_id,
                    element_id=cand.element_id,
                    reason=f"Failed to build context: {str(e)}"
                ))
                continue

            # 3 & 4. Route to Extractor & LLM Extraction
            try:
                if cand.type == "table":
                    cand_facts = extract_table_facts(context, self.llm_client)
                elif cand.type in ("figure", "image"):
                    cand_facts = extract_figure_facts(context, self.llm_client)
                else:
                    cand_facts = extract_text_facts(context, self.llm_client)

                if not cand_facts:
                    # Note potential uncertain candidate if no facts extracted
                    uncertain_candidates.append({
                        "element_id": cand.element_id,
                        "type": cand.type,
                        "page_number": page_num,
                        "reason": "No high-confidence structured claims found."
                    })
                else:
                    raw_facts.extend(cand_facts)

            except Exception as e:
                failures.append(ExtractionFailure(
                    document_id=document.metadata.document_id,
                    page_number=page_num,
                    candidate_id=cand.element_id,
                    element_id=cand.element_id,
                    reason=f"Extraction failure: {str(e)}"
                ))

        # 5. Schema & Evidence Validation
        valid_facts, rejection_records = validate_facts(raw_facts, document)
        stats.facts_extracted = len(raw_facts)
        stats.facts_rejected = len(rejection_records)
        stats.validation_failures = len(rejection_records)
        stats.facts_uncertain = len(uncertain_candidates)

        for rec in rejection_records:
            f = rec["fact"]
            first_eid = f.evidence_ids[0] if f.evidence_ids else "unknown"
            p_num = self._find_page_number_for_element(document, first_eid)
            failures.append(ExtractionFailure(
                document_id=document.metadata.document_id,
                page_number=p_num,
                candidate_id=first_eid,
                element_id=first_eid,
                reason=rec["reason"],
                details={"fact_id": f.fact_id, "predicate": f.predicate}
            ))

        # 6. Local Deduplication
        deduplicated = deduplicate_facts(valid_facts)

        result = FactExtractionResult(
            document_id=document.metadata.document_id,
            facts=deduplicated,
            uncertain_candidates=uncertain_candidates,
            failed_candidates=failures,
            warnings=warnings,
            statistics=stats
        )

        # 7. Persistence
        if self.output_dir:
            try:
                self.save_result(result)
            except Exception as e:
                warnings.append(f"Failed to persist fact extraction result: {str(e)}")

        return result
