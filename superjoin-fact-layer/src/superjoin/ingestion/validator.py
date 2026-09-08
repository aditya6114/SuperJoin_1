import os
import hashlib
from pathlib import Path
from .exceptions import InvalidDocumentError

def validate_pdf(path: Path) -> None:
    """Validates that a path points to a valid PDF file."""
    if not path.exists():
        raise InvalidDocumentError(f"File does not exist: {path}")
    
    if not path.is_file():
        raise InvalidDocumentError(f"Path is not a regular file: {path}")
    
    if path.stat().st_size == 0:
        raise InvalidDocumentError(f"File is empty: {path}")
    
    try:
        with open(path, 'rb') as f:
            header = f.read(5)
            if header != b'%PDF-':
                raise InvalidDocumentError(f"File signature is not PDF: {path}")
    except IOError as e:
        raise InvalidDocumentError(f"Could not read file: {path} - {e}")

def generate_document_id(path: Path, sha256_hash: str) -> str:
    """Generates a deterministic document ID from filename and hash."""
    import re
    # Clean the filename: lowercase, replace non-alphanumeric with hyphens
    basename = path.stem.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', basename).strip('-')
    
    # Use first 6 chars of hash
    short_hash = sha256_hash[:6]
    
    return f"{slug}-{short_hash}"

def calculate_sha256(path: Path) -> str:
    """Calculates the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        # Read in chunks for memory efficiency
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
