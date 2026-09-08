import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from superjoin.matching.service import FactMatchingService
from superjoin.matching.candidate_generator import CandidateGenerator
from superjoin.matching.models import MatchingSessionResult, MatchClassification


def inspect_matches(session: MatchingSessionResult):
    stats = session.statistics
    print("\n" + "=" * 60)
    print("FACT MATCHING EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Total Documents:           {stats.total_documents}")
    print(f"Total Facts Indexed:       {stats.total_facts}")
    print(f"Candidate Pairs Evaluated: {stats.candidate_pairs}")
    print(f"  - SAME_CLAIM:            {stats.same_claim_count}")
    print(f"  - RELATED_CLAIM:         {stats.related_claim_count}")
    print(f"  - NOT_MATCH:             {stats.not_match_count}")
    print(f"  - UNCERTAIN:             {stats.uncertain_count}")
    print(f"Execution Time:            {stats.execution_time_ms:.2f} ms")
    print("=" * 60 + "\n")

    if not session.matches:
        print("No matching pairs discovered.")
        return

    print("Sample Matches:")
    print("-" * 60)
    for i, m in enumerate(session.matches[:15]):
        val_a = f"{m.fact_a.object.currency or ''}{m.fact_a.object.value} {m.fact_a.object.unit or ''} {m.fact_a.object.scale or ''}".strip() if m.fact_a else ""
        val_b = f"{m.fact_b.object.currency or ''}{m.fact_b.object.value} {m.fact_b.object.unit or ''} {m.fact_b.object.scale or ''}".strip() if m.fact_b else ""
        time_a = f" [{m.fact_a.time.value}]" if m.fact_a and m.fact_a.time.value else ""
        time_b = f" [{m.fact_b.time.value}]" if m.fact_b and m.fact_b.time.value else ""

        print(f"[{i+1}] [{m.classification.value}] (Conf: {m.confidence:.2f})")
        print(f"    Fact A ({m.document_a_id}): {m.fact_a.subject.name} -> {m.fact_a.predicate} -> {val_a}{time_a}" if m.fact_a else f"    Fact A: {m.fact_a_id}")
        print(f"    Fact B ({m.document_b_id}): {m.fact_b.subject.name} -> {m.fact_b.predicate} -> {val_b}{time_b}" if m.fact_b else f"    Fact B: {m.fact_b_id}")
        print(f"    Signals: {m.signals.model_dump()}")
        print(f"    Reasons:")
        for r in m.reasons:
            print(f"      - {r}")
        print("-" * 60)

    if len(session.matches) > 15:
        print(f"... and {len(session.matches) - 15} more matches.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Superjoin Fact Layer - Module 4: Fact Matching")
    parser.add_argument("--input", type=str, default="data/facts", help="Path to a facts JSON file or directory")
    parser.add_argument("--output", type=str, default="data/matches", help="Output directory for match results")
    parser.add_argument("--inspect", action="store_true", help="Print detailed match breakdown")
    parser.add_argument("--allow-intra-doc", action="store_true", help="Compare facts within the same document")

    args = parser.parse_args()

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        sys.exit(1)

    candidate_gen = CandidateGenerator(cross_document_only=not args.allow_intra_doc)
    service = FactMatchingService(
        candidate_generator=candidate_gen,
        output_dir=output_dir
    )

    if input_path.is_file():
        doc_result = service.load_from_json(input_path)
        extraction_results = [doc_result]
    else:
        extraction_results = service.load_from_dir(input_path)

    print(f"Loaded {len(extraction_results)} fact documents from {input_path}")

    session_result = service.match(extraction_results)
    out_file = service.save_results(session_result, filename="matches_session.json")

    if args.inspect:
        inspect_matches(session_result)
    else:
        stats = session_result.statistics
        print(f"Indexed {stats.total_facts} facts across {stats.total_documents} documents.")
        print(f"Candidate pairs: {stats.candidate_pairs}")
        print(f"SAME_CLAIM: {stats.same_claim_count} | RELATED_CLAIM: {stats.related_claim_count} | NOT_MATCH: {stats.not_match_count} | UNCERTAIN: {stats.uncertain_count}")
        print(f"Results saved to: {out_file}\n")


if __name__ == "__main__":
    main()
