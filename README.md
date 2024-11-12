# Document Processing API

A FastAPI-based service for extracting text and links from documents (PDF, DOC, DOCX).

## Features
### Text Extraction
- Primary method: OCR for all documents
- Fallback methods:
  - PDF: PyMuPDF
  - DOC/DOCX: docx library → PyMuPDF
- Image preprocessing for better OCR results
- Memory-efficient processing of large documents

### Link Extraction (PDF only)
- Embedded/clickable links
- URLs in text
- Email addresses
- Categorized by platform (LinkedIn, GitHub, Stack Overflow)

## API Reference

### Process Document
**Endpoint:**

```
POST /process-document/
```

**Headers:**

```
Content-Type: multipart/form-data
```

#### Request
Either provide a file upload or URL:
- `file`: Binary file upload
- `url`: String URL to document

Supported formats:
- PDF
- DOC/DOCX
- Images (JPEG, PNG, TIFF)

#### Response
```json
{
"filename": "example.pdf",
"content_type": "application/pdf",
"detected_mime_type": "application/pdf",
"extraction_method": "ocr",
"extracted_text": "Sample extracted text...",
"links": {
"web_links": ["https://example.com"],
"linkedin_links": ["https://linkedin.com/in/user"],
"github_links": ["https://github.com/user"],
"stackoverflow_links": [],
"email_links": ["user@example.com"],
"text_links": [],
"annotation_links": ["https://example.com"]
    }
}   
```
## Technical Details

### Text Extraction Flow
1. **OCR Processing (Primary)**
   - Convert document to images
   - Optimize image size for OCR
   - Process with Tesseract OCR
   
2. **Format-Specific Fallbacks**
   - PDF: PyMuPDF text extraction
   - DOC/DOCX: 
     1. Native docx library
     2. Convert to PDF → PyMuPDF

### Link Extraction Flow
1. Extract embedded links using PyMuPDF
2. Parse text for URLs and email addresses
3. Categorize links by platform
4. Remove duplicates
5. Convert to JSON-serializable format

### Installation
#### Install dependencies
```
pip install -r requirements.txt
```
#### Set API key:
```
export API_KEY="your-api-key"
```
#### Install system packages
```
apt-get install tesseract-ocr
apt-get install libreoffice
```
#### Start server
```
uvicorn app.main:app --reload
```

## Error Handling
- Detailed logging of processing steps
- Graceful fallbacks for extraction methods
- Proper cleanup of temporary files
- Comprehensive error messages in API responses

### Prerequisites
- Python 3.8+
- Tesseract OCR
- LibreOffice (for DOC/DOCX conversion)

### Installation

## Processing Flow
1. Document Upload
   - Accept file upload or URL
   - Verify MIME type
2. Text Extraction
   - Primary: OCR for all documents
   - Fallback for PDFs: PyMuPDF
   - Fallback for DOC/DOCX: docx library → PyMuPDF
3. Link Extraction (PDFs only)
   - Extract embedded links using PyMuPDF
   - Categorize links by platform
   - Extract email addresses
