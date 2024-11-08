# app/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from typing import Dict, Any, Optional
import magic
import httpx
from .utils.pdf_processor import PDFProcessor

app = FastAPI(
    title="Document Processor",
    description="API for processing documents and extracting text",
    version="1.0.0"
)

@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "running"}

@app.post("/process-pdf/")
async def process_pdf(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
) -> Dict[str, Any]:
    if not file and not url:
        raise HTTPException(
            status_code=400,
            detail="Either file or url must be provided"
        )
    
    try:
        # Handle URL input
        if url:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not download file from URL"
                    )
                content = response.content
                filename = url.split('/')[-1]
                content_type = response.headers.get('content-type', '')
        # Handle file upload
        else:
            content = await file.read()
            filename = file.filename
            content_type = file.content_type
        
        # Verify file is PDF
        mime_type = magic.from_buffer(content, mime=True)
        if mime_type != 'application/pdf':
            raise HTTPException(
                status_code=400,
                detail="File must be a PDF"
            )
        
        # Process PDF
        processor = PDFProcessor(content)
        
        return {
            "filename": filename,
            "content_type": content_type,
            "extracted_text": {
                "pymupdf": processor.extract_text_pymupdf(),
                "pdfplumber": processor.extract_text_pdfplumber(),
                "ocr": {
                    "direct_pdf": processor.extract_text_ocr_direct(),
                    "from_images": processor.extract_text_ocr_from_images()
                }
            },
            "links": processor.extract_links()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))