import io
from pypdf import PdfReader
from fastapi import UploadFile

async def extract_text_from_pdf(file: UploadFile) -> str:
    """
    Reads a PDF file from an UploadFile object and extracts its text content.
    """
    content = await file.read()
    pdf_file = io.BytesIO(content)
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Reset file cursor just in case it's needed elsewhere, though UploadFile behavior 
    # with read() usually consumes it.
    await file.seek(0) 
    return text
