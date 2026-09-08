import json
from pathlib import Path
import docling

from .validator import validate_pdf, calculate_sha256, generate_document_id
from .docling_parser import DoclingDocumentParser
from .canonicalizer import Canonicalizer
from .models import DocumentMetadata, CanonicalDocument, RawParseResult

class DocumentIngestionService:
    def __init__(self):
        self.parser = DoclingDocumentParser()
        self.canonicalizer = Canonicalizer()

    def ingest(self, pdf_path: Path) -> CanonicalDocument:
        # Validate
        validate_pdf(pdf_path)
        
        # Identity
        sha256_hash = calculate_sha256(pdf_path)
        doc_id = generate_document_id(pdf_path, sha256_hash)
        
        # Parse
        docling_doc = self.parser.parse(pdf_path)
        
        # Meta
        metadata = DocumentMetadata(
            document_id=doc_id,
            filename=pdf_path.name,
            page_count=len(docling_doc.pages) if hasattr(docling_doc, 'pages') else 0,
            parser="docling",
            parser_version=getattr(docling, '__version__', 'unknown'),
            file_size_bytes=pdf_path.stat().st_size,
            sha256=sha256_hash,
            title=pdf_path.stem,
            processing_status="success"
        )
        
        raw_result = RawParseResult(
            docling_document=docling_doc,
            metadata=metadata
        )
        
        # Normalize to Canonical
        canonical_doc = self.canonicalizer.canonicalize(raw_result)
        return canonical_doc

    def save(self, doc: CanonicalDocument, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{doc.metadata.document_id}.json"
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(doc.model_dump_json(indent=2))
        
        return out_path
