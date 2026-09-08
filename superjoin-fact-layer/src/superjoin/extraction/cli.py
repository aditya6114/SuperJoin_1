import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from superjoin.ingestion.models import CanonicalDocument
from .service import FactExtractionService
from .llm.provider import DefaultLLMProvider

def inspect_facts(result):
    print(f"\nDocument ID: {result.document_id}")
    print(f"Candidates Analyzed: {result.statistics.candidate_count}")
    print(f"  - Text Candidates: {result.statistics.text_candidate_count}")
    print(f"  - Table Candidates: {result.statistics.table_candidate_count}")
    print(f"  - Figure Candidates: {result.statistics.figure_candidate_count}")
    print(f"Facts Extracted: {result.statistics.facts_extracted}")
    print(f"Facts Validated & Retained: {len(result.facts)}")
    print(f"Validation Rejections: {result.statistics.validation_failures}")
    print(f"Uncertainties / Skipped: {result.statistics.facts_uncertain}\n")

    print("Sample Extracted Facts:")
    print("-" * 60)
    for i, fact in enumerate(result.facts[:15]):
        val_str = f"{fact.object.currency or ''}{fact.object.value} {fact.object.unit or ''} {fact.object.scale or ''}".strip()
        time_str = f" [{fact.time.time_type}: {fact.time.value}]" if fact.time.value else ""
        scope_str = f" ({fact.scope})" if fact.scope else ""
        qual_str = f" [qualifiers: {', '.join(fact.qualifiers)}]" if fact.qualifiers else ""
        print(f"[{i+1}] {fact.subject.name} -> {fact.predicate} -> {val_str}{time_str}{scope_str}{qual_str}")
        print(f"    Evidence IDs: {fact.evidence_ids} | Conf: {fact.confidence:.2f}")
    if len(result.facts) > 15:
        print(f"... and {len(result.facts) - 15} more facts.")
    print()

def process_canonical_file(service: FactExtractionService, json_path: Path, inspect: bool):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            doc_dict = json.load(f)
        doc = CanonicalDocument.model_validate(doc_dict)
        
        result = service.extract(doc)
        
        if inspect:
            inspect_facts(result)
        else:
            print(f"Document: {json_path.name}")
            print(f"Document ID: {result.document_id}")
            print(f"Candidates: {result.statistics.candidate_count}")
            print(f"Facts extracted & deduplicated: {len(result.facts)}")
            print(f"Results saved to: {service.output_dir / f'{result.document_id}.json'}\n")
        return True, None
    except Exception as e:
        print(f"Failed to extract from {json_path.name}: {e}\n")
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Superjoin Fact Layer - Module 2: Fact Extraction")
    parser.add_argument("--input", type=str, required=True, help="Path to a canonical JSON file or directory of JSONs")
    parser.add_argument("--output", type=str, default="data/facts", help="Output directory for extracted facts")
    parser.add_argument("--inspect", action="store_true", help="Print detailed factual breakdown")
    parser.add_argument("--model", type=str, default="gemini-1.5-flash", help="LLM model name")

    args = parser.parse_args()

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')

    input_path = Path(args.input)
    output_dir = Path(args.output)
    
    llm_provider = DefaultLLMProvider(model_name=args.model)
    service = FactExtractionService(llm_client=llm_provider, output_dir=str(output_dir))

    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        sys.exit(1)

    if input_path.is_file():
        process_canonical_file(service, input_path, args.inspect)
    elif input_path.is_dir():
        json_files = list(input_path.glob("*.json"))
        print(f"Found {len(json_files)} canonical JSON documents in {input_path}\n")

        success_count = 0
        failures = []

        for jf in json_files:
            success, err = process_canonical_file(service, jf, args.inspect)
            if success:
                success_count += 1
            else:
                failures.append((jf.name, err))

        print(f"Processed: {success_count}")
        print(f"Failed: {len(failures)}")
        if failures:
            print("\nFailures:")
            for name, err in failures:
                print(f"- {name}: {err}")

if __name__ == "__main__":
    main()
