import argparse
import sys
from pathlib import Path
from .service import DocumentIngestionService
from .exceptions import InvalidDocumentError, DocumentParsingError
from .models import CanonicalTable, CanonicalFigure

def inspect_document(doc):
    print(f"\nDocument: {doc.metadata.filename}")
    print(f"Pages: {doc.metadata.page_count}")
    
    total_elements = sum(len(p.elements) for p in doc.pages)
    tables = sum(1 for p in doc.pages for e in p.elements if isinstance(e, CanonicalTable))
    figures = sum(1 for p in doc.pages for e in p.elements if isinstance(e, CanonicalFigure))
    paragraphs = sum(1 for p in doc.pages for e in p.elements if e.type == 'paragraph')
    footnotes = sum(1 for p in doc.pages for e in p.elements if e.type == 'footnote')
    headers = sum(1 for p in doc.pages for e in p.elements if e.type == 'page_header')
    footers = sum(1 for p in doc.pages for e in p.elements if e.type == 'page_footer')
    unknown = sum(1 for p in doc.pages for e in p.elements if e.type == 'unknown')
    
    print(f"Canonical elements: {total_elements}")
    print(f"Tables: {tables}")
    print(f"Figures: {figures}")
    print(f"Paragraphs: {paragraphs}")
    print(f"Footnotes: {footnotes}")
    print(f"Headers: {headers}")
    print(f"Footers: {footers}")
    print(f"Unknown: {unknown}\n")
    
    for page in doc.pages:
        print(f"Page {page.pdf_page_number} (Printed: {page.printed_page_number})")
        print("-" * 25)
        for i, el in enumerate(page.elements):
            if isinstance(el, CanonicalTable):
                print(f"[{el.canonical_order}] table")
                print(f"    Caption: {el.caption}")
                print(f"    Columns: {len(el.headers)}")
                print(f"    Rows: {len(el.rows)}")
                print(f"    Source: {el.source}")
                print(f"    Evidence: {el.evidence_ids}")
            elif isinstance(el, CanonicalFigure):
                print(f"[{el.canonical_order}] figure")
                print(f"    Evidence: {el.evidence_ids}")
            else:
                text_preview = el.content[:50] + "..." if len(el.content) > 50 else el.content
                print(f"[{el.canonical_order}] {el.type} - {text_preview}")
        print()

def process_file(service: DocumentIngestionService, pdf_path: Path, output_dir: Path, inspect: bool):
    try:
        doc = service.ingest(pdf_path)
        out_path = service.save(doc, output_dir)
        
        if inspect:
            inspect_document(doc)
        else:
            print(f"Document: {pdf_path.name}")
            print(f"Document ID: {doc.metadata.document_id}")
            print(f"Status: success")
            print(f"Output saved to: {out_path}\n")
        return True, None
    except (InvalidDocumentError, DocumentParsingError) as e:
        print(f"Failed to process {pdf_path.name}: {e}\n")
        return False, str(e)
    except Exception as e:
        print(f"Unexpected error processing {pdf_path.name}: {e}\n")
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Superjoin Fact Layer - Module 1: Document Ingestion")
    parser.add_argument("--input", type=str, required=True, help="Path to a PDF file or directory of PDFs")
    parser.add_argument("--output", type=str, default="data/parsed", help="Output directory for JSON files")
    parser.add_argument("--inspect", action="store_true", help="Print structural overview of the canonical document")
    
    args = parser.parse_args()
    
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
        
    input_path = Path(args.input)
    output_dir = Path(args.output)
    
    service = DocumentIngestionService()
    
    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        sys.exit(1)
        
    if input_path.is_file():
        process_file(service, input_path, output_dir, args.inspect)
    elif input_path.is_dir():
        pdfs = list(input_path.rglob("*.pdf"))
        print(f"Found {len(pdfs)} PDFs in {input_path}\n")
        
        success_count = 0
        failures = []
        
        for pdf in pdfs:
            success, error_msg = process_file(service, pdf, output_dir, args.inspect)
            if success:
                success_count += 1
            else:
                failures.append((pdf.name, error_msg))
                
        print(f"Processed: {success_count}")
        print(f"Failed: {len(failures)}")
        
        if failures:
            print("\nFailures:")
            for name, err in failures:
                print(f"- {name}: {err}")
    else:
        print("Input is neither a file nor a directory.")
        sys.exit(1)

if __name__ == "__main__":
    main()
