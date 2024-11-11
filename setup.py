from setuptools import setup, find_packages

setup(
    name="docprocessor",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "python-multipart",
        "PyMuPDF",
        "pdfplumber",
        "pytesseract",
        "Pillow",
        "pdf2image",
        "python-magic",
        "httpx",
        "uvicorn",
    ],
) 