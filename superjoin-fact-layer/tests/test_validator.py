import pytest
from pathlib import Path
from superjoin.ingestion.validator import validate_pdf, generate_document_id
from superjoin.ingestion.exceptions import InvalidDocumentError

def test_validate_pdf_not_exist():
    with pytest.raises(InvalidDocumentError, match="File does not exist"):
        validate_pdf(Path("does_not_exist.pdf"))

def test_validate_pdf_empty(tmp_path):
    empty_file = tmp_path / "empty.pdf"
    empty_file.touch()
    with pytest.raises(InvalidDocumentError, match="File is empty"):
        validate_pdf(empty_file)

def test_validate_pdf_bad_signature(tmp_path):
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_text("This is not a PDF")
    with pytest.raises(InvalidDocumentError, match="File signature is not PDF"):
        validate_pdf(bad_pdf)

def test_validate_pdf_valid(tmp_path):
    valid_pdf = tmp_path / "valid.pdf"
    valid_pdf.write_bytes(b"%PDF-1.4\nSome content")
    # Should not raise
    validate_pdf(valid_pdf)

def test_generate_document_id():
    path = Path("/some/dir/Delhivery-Annual-Report-FY24.pdf")
    sha256_hash = "a81c92a9b3d4f1"
    doc_id = generate_document_id(path, sha256_hash)
    assert doc_id == "delhivery-annual-report-fy24-a81c92"
