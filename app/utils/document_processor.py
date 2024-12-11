from enum import Enum
import fitz
import logging
from typing import Tuple
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import docx
import io
import os
import tempfile
import subprocess
import re

logger = logging.getLogger(__name__)

class ExtractionMethod(Enum):
    OCR = "ocr"
    PYMUPDF = "pymupdf"
    DOCX = "docx"

class DocumentProcessor:
    def __init__(self, file_bytes: bytes, mime_type: str):
        self.file_bytes = file_bytes
        self.mime_type = mime_type
        self._extracted_text = None
        self._extraction_method = None

    def process(self) -> Tuple[str, ExtractionMethod]:
        """Process the document and return extracted text and method used"""
        if self._extracted_text is not None:
            return self._extracted_text, self._extraction_method

        extraction_errors = []

        # Try OCR first for all file types
        try:
            logger.info("Attempting OCR extraction as primary method")
            self._extracted_text, self._extraction_method = self._process_ocr()
            if self._extracted_text.strip():
                return self._extracted_text, self._extraction_method
        except Exception as e:
            error_msg = f"OCR extraction failed: {str(e)}"
            logger.error(error_msg)
            extraction_errors.append(error_msg)

        # Format-specific fallbacks with detailed errors
        if self.mime_type == 'application/pdf':
            try:
                logger.info("Attempting PyMuPDF extraction for PDF")
                self._extracted_text, self._extraction_method = self._process_pymupdf()
                if self._extracted_text.strip():
                    return self._extracted_text, self._extraction_method
                else:
                    error_msg = "PyMuPDF extraction produced empty text"
                    logger.error(error_msg)
                    extraction_errors.append(error_msg)
            except Exception as e:
                error_msg = f"PyMuPDF extraction failed: {str(e)}"
                logger.error(error_msg)
                extraction_errors.append(error_msg)

        elif self.mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            try:
                logger.info("Attempting DOCX extraction")
                self._extracted_text, self._extraction_method = self._process_docx()
                if self._extracted_text.strip():
                    return self._extracted_text, self._extraction_method
                else:
                    error_msg = "DOCX extraction produced empty text"
                    logger.error(error_msg)
                    extraction_errors.append(error_msg)
            except Exception as e:
                error_msg = f"DOCX extraction failed: {str(e)}"
                logger.error(error_msg)
                extraction_errors.append(error_msg)

            try:
                logger.info("Attempting PyMuPDF extraction for DOC/DOCX")
                self._extracted_text, self._extraction_method = self._process_pymupdf()
                if self._extracted_text.strip():
                    return self._extracted_text, self._extraction_method
                else:
                    error_msg = "PyMuPDF extraction produced empty text"
                    logger.error(error_msg)
                    extraction_errors.append(error_msg)
            except Exception as e:
                error_msg = f"PyMuPDF extraction failed: {str(e)}"
                logger.error(error_msg)
                extraction_errors.append(error_msg)

        # If all methods fail, raise a detailed error
        error_summary = " | ".join(extraction_errors)
        raise ValueError(f"All extraction methods failed. Details: {error_summary}")

    def _process_ocr(self) -> Tuple[str, ExtractionMethod]:
        """Extract text using OCR"""
        logger.info("Converting document to images...")
        
        # For DOC/DOCX, convert to PDF first
        if self.mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            pdf_bytes = self._convert_to_pdf()
        else:
            pdf_bytes = self.file_bytes

        # Convert PDF to images
        images = convert_from_bytes(
            pdf_bytes,
            dpi=150,
            fmt='jpeg',
            size=(2000, None)  # Limit width to 2000 pixels
        )

        if not images:
            raise Exception("Document to image conversion produced no images")

        logger.info(f"Successfully converted document to {len(images)} images")
        text = ""

        for i, image in enumerate(images):
            try:
                logger.info(f"Processing page {i+1} with OCR...")
                # Resize if image is too large
                max_dimension = 4000
                if max(image.size) > max_dimension:
                    ratio = max_dimension / max(image.size)
                    new_size = tuple(int(dim * ratio) for dim in image.size)
                    image = image.resize(new_size, Image.Resampling.LANCZOS)

                page_text = pytesseract.image_to_string(image)
                text += page_text + "\n"
            except Exception as e:
                logger.error(f"Failed to OCR page {i+1}: {str(e)}")

        if not text.strip():
            raise Exception("OCR extraction produced no text")

        return text.strip(), ExtractionMethod.OCR

    def _process_pymupdf(self) -> Tuple[str, ExtractionMethod]:
        """Extract text using PyMuPDF"""
        if self.mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            pdf_bytes = self._convert_to_pdf()
        else:
            pdf_bytes = self.file_bytes

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()

        if not text.strip():
            raise Exception("PyMuPDF extraction produced no text")

        return text.strip(), ExtractionMethod.PYMUPDF

    def _process_docx(self) -> Tuple[str, ExtractionMethod]:
        """Extract text from DOCX using python-docx"""
        doc = docx.Document(io.BytesIO(self.file_bytes))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        
        if not text.strip():
            raise Exception("DOCX extraction produced no text")

        return text.strip(), ExtractionMethod.DOCX

    def _convert_to_pdf(self) -> bytes:
        """Convert DOC/DOCX to PDF using LibreOffice"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_doc:
            temp_doc.write(self.file_bytes)
            temp_doc_path = temp_doc.name

        try:
            temp_pdf_path = temp_doc_path.replace('.docx', '.pdf')
            
            # Convert to PDF using LibreOffice
            process = subprocess.Popen([
                'soffice',
                '--headless',
                '--convert-to',
                'pdf',
                '--outdir',
                os.path.dirname(temp_pdf_path),
                temp_doc_path
            ])
            process.wait()

            # Read the converted PDF
            with open(temp_pdf_path, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()

            return pdf_bytes

        finally:
            # Clean up temporary files
            if os.path.exists(temp_doc_path):
                os.unlink(temp_doc_path)
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)

    def extract_links(self) -> dict:
        """Extract links from the document"""
        if self.mime_type != 'application/pdf':
            return {
                'web_links': [],
                'linkedin_links': [],
                'github_links': [],
                'stackoverflow_links': [],
                'email_links': [],
                'text_links': [],
                'annotation_links': []
            }
        
        try:
            # Initialize links dictionary with sets
            links = {
                'web_links': set(),
                'linkedin_links': set(),
                'github_links': set(),
                'stackoverflow_links': set(),
                'email_links': set(),
                'text_links': set(),
                'annotation_links': set()
            }
            
            # Open PDF and extract links
            doc = fitz.open(stream=self.file_bytes, filetype="pdf")
            for page in doc:
                # Get all links from the page
                for link in page.get_links():
                    if 'uri' in link:  # Check if it's a URL link
                        uri = link['uri']
                        links['annotation_links'].add(uri)
                        
                        # Categorize the link
                        uri_lower = uri.lower()
                        if 'linkedin.com' in uri_lower:
                            links['linkedin_links'].add(uri)
                        elif 'github.com' in uri_lower:
                            links['github_links'].add(uri)
                        elif 'stackoverflow.com' in uri_lower:
                            links['stackoverflow_links'].add(uri)
                        else:
                            links['web_links'].add(uri)
                        
                # Extract any email addresses from text
                text = page.get_text()
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                links['email_links'].update(emails)
            
            doc.close()
            
            # Convert sets to lists for JSON serialization
            return {k: list(v) for k, v in links.items()}
            
        except Exception as e:
            logger.error(f"Error extracting links: {str(e)}", exc_info=True)
            return {
                'web_links': [],
                'linkedin_links': [],
                'github_links': [],
                'stackoverflow_links': [],
                'email_links': [],
                'text_links': [],
                'annotation_links': []
            }