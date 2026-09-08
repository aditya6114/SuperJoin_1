import argparse
import sys
from pathlib import Path
from typing import Optional

from .service import RelationshipReasoningService
from .models import RelationshipSessionResult, RelationshipType


def inspect_relationships(session: RelationshipSessionResult):
    """Print a detailed breakdown of relationship reasoning results."""
    stats = session.statistics
    print("\n" + "=" * 65)
    print("RELATIONSHIP & CONFLICT REASONING SUMMARY")
    print("=" * 65)
    print(f"Total Evaluated Pairs:         {stats.total_pairs}")
    print(f"  - CORROBORATES:              {stats.corroborates}")
    print(f"  - CONTRADICTS:               {stats.contradicts}")
    print(f"  - CONTEXTUALLY_RECONCILED:   {stats.contextually_reconciled}")
    print(f"  - UNRELATED:                 {stats.unrelated}")
    print(f"  - UNRESOLVED:                {stats.unresolved}")
    print(f"Cross-document relationships:  {stats.cross_document_count}")
    print(f"Same-document relationships:   {stats.same_document_count}")
    print(f"Average Confidence:            {stats.average_confidence:.4f}")
    print(f"Execution Time:                {stats.execution_time_ms:.2f} ms")
    print("=" * 65 + "\n")

    if not session.relationships:
        print("No relationships to display.")
        return

    # Group sample by category
    by_type = {}
    for r in session.relationships:
        by_type.setdefault(r.relationship, []).append(r)

    print("Representative Category Samples:")
    print("-" * 65)

    for rel_type in [
        RelationshipType.CORROBORATES,
        RelationshipType.CONTRADICTS,
        RelationshipType.CONTEXTUALLY_RECONCILED,
        RelationshipType.UNRESOLVED,
        RelationshipType.UNRELATED,
    ]:
        items = by_type.get(rel_type, [])
        if not items:
            continue
        sample = items[0]
        f_a_desc = f"{sample.fact_a.subject.name} -> {sample.fact_a.predicate} = {sample.fact_a.object.value}" if sample.fact_a else sample.fact_a_id
        f_b_desc = f"{sample.fact_b.subject.name} -> {sample.fact_b.predicate} = {sample.fact_b.object.value}" if sample.fact_b else sample.fact_b_id

        print(f"[{sample.relationship.value}] (Confidence: {sample.confidence:.2f}, Source: {sample.source_independence})")
        print(f"  Fact A ({sample.document_a_id or 'doc_a'}): {f_a_desc}")
        print(f"  Fact B ({sample.document_b_id or 'doc_b'}): {f_b_desc}")
        print(f"  Reason:      {sample.reason}")
        print(f"  Explanation: {sample.explanation}")
        print(f"  Evidence:    Fact A: {sample.evidence.fact_a_evidence} | Fact B: {sample.evidence.fact_b_evidence}")
        print("-" * 65)
    print()


def main():
    parser = argparse.ArgumentParser(description="Superjoin Fact Layer - Module 5: Relationship & Conflict Reasoning")
    parser.add_argument("--matches", type=str, default="data/matches/matches_session.json", help="Path to matches JSON file")
    parser.add_argument("--facts", type=str, default="data/facts", help="Path to facts directory or file")
    parser.add_argument("--output", type=str, default="data/relationships/relationships_session.json", help="Output path for relationship JSON")
    parser.add_argument("--inspect", action="store_true", help="Print detailed breakdown and representative samples")
    parser.add_argument("--use-llm", action="store_true", help="Enable optional OpenAI semantic reasoning for unresolved cases")

    args = parser.parse_args()

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    matches_path = Path(args.matches)
    if not matches_path.exists():
        print(f"Error: Matches file not found: {matches_path}")
        sys.exit(1)

    service = RelationshipReasoningService(use_llm=args.use_llm)

    # Load facts if facts path exists
    facts_path = Path(args.facts)
    facts_map = service.load_facts_from_dir(facts_path) if facts_path.exists() else {}

    # Load matches
    match_session = service.load_matches_from_file(matches_path)
    print(f"Loaded {len(match_session.matches)} match results from {matches_path}")

    # Reason relationships
    rel_session = service.reason_session(match_session, facts_map=facts_map)
    out_file = service.save_results(rel_session, output_path=args.output)

    if args.inspect:
        inspect_relationships(rel_session)
    else:
        stats = rel_session.statistics
        print(f"Processed {stats.total_pairs} pairs into relationships:")
        print(f"CORROBORATES: {stats.corroborates} | CONTRADICTS: {stats.contradicts} | "
              f"CONTEXTUALLY_RECONCILED: {stats.contextually_reconciled} | UNRELATED: {stats.unrelated} | UNRESOLVED: {stats.unresolved}")
        print(f"Average confidence: {stats.average_confidence:.4f}")
        print(f"Saved to: {out_file}\n")


if __name__ == "__main__":
    main()
