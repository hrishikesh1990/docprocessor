# app/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Security
from typing import Dict, Any, Optional
import magic
import httpx
import logging
from app.utils.document_processor import DocumentProcessor, ExtractionMethod
from app.auth.auth_handler import get_api_key

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document Processor",
    description="API for processing documents and extracting text",
    version="1.0.0"
)

SUPPORTED_MIME_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/tiff',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "running"}

@app.post("/process-document/")
async def process_document(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    api_key: str = Security(get_api_key)
) -> Dict[str, Any]:
    logger.info(f"Received request - file: {file}, url: {url}")
    
    if not file and not url:
        raise HTTPException(
            status_code=400,
            detail="Either file or url must be provided"
        )
    
    try:
        # Handle URL input
        if url:
            logger.info(f"Processing URL: {url}")
            async with httpx.AsyncClient(verify=False) as client:  # Added verify=False for testing
                response = await client.get(url)
                logger.info(f"URL response status: {response.status_code}")
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not download file from URL. Status code: {response.status_code}"
                    )
                content = response.content
                filename = url.split('/')[-1].split('?')[0]  # Clean up filename
                content_type = response.headers.get('content-type', '')
                logger.info(f"Downloaded file: {filename}, content-type: {content_type}")
        # Handle file upload
        else:
            content = await file.read()
            filename = file.filename
            content_type = file.content_type
            logger.info(f"Processing uploaded file: {filename}, content-type: {content_type}")

        # Verify file type
        mime_type = magic.from_buffer(content, mime=True)
        logger.info(f"Detected MIME type: {mime_type}")
        
        if mime_type not in SUPPORTED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {mime_type}. Supported types: {', '.join(SUPPORTED_MIME_TYPES)}"
            )
        
        # Process document
        processor = DocumentProcessor(content, mime_type)
        extracted_text, method_used = processor.process()
        
        result = {
            "filename": filename,
            "content_type": content_type,
            "detected_mime_type": mime_type,
            "extraction_method": method_used.value,
            "extracted_text": extracted_text,
            "links": processor.extract_links() if mime_type == 'application/pdf' else []
        }
        logger.info("Processing completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))