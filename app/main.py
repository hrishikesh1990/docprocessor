# app/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Security
from typing import Dict, Any, Optional
import magic
import httpx
import logging
from app.utils.document_processor import DocumentProcessor, ExtractionMethod
from app.auth.auth_handler import get_api_key
import boto3
from urllib.parse import urlparse, parse_qs
from botocore.exceptions import ClientError
import os

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

def get_s3_client():
    return boto3.client('s3')

def generate_presigned_url(bucket: str, key: str, expiration: int = 900) -> str:
    try:
        s3_client = get_s3_client()
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating S3 access URL")

def extract_s3_details_from_url(url: str) -> tuple[str, str]:
    """Extract bucket and key from S3 URL"""
    try:
        parsed = urlparse(url)
        # The bucket is the first part of the hostname
        bucket = parsed.netloc.split('.')[0]
        # Remove leading slash and everything after the question mark
        key = parsed.path.lstrip('/').split('?')[0]
        logger.info(f"Extracted bucket: {bucket}, key: {key}")
        return bucket, key
    except Exception as e:
        logger.error(f"Failed to parse S3 URL: {str(e)}")
        raise ValueError(f"Invalid S3 URL format: {str(e)}")

def get_mime_type_from_filename(filename: str) -> str:
    """Determine MIME type from file extension."""
    extension_map = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff'
    }
    ext = os.path.splitext(filename.lower())[1]
    return extension_map.get(ext)

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
            # Remove S3 URL handling since these are public URLs
            async with httpx.AsyncClient(
                verify=False,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': '*/*'
                }
            ) as client:
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
        
        if mime_type == 'application/octet-stream':
            # Try to determine type from filename
            filename_mime_type = get_mime_type_from_filename(filename)
            if filename_mime_type and filename_mime_type in SUPPORTED_MIME_TYPES:
                mime_type = filename_mime_type
                logger.info(f"Using file extension to determine MIME type: {mime_type}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {mime_type}. Supported types: {', '.join(SUPPORTED_MIME_TYPES)}"
                )
        elif mime_type not in SUPPORTED_MIME_TYPES:
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