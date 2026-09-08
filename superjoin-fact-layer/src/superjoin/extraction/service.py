import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from superjoin.ingestion.models import CanonicalDocument
from .models import (
    Fact,
    FactExtractionResult,
    ExtractionFailure,
    ExtractionStatistics
)
from .candidate_selector import select_candidates
from .context_builder import build_context, build_context_dict
from .extractors.text_extractor import extract_text_facts, extract_text_facts_deterministic
from .extractors.table_extractor import extract_table_facts, extract_table_facts_deterministic
from .extractors.figure_extractor import extract_figure_facts, extract_figure_facts_deterministic
from .validators import validate_facts
from .deduplicator import deduplicate_facts
from .llm.client import LLMClient

class FactExtractionService:
    """
    Main orchestration service for extracting atomic, evidence-grounded facts
    from CanonicalDocuments using a hybrid extraction architecture.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        llm_enabled: bool = True,
        output_dir: Optional[str] = "data/facts"
    ):
        self.llm_client = llm_client
        self.llm_enabled = llm_enabled and (llm_client is not None)
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
        Executes the hybrid fact extraction pipeline:
        1. Select candidates via deterministic signals
        2. Build localized context
        3. Run deterministic extraction (Table / Text / Figure)
        4. LLM enhancement (only if ambiguous/complex and LLM is enabled)
        5. Validate schema and evidence against CanonicalDocument
        6. Deduplicate facts conservatively
        7. Compute statistics and persist
        """
        doc_id = document.metadata.document_id if document.metadata else document.document_id
        stats = ExtractionStatistics()
        failures: List[ExtractionFailure] = []
        warnings: List[str] = []
        raw_facts: List[Fact] = []
        uncertain_candidates: List[Dict[str, Any]] = []

        # 1. Candidate Selection
        candidates = select_candidates(document)
        stats.candidate_count = len(candidates)

        active_llm = self.llm_client if self.llm_enabled else None

        for cand in candidates:
            page_num = self._find_page_number_for_element(document, cand.element_id)

            if cand.type == "table":
                stats.table_candidate_count += 1
            elif cand.type in ("figure", "image"):
                stats.figure_candidate_count += 1
            else:
                stats.text_candidate_count += 1

            # 2. Context Building
            try:
                context_str = build_context(document, cand)
                context_dict = build_context_dict(document, cand)
            except Exception as e:
                failures.append(ExtractionFailure(
                    document_id=doc_id,
                    page_number=page_num,
                    candidate_id=cand.element_id,
                    element_id=cand.element_id,
                    reason=f"Failed to build context: {str(e)}"
                ))
                continue

            # 3 & 4. Hybrid Extraction (Deterministic first, LLM fallback if needed)
            try:
                cand_facts: List[Fact] = []
                is_ambiguous: bool = False

                if cand.type == "table":
                    det_facts, is_ambiguous = extract_table_facts_deterministic(context_dict)
                    if det_facts and not is_ambiguous:
                        cand_facts = det_facts
                    elif active_llm is not None:
                        cand_facts = extract_table_facts(context_str, active_llm)
                    elif is_ambiguous:
                        uncertain_candidates.append({
                            "element_id": cand.element_id,
                            "type": "table",
                            "page_number": page_num,
                            "reason": "Ambiguous table column or header structure."
                        })

                elif cand.type in ("figure", "image"):
                    det_facts, is_ambiguous = extract_figure_facts_deterministic(context_dict)
                    if det_facts and not is_ambiguous:
                        cand_facts = det_facts
                    elif active_llm is not None:
                        cand_facts = extract_figure_facts(context_str, active_llm)
                    else:
                        uncertain_candidates.append({
                            "element_id": cand.element_id,
                            "type": cand.type,
                            "page_number": page_num,
                            "reason": "Figure lacks clear deterministic semantic grounding."
                        })

                else:
                    # Text candidate
                    det_facts, uncertainties = extract_text_facts_deterministic(context_dict)
                    if det_facts:
                        cand_facts = det_facts
                    elif active_llm is not None:
                        cand_facts = extract_text_facts(context_str, active_llm)
                    elif uncertainties:
                        for u in uncertainties:
                            uncertain_candidates.append({
                                "element_id": cand.element_id,
                                "type": cand.type,
                                "page_number": page_num,
                                "reason": u
                            })
                    else:
                        uncertain_candidates.append({
                            "element_id": cand.element_id,
                            "type": cand.type,
                            "page_number": page_num,
                            "reason": "No high-confidence structured claims found."
                        })

                if cand_facts:
                    raw_facts.extend(cand_facts)

            except Exception as e:
                failures.append(ExtractionFailure(
                    document_id=doc_id,
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
                document_id=doc_id,
                page_number=p_num,
                candidate_id=first_eid,
                element_id=first_eid,
                reason=rec["reason"],
                details={"fact_id": f.fact_id, "predicate": f.predicate}
            ))

        # 6. Local Deduplication
        deduplicated = deduplicate_facts(valid_facts)

        result = FactExtractionResult(
            document_id=doc_id,
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
