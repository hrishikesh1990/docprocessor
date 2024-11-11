import fitz
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
import re
from enum import Enum
from typing import Tuple, Dict, List
import docx
from .link_extractor import LinkExtractor
import logging

logger = logging.getLogger(__name__)

class ExtractionMethod(Enum):
    PYMUPDF = "pymupdf"
    OCR = "ocr"
    DOCX = "docx"

class DocumentProcessor:
    def __init__(self, file_bytes: bytes, mime_type: str):
        self.file_bytes = file_bytes
        self.mime_type = mime_type
        self.url_patterns = {
            'linkedin': r'https?://(?:www\.)?linkedin\.com/\S+',
            'github': r'https?://(?:www\.)?github\.com/\S+',
            'stackoverflow': r'https?://(?:www\.)?stackoverflow\.com/\S+'
        }

    def process(self) -> Tuple[str, ExtractionMethod]:
        """Process the document and return extracted text and method used"""
        if self.mime_type.startswith('image/'):
            return self._process_image(), ExtractionMethod.OCR
        elif self.mime_type == 'application/pdf':
            return self._process_pdf()
        elif self.mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return self._process_doc()
        else:
            raise ValueError(f"Unsupported file type: {self.mime_type}")

    def _process_image(self) -> str:
        """Process image files using OCR"""
        image = Image.open(io.BytesIO(self.file_bytes))
        return pytesseract.image_to_string(image)

    def _is_garbage_text(self, text: str) -> bool:
        """
        Check if the extracted text appears to be garbage.
        Returns True if the text contains too many unprintable characters or unusual patterns.
        """
        if not text:
            return True
        
        # Calculate the ratio of unprintable characters
        unprintable_chars = sum(1 for c in text if not c.isprintable() and not c.isspace())
        total_chars = len(text)
        
        if total_chars == 0:
            return True
        
        unprintable_ratio = unprintable_chars / total_chars
        
        # If more than 15% of characters are unprintable, consider it garbage
        if unprintable_ratio > 0.15:
            return True
        
        # Check if text contains actual words (at least some alphabetic characters)
        alphabetic_chars = sum(1 for c in text if c.isalpha())
        alphabetic_ratio = alphabetic_chars / total_chars
        
        # If less than 20% of characters are letters, likely garbage
        if alphabetic_ratio < 0.20:
            return True
        
        return False

    def _process_pdf(self) -> Tuple[str, ExtractionMethod]:
        """Process PDF files"""
        try:
            # Try PyMuPDF first
            doc = fitz.open(stream=self.file_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            
            # Check if the extracted text is valid
            if text.strip() and not self._is_garbage_text(text):
                return text, ExtractionMethod.PYMUPDF
                
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {str(e)}", exc_info=True)
        
        # Fall back to OCR
        try:
            logger.info("Attempting OCR extraction")
            logger.info("Converting PDF to images...")
            
            # Add debugging for PDF content
            logger.info(f"PDF bytes length: {len(self.file_bytes)}")
            
            try:
                # Try to open PDF with PyMuPDF to check validity
                doc = fitz.open(stream=self.file_bytes, filetype="pdf")
                logger.info(f"PDF has {len(doc)} pages")
            except Exception as pdf_error:
                logger.error(f"Failed to validate PDF: {str(pdf_error)}")
            
            # Try conversion with explicit DPI
            images = convert_from_bytes(
                self.file_bytes,
                dpi=300,  # Explicit DPI setting
                fmt='jpeg',  # Use JPEG format
                output_folder=None,  # Keep in memory
                paths_only=False,
                poppler_path=None  # Let it find poppler automatically
            )
            
            if not images:
                raise Exception("PDF to image conversion produced no images")
                
            logger.info(f"Successfully converted PDF to {len(images)} images")
            
            text = ""
            for i, image in enumerate(images):
                try:
                    logger.info(f"Processing page {i+1} with OCR...")
                    # Save image quality and DPI info for debugging
                    logger.info(f"Image size: {image.size}, mode: {image.mode}")
                    page_text = pytesseract.image_to_string(image)
                    
                    if not page_text.strip():
                        logger.warning(f"No text extracted from page {i+1}")
                    else:
                        logger.info(f"Successfully extracted {len(page_text)} characters from page {i+1}")
                    
                    text += page_text + "\n"
                    
                except Exception as page_error:
                    logger.error(f"Failed to OCR page {i+1}: {str(page_error)}", exc_info=True)
            
            if not text.strip():
                logger.error("OCR extraction produced no text for any page")
                # Try with different image parameters
                logger.info("Retrying with different image parameters...")
                text = ""
                for i, image in enumerate(images):
                    try:
                        # Convert to grayscale and enhance contrast
                        gray_image = image.convert('L')
                        page_text = pytesseract.image_to_string(
                            gray_image,
                            config='--psm 1 --oem 3'  # Use more aggressive OCR settings
                        )
                        text += page_text + "\n"
                        logger.info(f"Retry: Extracted {len(page_text)} characters from page {i+1}")
                    except Exception as retry_error:
                        logger.error(f"Retry failed for page {i+1}: {str(retry_error)}", exc_info=True)
            
            final_text = text.strip()
            if not final_text:
                raise Exception("OCR extraction produced no text after all attempts")
                
            return final_text, ExtractionMethod.OCR
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}", exc_info=True)
            raise Exception(f"Failed to extract text from PDF: {str(e)}")

    def _process_doc(self) -> Tuple[str, ExtractionMethod]:
        """Process DOC/DOCX files"""
        try:
            # Load the document from bytes
            doc = docx.Document(io.BytesIO(self.file_bytes))
            
            # Extract text from paragraphs
            text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():  # Only add non-empty paragraphs
                    text.append(paragraph.text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():  # Only add non-empty cells
                            text.append(cell.text)
            
            # Join all text with newlines
            full_text = '\n'.join(text)
            
            # If we got meaningful text, return it
            if full_text.strip():
                return full_text, ExtractionMethod.PYMUPDF  # Using PYMUPDF as method for now
            
            # If no text was extracted, try OCR as fallback
            return self._convert_to_pdf_and_process()
            
        except Exception as e:
            # If DOCX processing fails, try converting to PDF
            return self._convert_to_pdf_and_process()

    def _convert_to_pdf_and_process(self) -> Tuple[str, ExtractionMethod]:
        """
        Convert DOC/DOCX to PDF using LibreOffice and then process.
        Requires LibreOffice to be installed.
        """
        try:
            import subprocess
            import tempfile
            import os
            
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_doc:
                temp_doc.write(self.file_bytes)
                temp_doc_path = temp_doc.name
            
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
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            process.wait()
            
            # Read the converted PDF
            if os.path.exists(temp_pdf_path):
                with open(temp_pdf_path, 'rb') as pdf_file:
                    pdf_bytes = pdf_file.read()
                
                # Clean up temporary files
                os.unlink(temp_doc_path)
                os.unlink(temp_pdf_path)
                
                # Process the PDF
                self.file_bytes = pdf_bytes
                self.mime_type = 'application/pdf'
                return self._process_pdf()
            
            raise Exception("PDF conversion failed")
            
        except Exception as e:
            # If conversion fails, fall back to OCR
            try:
                images = convert_from_bytes(self.file_bytes)
                text = ""
                for image in images:
                    text += pytesseract.image_to_string(image) + "\n"
                return text.strip(), ExtractionMethod.OCR
            except Exception as ocr_error:
                raise Exception(f"Failed to process document: {str(ocr_error)}")

    def extract_links(self) -> dict:
        """Extract all links from the document"""
        if self.mime_type != 'application/pdf':
            return {
                'web_links': [],
                'linkedin': [],
                'github': [],
                'stackoverflow': [],
                'email': [],
                'annotation': []
            }
        
        try:
            # Get text content (use the already extracted text if available)
            if hasattr(self, '_extracted_text'):
                extracted_text = self._extracted_text
            else:
                extracted_text, _ = self.process()
            
            return LinkExtractor.extract_all_links(self.file_bytes, extracted_text)
            
        except Exception as e:
            print(f"Error extracting links: {str(e)}")
            return {
                'web_links': [],
                'linkedin': [],
                'github': [],
                'stackoverflow': [],
                'email': [],
                'annotation': []
            }

    @staticmethod
    def extract_all_links(pdf_file, extracted_text):
        """Extract both annotation and text-based links"""
        all_links = []
        
        # Get annotation links
        annotation_links = LinkExtractor.extract_annotations_with_pymupdf(pdf_file)
        all_links.extend(annotation_links)
        
        # Get text-based links
        text_links = LinkExtractor.extract_links_from_text(extracted_text)
        all_links.extend(text_links)

        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in all_links:
            uri = link['uri']
            if uri not in seen:
                seen.add(uri)
                unique_links.append(link)

        # Group links by type
        grouped_links = {
            'web_links': [],
            'linkedin': [],
            'github': [],
            'stackoverflow': [],
            'email': [],
            'annotation': []
        }

        for link in unique_links:
            link_type = link['type']
            if link_type in grouped_links:
                grouped_links[link_type].append(link['uri'])
            else:
                grouped_links['web_links'].append(link['uri'])

        return grouped_links