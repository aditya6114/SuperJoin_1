import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set

from superjoin.ingestion.service import DocumentIngestionService
from superjoin.ingestion.validator import validate_pdf
from superjoin.extraction.service import FactExtractionService
from superjoin.extraction.models import Fact, FactExtractionResult
from superjoin.matching.service import FactMatchingService
from superjoin.matching.models import MatchingSessionResult
from superjoin.reasoning.service import RelationshipReasoningService
from superjoin.reasoning.models import (
    RelationshipSessionResult,
    RelationshipResult,
    RelationshipType
)

STOP_WORDS = {
    "the", "in", "of", "and", "a", "an", "for", "to", "was", "is", "are",
    "by", "at", "on", "with", "from", "as", "that", "it", "its", "what",
    "how", "many", "there", "were", "or", "which", "who", "whom", "this",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "about", "any", "all", "some"
}

SEMANTIC_SYNONYMS: Dict[str, List[str]] = {
    "financial": ["revenue", "profit", "loss", "ebitda", "equity_share_capital", "income", "turnover", "capex"],
    "metrics": ["revenue", "profit", "growth", "volume", "shipments", "facilities", "centres", "equity_share_capital"],
    "metric": ["revenue", "profit", "growth", "volume", "shipments", "facilities", "centres", "equity_share_capital"],
    "capital": ["equity_share_capital"],
    "shares": ["equity_share_capital"],
    "share": ["equity_share_capital"],
    "equity": ["equity_share_capital"],
    "earnings": ["revenue", "ebitda", "profit"],
    "operational": ["fulfilment_centres", "express_parcel_shipments", "pincodes", "facilities", "vehicles"],
    "centres": ["fulfilment_centres", "delivery_centres"],
    "shipments": ["express_parcel_shipments", "part_truckload_volume"],
}


