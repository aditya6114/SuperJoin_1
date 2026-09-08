class InvalidDocumentError(Exception):
    """Raised when a document fails initial validation (e.g. not a PDF, empty, non-existent)."""
    pass

class DocumentParsingError(Exception):
    """Raised when the document cannot be parsed by the underlying parser (e.g. corrupted PDF, protected)."""
    pass
