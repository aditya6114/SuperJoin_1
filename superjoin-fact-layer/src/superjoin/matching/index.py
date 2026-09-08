import unicodedata
from typing import Optional, List, Dict, Tuple, Set
from collections import defaultdict

from superjoin.extraction.models import Fact, FactExtractionResult


def normalize_key(text: Optional[str]) -> str:
    """Conservatively normalize a key string: NFKC unicode, strip whitespace, lowercase."""
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    return normalized.strip().lower()


def resolve_subject(subject_name: Optional[str], document_id: Optional[str] = None) -> str:
    """Safely resolve generic subjects if document origin provides unambiguous grounding."""
    norm = normalize_key(subject_name)
    if norm in {"company", "the company", "our company"} and document_id:
        if "delhivery" in document_id.lower():
            return "delhivery"
    if norm in {"delhivery limited", "delhivery ltd"}:
        return "delhivery"
    return norm


class IndexedFact:
    """Container associating an extracted Fact with its document origin and normalized keys."""
    __slots__ = ("fact", "document_id", "normalized_subject", "normalized_predicate")

    def __init__(self, fact: Fact, document_id: str):
        self.fact = fact
        self.document_id = document_id
        raw_subj = fact.subject.name if fact.subject else ""
        self.normalized_subject = resolve_subject(raw_subj, document_id)
        self.normalized_predicate = normalize_key(fact.predicate)


class FactIndex:
    """In-memory inverted index for fast candidate retrieval across extracted facts.
    
    Provides lookup by:
    - fact_id
    - document_id
    - subject
    - predicate
    - (subject, predicate)
    
    Preserves original Fact instances without alteration.
    """

    def __init__(self):
        self._by_id: Dict[str, IndexedFact] = {}
        self._by_document: Dict[str, List[IndexedFact]] = defaultdict(list)
        self._by_subject: Dict[str, List[IndexedFact]] = defaultdict(list)
        self._by_predicate: Dict[str, List[IndexedFact]] = defaultdict(list)
        self._by_subject_predicate: Dict[Tuple[str, str], List[IndexedFact]] = defaultdict(list)

    def add_fact(self, fact: Fact, document_id: str) -> None:
        """Index a single fact associated with a document_id."""
        if not fact or not fact.fact_id:
            return

        indexed = IndexedFact(fact=fact, document_id=document_id)
        self._by_id[fact.fact_id] = indexed
        self._by_document[document_id].append(indexed)

        if indexed.normalized_subject:
            self._by_subject[indexed.normalized_subject].append(indexed)
        if indexed.normalized_predicate:
            self._by_predicate[indexed.normalized_predicate].append(indexed)
        if indexed.normalized_subject and indexed.normalized_predicate:
            key = (indexed.normalized_subject, indexed.normalized_predicate)
            self._by_subject_predicate[key].append(indexed)

    def index_facts(self, facts: List[Fact], document_id: str) -> None:
        """Index a collection of facts for a document."""
        for fact in facts:
            self.add_fact(fact, document_id)

    def index_extraction_result(self, result: FactExtractionResult) -> None:
        """Index all facts from a FactExtractionResult."""
        if not result or not result.document_id:
            return
        self.index_facts(result.facts, result.document_id)

    def get(self, fact_id: str) -> Optional[Fact]:
        """Retrieve a fact by its unique ID."""
        indexed = self._by_id.get(fact_id)
        return indexed.fact if indexed else None

    def get_document_id(self, fact_id: str) -> Optional[str]:
        """Retrieve the document_id associated with a fact ID."""
        indexed = self._by_id.get(fact_id)
        return indexed.document_id if indexed else None

    def get_indexed(self, fact_id: str) -> Optional[IndexedFact]:
        """Retrieve the internal IndexedFact wrapper."""
        return self._by_id.get(fact_id)

    def by_document(self, document_id: str) -> List[Fact]:
        """Retrieve all facts belonging to a given document."""
        return [item.fact for item in self._by_document.get(document_id, [])]

    def by_subject(self, subject: str) -> List[Fact]:
        """Retrieve all facts matching the normalized subject."""
        norm = normalize_key(subject)
        return [item.fact for item in self._by_subject.get(norm, [])]

    def by_predicate(self, predicate: str) -> List[Fact]:
        """Retrieve all facts matching the normalized predicate."""
        norm = normalize_key(predicate)
        return [item.fact for item in self._by_predicate.get(norm, [])]

    def by_subject_predicate(self, subject: str, predicate: str) -> List[Fact]:
        """Retrieve all facts matching both subject and predicate."""
        norm_subj = normalize_key(subject)
        norm_pred = normalize_key(predicate)
        return [item.fact for item in self._by_subject_predicate.get((norm_subj, norm_pred), [])]

    def all_facts(self) -> List[Fact]:
        """Return all indexed facts."""
        return [item.fact for item in self._by_id.values()]

    def all_indexed_facts(self) -> List[IndexedFact]:
        """Return all IndexedFact wrappers."""
        return list(self._by_id.values())

    def documents(self) -> Set[str]:
        """Return all distinct document IDs present in the index."""
        return set(self._by_document.keys())

    def subjects(self) -> Set[str]:
        """Return all distinct normalized subjects present in the index."""
        return set(self._by_subject.keys())

    def predicates(self) -> Set[str]:
        """Return all distinct normalized predicates present in the index."""
        return set(self._by_predicate.keys())

    def subject_predicate_keys(self) -> Set[Tuple[str, str]]:
        """Return all distinct (subject, predicate) normalized pairs."""
        return set(self._by_subject_predicate.keys())

    def indexed_by_subject_predicate(self, subject: str, predicate: str) -> List[IndexedFact]:
        """Retrieve IndexedFact wrappers matching both subject and predicate."""
        norm_subj = normalize_key(subject)
        norm_pred = normalize_key(predicate)
        return self._by_subject_predicate.get((norm_subj, norm_pred), [])

    def indexed_by_subject(self, subject: str) -> List[IndexedFact]:
        """Retrieve IndexedFact wrappers matching subject."""
        norm_subj = normalize_key(subject)
        return self._by_subject.get(norm_subj, [])

    def indexed_by_predicate(self, predicate: str) -> List[IndexedFact]:
        """Retrieve IndexedFact wrappers matching predicate."""
        norm_pred = normalize_key(predicate)
        return self._by_predicate.get(norm_pred, [])

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, fact_id: str) -> bool:
        return fact_id in self._by_id
