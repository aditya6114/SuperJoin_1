import time
import json
from pathlib import Path
from typing import List, Optional, Union

from superjoin.extraction.models import FactExtractionResult
from .models import (
    MatchingSessionResult,
    MatchingStatistics,
    MatchResult,
    MatchClassification
)
from .index import FactIndex
from .candidate_generator import CandidateGenerator
from .deterministic_matcher import DeterministicMatcher
from .validators import validate_match_result


class FactMatchingService:
    """End-to-end service for indexing facts, generating candidates, and executing deterministic matching."""

    def __init__(
        self,
        candidate_generator: Optional[CandidateGenerator] = None,
        matcher: Optional[DeterministicMatcher] = None,
        output_dir: Optional[Union[str, Path]] = "data/matches"
    ):
        self.candidate_generator = candidate_generator or CandidateGenerator(cross_document_only=True)
        self.matcher = matcher or DeterministicMatcher()
        self.output_dir = Path(output_dir) if output_dir else Path("data/matches")

    def load_from_json(self, file_path: Union[str, Path]) -> FactExtractionResult:
        """Load FactExtractionResult from a JSON file."""
        p = Path(file_path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return FactExtractionResult.model_validate(data)

    def load_from_dir(self, dir_path: Union[str, Path]) -> List[FactExtractionResult]:
        """Load all FactExtractionResult JSON files from a directory."""
        p = Path(dir_path)
        results: List[FactExtractionResult] = []
        if not p.exists():
            return results

        json_files = sorted(list(p.glob("*.json")))
        for jf in json_files:
            try:
                res = self.load_from_json(jf)
                results.append(res)
            except Exception as e:
                # If a file is not a FactExtractionResult (e.g. metadata), skip
                pass
        return results

    def match(self, extraction_results: List[FactExtractionResult]) -> MatchingSessionResult:
        """Build FactIndex and perform cross-document fact matching."""
        start_time = time.perf_counter()

        index = FactIndex()
        for res in extraction_results:
            index.index_extraction_result(res)

        session_result = self.match_index(index)
        session_result.statistics.total_documents = len(extraction_results)
        session_result.statistics.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return session_result

    def match_index(self, index: FactIndex) -> MatchingSessionResult:
        """Execute candidate generation and deterministic comparison over a prepared FactIndex."""
        candidates = self.candidate_generator.generate_candidates(index)

        stats = MatchingStatistics(
            total_documents=len(index.documents()),
            total_facts=len(index),
            candidate_pairs=len(candidates)
        )

        matches: List[MatchResult] = []

        for cand in candidates:
            fact_a = index.get(cand.fact_a_id)
            fact_b = index.get(cand.fact_b_id)
            if not fact_a or not fact_b:
                continue

            match_res = self.matcher.compare(fact_a, fact_b, candidate=cand)
            validate_match_result(match_res)

            if match_res.classification == MatchClassification.SAME_CLAIM:
                stats.same_claim_count += 1
            elif match_res.classification == MatchClassification.RELATED_CLAIM:
                stats.related_claim_count += 1
            elif match_res.classification == MatchClassification.NOT_MATCH:
                stats.not_match_count += 1
            elif match_res.classification == MatchClassification.UNCERTAIN:
                stats.uncertain_count += 1

            matches.append(match_res)

        return MatchingSessionResult(matches=matches, statistics=stats)

    def save_results(
        self,
        session_result: MatchingSessionResult,
        filename: str = "matches_session.json"
    ) -> Path:
        """Persist matching session results to JSON."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / filename
        data = session_result.model_dump(mode="json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out_path
