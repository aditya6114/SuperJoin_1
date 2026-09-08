# Superjoin Fact Knowledge Layer — Module 1

## Module 1 Responsibility
This project implements **Module 1: Document Ingestion, Parsing & Canonicalization** of the Superjoin Fact Knowledge Layer.

It accepts arbitrary PDFs, leverages Docling as the primary parsing engine, and converts the raw Docling outputs into a clean, deterministic, provenance-preserving `CanonicalDocument`. This document model acts as the exclusive ingestion boundary, meaning that downstream modules (like LLM Fact Extraction in Module 2) consume canonical data without needing to know anything about Docling or PDF coordinate structures.

## Architecture
```text
PDF
 ↓
DocumentParser interface
 ↓
DoclingDocumentParser
 ↓
RawParseResult (adapter pattern preventing Docling leakage)
 ↓
Canonicalizer (Normalizes text, geometry, reading order, and tables)
 ↓
CanonicalDocument
 ↓
persist/cache (JSON)
 ↓
Module 2 (Future)
```

## Why Docling?
Docling provides sophisticated raw document parsing (including OCR, table boundary recognition, and image classification) out of the box. Instead of writing custom PDF geometry extraction logic, we leverage Docling for low-level structure recognition.

## Why a Canonicalization Layer?
While Docling is powerful, its native order fields sometimes disagree with visual reading order, its text outputs may contain invisible control characters, and its table headers are occasionally merged with captions. The Canonicalizer performs semantic reconstruction (like geometry-based reading order mapping) and cleans textual artifacts to provide a predictable standard schema for down-stream reasoning tasks.

## Schema Highlights
- **CanonicalDocument**: The stable top-level container preserving document hash and metadata.
- **CanonicalPage**: 1-indexed representations mapping `pdf_page_number` and resolving embedded `printed_page_number`.
- **Provenance**: Every `CanonicalElement` preserves an `evidence_ids` array, allowing downstream extraction to perfectly map any extracted fact back to exact bounding boxes and original Docling blocks.
- **Reading Order Strategy**: Elements are clustered by X-coordinate to infer column structure, then sorted top-to-bottom via Y-coordinates, ensuring multi-column PDFs read logically.
- **Table Normalization Strategy**: Custom rules parse out embedded captions (e.g. `Table IV.1: Title`) into distinct `caption` fields and strip repetitive `Source:` rows into dedicated table metadata properties.

## Installation
Ensure you have Python 3.11+ installed.

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Usage (Running Ingestion)
Parse a directory of PDFs:
```bash
python scripts/parse_documents.py --input data/input --output data/parsed
```

### Inspect Output Structure
Run the CLI in `--inspect` mode to print a debugging overview of the semantic hierarchy without printing massive walls of raw text:
```bash
python scripts/parse_documents.py --input data/input/sample.pdf --inspect
```

## Running Tests
Run the deterministic verification tests covering table captions, geometry sorting, and control character cleanup:
```bash
pytest tests/
```

## Known Limitations
- Docling's `RapidOCR` dependencies are currently massive (multiple GBs of HuggingFace models), significantly increasing the cold-start time of parsing.
- "Unknown" elements or fragmented text blocks from charts are conservatively captured rather than semantically understood. Full chart data understanding is left for future modules.
- Nested sub-tables might occasionally flatten into their parent cells depending on Docling's confidence thresholds.

## Boundary Definition
Module 1 creates the semantic scaffolding. **Module 2 (LLM Fact Extraction)** will ingest the `data/parsed/*.json` canonical documents to perform reasoning and extraction. No Module 2 logic currently resides in this repository.
