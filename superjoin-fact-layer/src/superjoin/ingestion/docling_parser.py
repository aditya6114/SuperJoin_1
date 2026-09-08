from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.document import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from .exceptions import DocumentParsingError

class DoclingDocumentParser:
    def __init__(self):
        try:
            # Disable OCR by default to speed up parsing on native PDFs
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            
            # Additional optimizations: skip generating images of the document pages
            pipeline_options.images_scale = 1.0 
            pipeline_options.generate_page_images = False
            
            self.converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        except Exception as e:
            raise DocumentParsingError(f"Failed to initialize Docling parser: {e}")

    def parse(self, pdf_path: Path):
        try:
            result = self.converter.convert(pdf_path)
            return result.document
        except Exception as e:
            raise DocumentParsingError(f"Docling failed to parse {pdf_path}: {e}")
