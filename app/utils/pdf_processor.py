import pymupdf as fitz
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
import re

class PDFProcessor:
    def __init__(self, pdf_bytes: bytes):
        self.pdf_bytes = pdf_bytes
        self.url_patterns = {
            'linkedin': r'https?://(?:www\.)?linkedin\.com/\S+',
            'github': r'https?://(?:www\.)?github\.com/\S+',
            'stackoverflow': r'https?://(?:www\.)?stackoverflow\.com/\S+'
        }

    def extract_text_pymupdf(self) -> str:
        doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text

    def extract_text_pdfplumber(self) -> str:
        with pdfplumber.open(io.BytesIO(self.pdf_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text

    def extract_text_ocr_direct(self) -> str:
        """Extract text using OCR directly from PDF"""
        doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
        text = ""
        
        for page in doc:
            # Get the page as an image
            pix = page.get_pixmap()
            # Convert PyMuPDF pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            # Extract text using OCR
            text += pytesseract.image_to_string(img) + "\n"
        
        return text

    def extract_text_ocr_from_images(self) -> str:
        """Extract text using OCR after converting PDF to images using pdf2image"""
        images = convert_from_bytes(self.pdf_bytes)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
        return text

    def extract_links(self) -> dict:
        doc = fitz.open(stream=self.pdf_bytes, filetype="pdf")
        links = {
            'text_links': set(),
            'annotation_links': set(),
            'linkedin_links': set(),
            'github_links': set(),
            'stackoverflow_links': set()
        }
        
        # Extract text and annotation links
        for page in doc:
            # Get text links
            text = page.get_text()
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
            links['text_links'].update(urls)
            
            # Get annotation links
            for annot in page.annots():
                if annot.type[0] == 8:  # Link annotation
                    uri = annot.uri
                    if uri:
                        links['annotation_links'].add(uri)
        
        # Categorize links by platform
        all_links = links['text_links'].union(links['annotation_links'])
        for link in all_links:
            for platform, pattern in self.url_patterns.items():
                if re.match(pattern, link):
                    links[f'{platform}_links'].add(link)
        
        # Convert sets to lists for JSON serialization
        return {k: list(v) for k, v in links.items()} 