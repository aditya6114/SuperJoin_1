import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set

from superjoin.ingestion.service import DocumentIngestionService
from superjoin.ingestion.validator import validate_pdf
from superjoin.extraction.service import FactExtractionService
from superjoin.extraction.models import Fact, FactExtractionResult
from superjoin.matching.service import FactMatchingService
from superjoin.reasoning.service import RelationshipReasoningService
from superjoin.reasoning.models import (
    RelationshipSessionResult,
    RelationshipResult,
    RelationshipType
)
from superjoin.api.schemas import (
    DocumentInfo,
    EvidenceModel,
    FactModel,
    RelationshipModel,
    DocumentResultsResponse,
    CorpusResultsResponse,
    QueryResponse,
    FactsListResponse,
    RelationshipsListResponse
)

STOP_WORDS = {
    "the", "in", "of", "and", "a", "an", "for", "to", "was", "is", "are",
    "by", "at", "on", "with", "from", "as", "that", "it", "its", "what",
    "how", "many", "there", "were", "or", "which", "who", "whom", "this",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "about", "any", "all", "some"
}

GENERIC_TIME_WORDS = {
    "year", "fiscal", "calendar", "period", "ended", "date", "as", "of", "quarter", "month"
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


class KnowledgeLayerService:
    """
    Lightweight orchestration service coordinating Ingestion, Extraction,
    Matching, and Reasoning pipelines for the API layer.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent.parent.parent
        else:
            self.base_dir = Path(base_dir)

        self.input_dir = self.base_dir / "data" / "input"
        self.parsed_dir = self.base_dir / "data" / "parsed"
        self.facts_dir = self.base_dir / "data" / "facts"
        self.matches_dir = self.base_dir / "data" / "matches"
        self.relationships_dir = self.base_dir / "data" / "relationships"

        for d in [self.input_dir, self.parsed_dir, self.facts_dir, self.matches_dir, self.relationships_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.ingestion_service = DocumentIngestionService()
        self.extraction_service = FactExtractionService(
            llm_client=None,
            llm_enabled=False,
            output_dir=str(self.facts_dir)
        )
        self.matching_service = FactMatchingService(
            output_dir=self.matches_dir
        )
        self.reasoning_service = RelationshipReasoningService(
            output_dir=self.relationships_dir,
            use_llm=False
        )

        self._evidence_cache: Dict[str, Dict[str, Tuple[Optional[int], Optional[str]]]] = {}
        self._facts_cache: Optional[Dict[str, Tuple[str, Fact]]] = None
        self._relationships_cache: Optional[List[RelationshipResult]] = None

    def invalidate_caches(self):
        """Invalidates in-memory lookup caches."""
        self._evidence_cache.clear()
        self._facts_cache = None
        self._relationships_cache = None

    def get_document_evidence_map(self, document_id: str) -> Dict[str, Tuple[Optional[int], Optional[str]]]:
        """Indexes element and evidence IDs to (page_number, text) from CanonicalDocument."""
        if document_id in self._evidence_cache:
            return self._evidence_cache[document_id]

        parsed_file = self.parsed_dir / f"{document_id}.json"
        index: Dict[str, Tuple[Optional[int], Optional[str]]] = {}

        if parsed_file.exists():
            try:
                with open(parsed_file, "r", encoding="utf-8") as f:
                    doc_data = json.load(f)
                for page in doc_data.get("pages", []):
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

        self._evidence_cache[document_id] = index
        return index

    def resolve_primary_evidence(self, document_id: str, evidence_ids: List[str]) -> EvidenceModel:
        """Resolves the primary source evidence citation for a fact."""
        index = self.get_document_evidence_map(document_id)
        for eid in evidence_ids:
            if eid in index:
                page_num, text = index[eid]
                return EvidenceModel(page=page_num, text=text)

        # Fallback to regex for :p<num>: if present
        for eid in evidence_ids:
            m = re.search(r":p(\d+):", eid)
            if m:
                return EvidenceModel(page=int(m.group(1)), text=None)

        return EvidenceModel(page=None, text=None)

    @staticmethod
    def format_fact_value(fact: Fact) -> str:
        """Formats an atomic fact value into a readable string (e.g. '₹500 crore')."""
        curr = fact.object.currency or ""
        val = str(fact.object.value)
        scale = fact.object.scale or ""
        unit = fact.object.unit or ""

        parts = [curr + val] if curr else [val]
        if scale:
            parts.append(scale)
        if unit and unit != scale:
            parts.append(unit)
        return " ".join(parts).strip()

    def fact_to_model(self, fact: Fact, document_id: Optional[str] = None) -> FactModel:
        """Converts internal Fact model to API FactModel."""
        doc_id = document_id or "unknown"
        ev = self.resolve_primary_evidence(doc_id, fact.evidence_ids)
        period = fact.time.value if fact.time and fact.time.value else None

        return FactModel(
            fact_id=fact.fact_id,
            document_id=doc_id,
            subject=fact.subject.name,
            predicate=fact.predicate,
            value=self.format_fact_value(fact),
            period=period,
            evidence=ev
        )

    def relationship_to_model(
        self,
        rel: RelationshipResult,
        embed_facts: bool = True
    ) -> RelationshipModel:
        """Converts internal RelationshipResult to API RelationshipModel with actual embedded facts."""
        rel_type = rel.relationship.value if hasattr(rel.relationship, "value") else str(rel.relationship)

        if not embed_facts:
            return RelationshipModel(
                relationship_id=rel.relationship_id,
                fact_a=rel.fact_a_id,
                fact_b=rel.fact_b_id,
                type=rel_type,
                confidence=round(rel.confidence, 4),
                reason=rel.reason,
                explanation=rel.explanation
            )

        facts_cache = self._ensure_facts_cache()

        # Resolve Fact A
        f_a = rel.fact_a
        doc_a = rel.document_a_id
        if f_a is None and rel.fact_a_id in facts_cache:
            doc_a, f_a = facts_cache[rel.fact_a_id]

        if f_a is not None:
            fact_a_model = self.fact_to_model(f_a, doc_a)
        else:
            fact_a_model = FactModel(
                fact_id=rel.fact_a_id,
                document_id=doc_a,
                subject="unknown",
                predicate="unknown",
                value="unknown",
                evidence=EvidenceModel()
            )

        # Resolve Fact B
        f_b = rel.fact_b
        doc_b = rel.document_b_id
        if f_b is None and rel.fact_b_id in facts_cache:
            doc_b, f_b = facts_cache[rel.fact_b_id]

        if f_b is not None:
            fact_b_model = self.fact_to_model(f_b, doc_b)
        else:
            fact_b_model = FactModel(
                fact_id=rel.fact_b_id,
                document_id=doc_b,
                subject="unknown",
                predicate="unknown",
                value="unknown",
                evidence=EvidenceModel()
            )

        return RelationshipModel(
            relationship_id=rel.relationship_id,
            fact_a=fact_a_model,
            fact_b=fact_b_model,
            type=rel_type,
            confidence=round(rel.confidence, 4),
            reason=rel.reason,
            explanation=rel.explanation
        )

    def process_document(self, pdf_path: Path) -> str:
        """
        Runs the complete Fact Knowledge Layer pipeline on an uploaded PDF:
        1. Ingestion (Module 1)
        2. Extraction (Module 2)
        3. Cross-Document Matching (Module 4)
        4. Relationship Reasoning (Module 5)
        """
        validate_pdf(pdf_path)

        # 1. Module 1: Ingest
        canonical_doc = self.ingestion_service.ingest(pdf_path)
        self.ingestion_service.save(canonical_doc, self.parsed_dir)
        doc_id = canonical_doc.metadata.document_id

        # 2. Module 2: Extract
        extraction_result = self.extraction_service.extract(canonical_doc)
        self.extraction_service.save_result(extraction_result)

        # 3. Module 4: Match across corpus
        all_extractions = self.matching_service.load_from_dir(self.facts_dir)
        match_session = self.matching_service.match(all_extractions)
        self.matching_service.save_results(match_session, filename="matches_session.json")

        # 4. Module 5: Reason relationships
        facts_map = self.reasoning_service.load_facts_from_dir(self.facts_dir)
        rel_session = self.reasoning_service.reason_session(match_session, facts_map=facts_map)
        self.reasoning_service.save_results(rel_session, output_path=self.relationships_dir / "relationships_session.json")

        self.invalidate_caches()
        return doc_id

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

    def get_document_results(self, document_id: str) -> Optional[DocumentResultsResponse]:
        """Retrieves facts and relationships for a specific document."""
        fact_file = self.facts_dir / f"{document_id}.json"
        parsed_file = self.parsed_dir / f"{document_id}.json"

        if not fact_file.exists() and not parsed_file.exists():
            return None

        # Determine filename
        filename = f"{document_id}.pdf"
        if parsed_file.exists():
            try:
                with open(parsed_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                filename = data.get("metadata", {}).get("filename", filename)
            except Exception:
                pass

        doc_info = DocumentInfo(document_id=document_id, filename=filename)

        # Load facts
        facts: List[FactModel] = []
        if fact_file.exists():
            try:
                with open(fact_file, "r", encoding="utf-8") as f:
                    fdata = json.load(f)
                res = FactExtractionResult.model_validate(fdata)
                for fact in res.facts:
                    facts.append(self.fact_to_model(fact, document_id=document_id))
            except Exception:
                pass

        # Load relationships involving this document
        all_rels = self.load_all_relationships()
        rels: List[RelationshipModel] = []
        for r in all_rels:
            if r.document_a_id == document_id or r.document_b_id == document_id:
                rels.append(self.relationship_to_model(r))

        return DocumentResultsResponse(
            document=doc_info,
            facts=facts,
            relationships=rels
        )

    def get_corpus_results(self, document_ids: Optional[List[str]] = None) -> CorpusResultsResponse:
        """Retrieves accumulated results across all or selected documents."""
        doc_ids_filter = set(document_ids) if document_ids else None

        docs: List[DocumentInfo] = []
        facts: List[FactModel] = []

        # Find all documents
        doc_files = sorted(list(self.facts_dir.glob("*.json")))
        for f_file in doc_files:
            doc_id = f_file.stem
            if doc_ids_filter and doc_id not in doc_ids_filter:
                continue

            parsed_file = self.parsed_dir / f"{doc_id}.json"
            filename = f"{doc_id}.pdf"
            if parsed_file.exists():
                try:
                    with open(parsed_file, "r", encoding="utf-8") as pf:
                        pdata = json.load(pf)
                    filename = pdata.get("metadata", {}).get("filename", filename)
                except Exception:
                    pass

            docs.append(DocumentInfo(document_id=doc_id, filename=filename))

            try:
                with open(f_file, "r", encoding="utf-8") as f:
                    fdata = json.load(f)
                res = FactExtractionResult.model_validate(fdata)
                for fact in res.facts:
                    facts.append(self.fact_to_model(fact, document_id=doc_id))
            except Exception:
                continue

        # Filter relationships
        all_rels = self.load_all_relationships()
        rels: List[RelationshipModel] = []
        for r in all_rels:
            if doc_ids_filter:
                if r.document_a_id not in doc_ids_filter and r.document_b_id not in doc_ids_filter:
                    continue
            rels.append(self.relationship_to_model(r))

        return CorpusResultsResponse(
            documents=docs,
            facts=facts,
            relationships=rels
        )

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

    def get_facts(
        self,
        document_id: Optional[str] = None,
        predicate: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> FactsListResponse:
        """Retrieves structured facts across the corpus or for a specific document with optional predicate filter."""
        facts_cache = self._ensure_facts_cache()
        results: List[FactModel] = []

        for fact_id, (doc_id, fact) in facts_cache.items():
            if document_id and doc_id != document_id:
                continue
            if predicate and fact.predicate.lower() != predicate.lower():
                continue
            results.append(self.fact_to_model(fact, doc_id))

        total = len(results)
        paginated = results[offset:offset + limit]
        return FactsListResponse(
            total=total,
            limit=limit,
            offset=offset,
            facts=paginated
        )

    def get_fact_by_id(self, fact_id: str) -> Optional[FactModel]:
        """Retrieves an individual fact by its UUID."""
        facts_cache = self._ensure_facts_cache()
        if fact_id not in facts_cache:
            return None
        doc_id, fact = facts_cache[fact_id]
        return self.fact_to_model(fact, doc_id)

    def get_relationships(
        self,
        relationship_type: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> RelationshipsListResponse:
        """Retrieves relationships with actual embedded facts, optional type filter, and document filters."""
        all_rels = self.load_all_relationships()
        filtered: List[RelationshipResult] = []

        target_type = relationship_type.upper() if relationship_type else None
        target_docs = set(document_ids) if document_ids else None

        for r in all_rels:
            r_type = r.relationship.value if hasattr(r.relationship, "value") else str(r.relationship)
            if target_type and r_type != target_type:
                continue
            if target_docs:
                if r.document_a_id not in target_docs and r.document_b_id not in target_docs:
                    continue
            filtered.append(r)

        total = len(filtered)
        paginated = filtered[offset:offset + limit]
        models = [self.relationship_to_model(r, embed_facts=True) for r in paginated]
        return RelationshipsListResponse(
            total=total,
            limit=limit,
            offset=offset,
            relationships=models
        )

    def get_relationship_by_id(self, relationship_id: str) -> Optional[RelationshipModel]:
        """Retrieves an individual relationship by its UUID with actual embedded facts."""
        all_rels = self.load_all_relationships()
        for r in all_rels:
            if r.relationship_id == relationship_id:
                return self.relationship_to_model(r, embed_facts=True)
        return None


    def query_knowledge_layer(
        self,
        query: str,
        document_ids: Optional[List[str]] = None
    ) -> QueryResponse:
        """
        Operates over the structured fact layer to answer factual inquiries,
        surface corroborations/contradictions, and ground responses with source evidence.
        """
        facts_cache = self._ensure_facts_cache()
        query_clean = query.strip()
        query_lower = query_clean.lower()
        all_tokens = re.findall(r"\b[a-z0-9_\-]+\b", query_lower)
        query_tokens = [
            t for t in all_tokens
            if t not in STOP_WORDS and t not in GENERIC_TIME_WORDS and len(t) >= 2
        ]

        is_conflict_query = any(k in query_lower for k in [
            "conflict", "contradict", "differ", "disagree", "discrepancy", "diverg", "incompatible"
        ])

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

            # 1. Predicate matching
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

            # 3. Temporal matching
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

            # 5. Value match
            val_str = str(fact.object.value).lower()
            if len(val_str) >= 2 and any(token == val_str for token in query_tokens):
                score += 10.0

            if score >= 15.0:
                candidate_facts.append((score, doc_id, fact))

        candidate_facts.sort(key=lambda x: x[0], reverse=True)
        all_rels = self.load_all_relationships()

        # Handle general conflict inquiry if no specific entity/predicate matched
        if is_conflict_query and not candidate_facts:
            contradiction_rels = [
                r for r in all_rels
                if r.relationship == RelationshipType.CONTRADICTS
                and (not document_ids or (r.document_a_id in document_ids or r.document_b_id in document_ids))
            ]
            if contradiction_rels:
                top_rels = contradiction_rels[:5]
                fact_models: List[FactModel] = []
                seen_fids = set()
                for r in top_rels:
                    if r.fact_a and r.fact_a_id not in seen_fids:
                        fact_models.append(self.fact_to_model(r.fact_a, r.document_a_id))
                        seen_fids.add(r.fact_a_id)
                    if r.fact_b and r.fact_b_id not in seen_fids:
                        fact_models.append(self.fact_to_model(r.fact_b, r.document_b_id))
                        seen_fids.add(r.fact_b_id)

                return QueryResponse(
                    query=query_clean,
                    status="contradiction_found",
                    facts=fact_models,
                    relationships=[self.relationship_to_model(r) for r in top_rels]
                )

        if not candidate_facts:
            return QueryResponse(
                query=query_clean,
                status="no_results",
                facts=[],
                relationships=[]
            )

        top_candidates = candidate_facts[:10]
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

        result_facts: Dict[str, FactModel] = {}
        for _, doc_id, fact in top_candidates:
            result_facts[fact.fact_id] = self.fact_to_model(fact, doc_id)

        for r in relevant_rels:
            if r.fact_a_id not in result_facts and r.fact_a:
                result_facts[r.fact_a_id] = self.fact_to_model(r.fact_a, r.document_a_id)
            if r.fact_b_id not in result_facts and r.fact_b:
                result_facts[r.fact_b_id] = self.fact_to_model(r.fact_b, r.document_b_id)

        # Status determination
        has_contradiction = any(r.relationship == RelationshipType.CONTRADICTS for r in relevant_rels)
        if has_contradiction:
            status = "contradiction_found"
        else:
            status = "answered"

        return QueryResponse(
            query=query_clean,
            status=status,
            facts=list(result_facts.values()),
            relationships=[self.relationship_to_model(r) for r in relevant_rels]
        )


_service_instance: Optional[KnowledgeLayerService] = None

def get_knowledge_service() -> KnowledgeLayerService:
    global _service_instance
    if _service_instance is None:
        _service_instance = KnowledgeLayerService()
    return _service_instance