class KnowledgeLayerApplication:
    """
    Lightweight orchestration service coordinating Ingestion, Extraction,
    Matching, and Reasoning pipelines and providing read-access to the knowledge layer.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        ingestion_service: Optional[DocumentIngestionService] = None,
        extraction_service: Optional[FactExtractionService] = None,
        matching_service: Optional[FactMatchingService] = None,
        reasoning_service: Optional[RelationshipReasoningService] = None,
    ):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent.parent
        else:
            self.base_dir = Path(base_dir)

        self.input_dir = self.base_dir / "data" / "input"
        self.parsed_dir = self.base_dir / "data" / "parsed"
        self.facts_dir = self.base_dir / "data" / "facts"
        self.matches_dir = self.base_dir / "data" / "matches"
        self.relationships_dir = self.base_dir / "data" / "relationships"

        for d in [self.input_dir, self.parsed_dir, self.facts_dir, self.matches_dir, self.relationships_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.ingestion_service = ingestion_service or DocumentIngestionService()
        self.extraction_service = extraction_service or FactExtractionService(
            llm_client=None,
            llm_enabled=False,
            output_dir=str(self.facts_dir)
        )
        self.matching_service = matching_service or FactMatchingService(
            output_dir=self.matches_dir
        )
        self.reasoning_service = reasoning_service or RelationshipReasoningService(
            output_dir=self.relationships_dir,
            use_llm=False
        )

        self._doc_evidence_cache: Dict[str, Dict[str, Tuple[int, Optional[str]]]] = {}
        self._facts_cache: Optional[Dict[str, Tuple[str, Fact]]] = None
        self._relationships_cache: Optional[List[RelationshipResult]] = None

    def invalidate_caches(self):
        """Clears in-memory caches when new documents are ingested."""
        self._doc_evidence_cache.clear()
        self._facts_cache = None
        self._relationships_cache = None

    def get_document_evidence_map(self, document_id: str) -> Dict[str, Tuple[int, Optional[str]]]:
        """Builds lookup index from element_id/evidence_id to (page_number, text)."""
        if document_id in self._doc_evidence_cache:
            return self._doc_evidence_cache[document_id]

        parsed_file = self.parsed_dir / f"{document_id}.json"
        index: Dict[str, Tuple[int, Optional[str]]] = {}

        if parsed_file.exists():
            try:
                with open(parsed_file, "r", encoding="utf-8") as f:
                    doc_data = json.load(f)
                pages = doc_data.get("pages", [])
                for page in pages:
                    p_num = page.get("pdf_page_number", 1)
                    for el in page.get("elements", []):
                        el_id = el.get("element_id")
                        content = el.get("content") or el.get("caption")
                        if el_id:
                            index[el_id] = (p_num, content)
                        for ev_id in el.get("evidence_ids", []):
                            index[ev_id] = (p_num, content)
            except Exception:
                pass

        self._doc_evidence_cache[document_id] = index
        return index

    def resolve_evidence(self, document_id: str, evidence_ids: List[str]) -> List[Dict[str, Any]]:
        """Resolves raw evidence IDs into structured details with page number and text where available."""
        index = self.get_document_evidence_map(document_id)
        resolved = []

        for eid in evidence_ids:
            if eid in index:
                page_num, text = index[eid]
                resolved.append({
                    "evidence_id": eid,
                    "page": page_num,
                    "text": text
                })
            else:
                match = re.search(r":p(\d+):", eid)
                page_num = int(match.group(1)) if match else None
                resolved.append({
                    "evidence_id": eid,
                    "page": page_num,
                    "text": None
                })

        return resolved

    def process_document(self, pdf_path: Path) -> Dict[str, Any]:
        """Executes end-to-end processing pipeline for a PDF document."""
        validate_pdf(pdf_path)

        # 1. Ingestion
        canonical_doc = self.ingestion_service.ingest(pdf_path)
        self.ingestion_service.save(canonical_doc, self.parsed_dir)
        doc_id = canonical_doc.metadata.document_id

        # 2. Fact Extraction
        extraction_result = self.extraction_service.extract(canonical_doc)
        self.extraction_service.save_result(extraction_result)

        # 3. Matching
        all_extractions = self.matching_service.load_from_dir(self.facts_dir)
        match_session = self.matching_service.match(all_extractions)
        self.matching_service.save_results(match_session, filename="matches_session.json")

        # 4. Reasoning
        facts_map = self.reasoning_service.load_facts_from_dir(self.facts_dir)
        rel_session = self.reasoning_service.reason_session(match_session, facts_map=facts_map)
        self.reasoning_service.save_results(rel_session, output_path=self.relationships_dir / "relationships_session.json")

        self.invalidate_caches()

        rel_count = sum(
            1 for r in rel_session.relationships
            if r.document_a_id == doc_id or r.document_b_id == doc_id
        )

        return {
            "document_id": doc_id,
            "filename": canonical_doc.metadata.filename,
            "status": "processed",
            "page_count": canonical_doc.metadata.page_count,
            "fact_count": len(extraction_result.facts),
            "relationship_count": rel_count,
        }

    def list_documents(self, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Lists metadata for all documents in data/parsed/ (and pending input PDFs)."""
        docs: Dict[str, Dict[str, Any]] = {}

        for p_file in sorted(self.parsed_dir.glob("*.json")):
            doc_id = p_file.stem
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("metadata", {})
                fact_count = 0
                fact_file = self.facts_dir / f"{doc_id}.json"
                if fact_file.exists():
                    try:
                        with open(fact_file, "r", encoding="utf-8") as ff:
                            fdata = json.load(ff)
                        fact_count = len(fdata.get("facts", []))
                    except Exception:
                        pass

                docs[doc_id] = {
                    "document_id": doc_id,
                    "filename": meta.get("filename", f"{doc_id}.pdf"),
                    "status": "processed",
                    "page_count": meta.get("page_count", 0),
                    "fact_count": fact_count,
                    "created_at": None
                }
            except Exception:
                continue

        for pdf in sorted(self.input_dir.glob("*.pdf")):
            matched = any(d["filename"] == pdf.name for d in docs.values())
            if not matched:
                slug = pdf.stem.lower()
                docs[f"pending-{slug}"] = {
                    "document_id": f"pending-{slug}",
                    "filename": pdf.name,
                    "status": "unprocessed",
                    "page_count": 0,
                    "fact_count": 0,
                    "created_at": None
                }

        doc_list = list(docs.values())
        total = len(doc_list)
        start = (page - 1) * page_size
        end = start + page_size
        return doc_list[start:end], total

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves lightweight metadata for a single document."""
        parsed_file = self.parsed_dir / f"{document_id}.json"
        if not parsed_file.exists():
            return None

        with open(parsed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("metadata", {})
        fact_count = 0
        fact_file = self.facts_dir / f"{document_id}.json"
        if fact_file.exists():
            try:
                with open(fact_file, "r", encoding="utf-8") as ff:
                    fdata = json.load(ff)
                fact_count = len(fdata.get("facts", []))
            except Exception:
                pass

        rel_count = 0
        rels = self.load_all_relationships()
        for r in rels:
            if r.document_a_id == document_id or r.document_b_id == document_id:
                rel_count += 1

        return {
            "document_id": document_id,
            "filename": meta.get("filename", f"{document_id}.pdf"),
            "status": "processed",
            "page_count": meta.get("page_count", 0),
            "fact_count": fact_count,
            "relationship_count": rel_count,
            "title": meta.get("title"),
            "file_size_bytes": meta.get("file_size_bytes"),
            "sha256": meta.get("sha256"),
        }

    def get_facts_for_document(
        self,
        document_id: str,
        fact_type: Optional[str] = None,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        page_filter: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieves and filters facts for a document, resolving evidence."""
        fact_file = self.facts_dir / f"{document_id}.json"
        if not fact_file.exists():
            return [], 0

        with open(fact_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_facts = data.get("facts", [])
        filtered: List[Dict[str, Any]] = []

        for rf in raw_facts:
            if fact_type and rf.get("fact_type") != fact_type:
                continue

            if subject:
                subj_name = rf.get("subject", {}).get("name", "")
                if subject.lower() not in subj_name.lower():
                    continue

            if predicate:
                pred = rf.get("predicate", "")
                if predicate.lower() not in pred.lower():
                    continue

            resolved_evidence = self.resolve_evidence(document_id, rf.get("evidence_ids", []))

            if page_filter is not None:
                pages = [ev["page"] for ev in resolved_evidence if ev.get("page") is not None]
                if page_filter not in pages:
                    continue

            fact_item = dict(rf)
            fact_item["document_id"] = document_id
            fact_item["evidence"] = resolved_evidence
            filtered.append(fact_item)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    def _ensure_facts_cache(self) -> Dict[str, Tuple[str, Fact]]:
        """Loads all facts into memory keyed by fact_id: {fact_id: (document_id, Fact)}."""
        if self._facts_cache is not None:
            return self._facts_cache

        cache: Dict[str, Tuple[str, Fact]] = {}
        for f_file in self.facts_dir.glob("*.json"):
            try:
                with open(f_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result = FactExtractionResult.model_validate(data)
                for fact in result.facts:
                    cache[fact.fact_id] = (result.document_id, fact)
            except Exception:
                continue

        self._facts_cache = cache
        return self._facts_cache

    def get_fact_by_id(self, fact_id: str) -> Optional[Dict[str, Any]]:
        """Finds a fact by fact_id across the knowledge base with resolved evidence."""
        cache = self._ensure_facts_cache()
        if fact_id not in cache:
            return None

        doc_id, fact = cache[fact_id]
        fact_dict = fact.model_dump(mode="json")
        fact_dict["document_id"] = doc_id
        fact_dict["evidence"] = self.resolve_evidence(doc_id, fact.evidence_ids)
        return fact_dict

    def load_all_relationships(self) -> List[RelationshipResult]:
        """Loads relationships from relationships_session.json."""
        if self._relationships_cache is not None:
            return self._relationships_cache

        rel_file = self.relationships_dir / "relationships_session.json"
        if not rel_file.exists():
            return []

        try:
            with open(rel_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            session_result = RelationshipSessionResult.model_validate(data)
            self._relationships_cache = session_result.relationships
            return self._relationships_cache
        except Exception:
            return []

    def get_relationships(
        self,
        document_id: Optional[str] = None,
        fact_id: Optional[str] = None,
        relationship_type: Optional[str] = None,
        source_independence: Optional[str] = None,
        confidence_min: Optional[float] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Filters relationships from session results."""
        all_rels = self.load_all_relationships()
        filtered: List[Dict[str, Any]] = []

        for r in all_rels:
            if document_id:
                if r.document_a_id != document_id and r.document_b_id != document_id:
                    continue

            if fact_id:
                if r.fact_a_id != fact_id and r.fact_b_id != fact_id:
                    continue

            rel_val = r.relationship.value if hasattr(r.relationship, "value") else str(r.relationship)
            if relationship_type and rel_val != relationship_type:
                continue

            if source_independence and r.source_independence != source_independence:
                continue

            if confidence_min is not None and r.confidence < confidence_min:
                continue

            r_dict = r.model_dump(mode="json")
            r_dict["relationship_type"] = rel_val
            r_dict["relationship"] = rel_val
            ev_a = self.resolve_evidence(r.document_a_id or "", r.evidence.fact_a_evidence)
            ev_b = self.resolve_evidence(r.document_b_id or "", r.evidence.fact_b_evidence)
            r_dict["evidence_a"] = ev_a
            r_dict["evidence_b"] = ev_b
            filtered.append(r_dict)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    def get_relationship_by_id(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single relationship with detailed explanations and evidence."""
        all_rels = self.load_all_relationships()
        for r in all_rels:
            if r.relationship_id == relationship_id:
                r_dict = r.model_dump(mode="json")
                rel_val = r.relationship.value if hasattr(r.relationship, "value") else str(r.relationship)
                r_dict["relationship_type"] = rel_val
                r_dict["relationship"] = rel_val
                ev_a = self.resolve_evidence(r.document_a_id or "", r.evidence.fact_a_evidence)
                ev_b = self.resolve_evidence(r.document_b_id or "", r.evidence.fact_b_evidence)
                r_dict["evidence_a"] = ev_a
                r_dict["evidence_b"] = ev_b
                return r_dict
        return None

    def query_knowledge_layer(
        self,
        query: str,
        document_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes an evidence-grounded query across the structured knowledge layer.
        """
        facts_cache = self._ensure_facts_cache()
        query_clean = query.strip()
        query_lower = query_clean.lower()
        GENERIC_TIME_WORDS = {"year", "fiscal", "calendar", "period", "ended", "date", "as", "of", "quarter", "month"}
        all_tokens = re.findall(r"\b[a-z0-9_\-]+\b", query_lower)
        query_tokens = [
            t for t in all_tokens
            if t not in STOP_WORDS and t not in GENERIC_TIME_WORDS and len(t) >= 2
        ]

        is_conflict_query = any(k in query_lower for k in [
            "conflict", "contradict", "differ", "disagree", "discrepancy", "diverg", "incompatible"
        ])
        is_corroboration_query = any(k in query_lower for k in [
            "corroborat", "confirm", "support", "agree", "consistent", "same"
        ])

        # Expand query tokens with semantic synonyms
        synonym_predicates: Set[str] = set()
        for token in query_tokens:
            if token in SEMANTIC_SYNONYMS:
                synonym_predicates.update(SEMANTIC_SYNONYMS[token])

        candidate_facts: List[Tuple[float, str, Fact]] = []

        for fact_id, (doc_id, fact) in facts_cache.items():
            if document_ids and doc_id not in document_ids:
                continue

            score = 0.0
            pred = fact.predicate.lower()
            pred_phrase = pred.replace("_", " ")

            # 1. Predicate matching (exact phrase, token, or semantic synonym)
            if not pred.isdigit() and len(pred) >= 3 and pred_phrase in query_lower:
                score += 40.0
            elif pred in query_tokens and not pred.isdigit():
                score += 35.0
            elif pred in synonym_predicates:
                score += 25.0
            elif not pred.isdigit() and len(pred) >= 4 and any(token in pred_phrase.split() for token in query_tokens if len(token) >= 4):
                score += 15.0

            # 2. Subject matching
            subj = fact.subject.name.lower()
            if any(token == subj for token in query_tokens):
                score += 15.0
            elif len(subj) >= 4 and any(token in subj for token in query_tokens if len(token) >= 4):
                score += 8.0

            # 3. Temporal matching (excluding generic words like 'year')
            if fact.time.value:
                t_val = fact.time.value.lower()
                t_tokens = set(re.findall(r"\b[a-z0-9]+\b", t_val))
                overlap_time = (set(query_tokens) - GENERIC_TIME_WORDS).intersection(t_tokens - GENERIC_TIME_WORDS)
                if overlap_time:
                    score += 15.0 * len(overlap_time)

            # 4. Scope matching
            if fact.scope:
                s_val = fact.scope.lower()
                if any(token == s_val for token in query_tokens if len(token) >= 3):
                    score += 8.0

            # 5. Value match (avoid matching single digit numbers from years)
            val_str = str(fact.object.value).lower()
            if len(val_str) >= 2 and any(token == val_str for token in query_tokens):
                score += 10.0

            # Keep only high-confidence matches
            if score >= 15.0:
                candidate_facts.append((score, doc_id, fact))

        candidate_facts.sort(key=lambda x: x[0], reverse=True)

        all_rels = self.load_all_relationships()

        # Handle general conflict query when no specific facts matched
        if is_conflict_query and not candidate_facts:
            contradiction_rels = [
                r for r in all_rels
                if r.relationship == RelationshipType.CONTRADICTS
                and (not document_ids or (r.document_a_id in document_ids or r.document_b_id in document_ids))
            ]
            if contradiction_rels:
                top_rels = contradiction_rels[:5]
                fact_map: Dict[str, Dict[str, Any]] = {}
                rel_list = []
                for r in top_rels:
                    r_dict = r.model_dump(mode="json")
                    r_dict["relationship_type"] = r.relationship.value
                    r_dict["relationship"] = r.relationship.value
                    r_dict["evidence_a"] = self.resolve_evidence(r.document_a_id or "", r.evidence.fact_a_evidence)
                    r_dict["evidence_b"] = self.resolve_evidence(r.document_b_id or "", r.evidence.fact_b_evidence)
                    rel_list.append(r_dict)

                    if r.fact_a and r.fact_a_id not in fact_map:
                        fa = r.fact_a.model_dump(mode="json")
                        fa["document_id"] = r.document_a_id
                        fa["evidence"] = self.resolve_evidence(r.document_a_id or "", r.fact_a.evidence_ids)
                        fact_map[r.fact_a_id] = fa

                    if r.fact_b and r.fact_b_id not in fact_map:
                        fb = r.fact_b.model_dump(mode="json")
                        fb["document_id"] = r.document_b_id
                        fb["evidence"] = self.resolve_evidence(r.document_b_id or "", r.fact_b.evidence_ids)
                        fact_map[r.fact_b_id] = fb

                return {
                    "query": query_clean,
                    "status": "answered",
                    "answer": (
                        f"Yes, the available documents contain {len(top_rels)} identified contradictions. "
                        f"Primary example: {top_rels[0].reason}"
                    ),
                    "facts": list(fact_map.values()),
                    "relationships": rel_list
                }

        if not candidate_facts:
            return {
                "query": query_clean,
                "status": "no_results",
                "answer": "No matching evidence was found.",
                "facts": [],
                "relationships": []
            }

        top_candidates = candidate_facts[:15]
        top_fact_ids = {fact.fact_id for _, _, fact in top_candidates}

        relevant_rels: List[RelationshipResult] = []
        for r in all_rels:
            if r.fact_a_id in top_fact_ids and r.fact_b_id in top_fact_ids:
                relevant_rels.append(r)
            elif (r.fact_a_id in top_fact_ids or r.fact_b_id in top_fact_ids) and r.relationship in (
                RelationshipType.CONTRADICTS,
                RelationshipType.CORROBORATES,
                RelationshipType.CONTEXTUALLY_RECONCILED
            ):
                relevant_rels.append(r)

        result_fact_dict: Dict[str, Dict[str, Any]] = {}
        for _, doc_id, fact in top_candidates:
            f_dict = fact.model_dump(mode="json")
            f_dict["document_id"] = doc_id
            f_dict["evidence"] = self.resolve_evidence(doc_id, fact.evidence_ids)
            result_fact_dict[fact.fact_id] = f_dict

        for r in relevant_rels:
            if r.fact_a_id not in result_fact_dict and r.fact_a:
                f_a = r.fact_a.model_dump(mode="json")
                f_a["document_id"] = r.document_a_id
                f_a["evidence"] = self.resolve_evidence(r.document_a_id or "", r.fact_a.evidence_ids)
                result_fact_dict[r.fact_a_id] = f_a
            if r.fact_b_id not in result_fact_dict and r.fact_b:
                f_b = r.fact_b.model_dump(mode="json")
                f_b["document_id"] = r.document_b_id
                f_b["evidence"] = self.resolve_evidence(r.document_b_id or "", r.fact_b.evidence_ids)
                result_fact_dict[r.fact_b_id] = f_b

        final_facts = list(result_fact_dict.values())

        final_rels = []
        for r in relevant_rels:
            r_dict = r.model_dump(mode="json")
            rel_val = r.relationship.value if hasattr(r.relationship, "value") else str(r.relationship)
            r_dict["relationship_type"] = rel_val
            r_dict["relationship"] = rel_val
            r_dict["evidence_a"] = self.resolve_evidence(r.document_a_id or "", r.evidence.fact_a_evidence)
            r_dict["evidence_b"] = self.resolve_evidence(r.document_b_id or "", r.evidence.fact_b_evidence)
            final_rels.append(r_dict)

        contradictions = [r for r in relevant_rels if r.relationship == RelationshipType.CONTRADICTS]
        corroborations = [r for r in relevant_rels if r.relationship == RelationshipType.CORROBORATES]
        reconciliations = [r for r in relevant_rels if r.relationship == RelationshipType.CONTEXTUALLY_RECONCILED]
        unresolved = [r for r in relevant_rels if r.relationship == RelationshipType.UNRESOLVED]

        status = "answered"
        answer_parts = []

        if is_conflict_query:
            if contradictions:
                c = contradictions[0]
                val_a = f"{c.fact_a.object.currency or ''}{c.fact_a.object.value} {c.fact_a.object.unit or ''}".strip() if c.fact_a else ""
                val_b = f"{c.fact_b.object.currency or ''}{c.fact_b.object.value} {c.fact_b.object.unit or ''}".strip() if c.fact_b else ""
                time_str = f" for {c.fact_a.time.value}" if c.fact_a and c.fact_a.time.value else ""
                answer_parts.append(
                    f"Yes, the available documents contain conflicting figures{time_str}. "
                    f"Document '{c.document_a_id}' reports {val_a}, whereas '{c.document_b_id}' reports {val_b}."
                )
            elif reconciliations:
                rec = reconciliations[0]
                answer_parts.append(
                    f"No direct conflict was identified; differences are contextually reconciled: {rec.reason}"
                )
            else:
                answer_parts.append("No conflicting figures were identified among the relevant documents.")
        else:
            if contradictions:
                c = contradictions[0]
                answer_parts.append(
                    f"The available documents contain conflicting reported figures. "
                    f"Specifically: {c.reason}"
                )
            elif corroborations:
                corr = corroborations[0]
                val = f"{corr.fact_a.object.currency or ''}{corr.fact_a.object.value} {corr.fact_a.object.unit or ''}".strip() if corr.fact_a else ""
                subj = corr.fact_a.subject.name if corr.fact_a else "The entity"
                pred = corr.fact_a.predicate.replace('_', ' ') if corr.fact_a else "metric"
                answer_parts.append(
                    f"Multiple sources corroborate that {subj} reported {pred} as {val} ({corr.reason})."
                )
            elif reconciliations:
                rec = reconciliations[0]
                answer_parts.append(
                    f"Reported figures show differences that are contextually reconciled: {rec.explanation}"
                )
            elif unresolved:
                status = "ambiguous"
                un = unresolved[0]
                answer_parts.append(
                    f"The relationship between the reported figures remains unresolved: {un.reason}"
                )
            else:
                primary = final_facts[0]
                subj = primary.get("subject", {}).get("name", "Entity")
                pred = primary.get("predicate", "").replace("_", " ")
                obj = primary.get("object", {})
                val = f"{obj.get('currency') or ''}{obj.get('value')} {obj.get('unit') or ''}".strip()
                t_val = primary.get("time", {}).get("value")
                time_str = f" for {t_val}" if t_val else ""
                answer_parts.append(f"{subj} {pred} is reported as {val}{time_str}.")

        return {
            "query": query_clean,
            "status": status,
            "answer": " ".join(answer_parts),
            "facts": final_facts,
            "relationships": final_rels
        }
