import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.report import VerificationReport, ReportStatus
from app.services.workflow import run_audit_workflow
from app.core.interfaces import IReportRepository, IExtractionService, ISatelliteService, IFactCheckService
from app.api import deps
from app.core.config import settings
from app.core.utils import extract_text_from_pdf

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://greenaudit.faheemsarwar.com", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload-report", response_model=VerificationReport)
async def upload_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    report_repo: IReportRepository = Depends(deps.get_report_repo),
    extraction_service: IExtractionService = Depends(deps.get_extraction_service),
    satellite_service: ISatelliteService = Depends(deps.get_satellite_service),
    fact_check_service: IFactCheckService = Depends(deps.get_fact_check_service)
):
    """
    Upload a corporate sustainability report (PDF) for verification.
    Starts an async background task to process the claim.
    """
    report_id = str(uuid.uuid4())
    
    try:
        if file.content_type == "application/pdf":
            text_content = await extract_text_from_pdf(file)
        else:
            # Fallback for plain text files just in case
            content = await file.read()
            text_content = content.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process file: {str(e)}")

    # Truncate content for debug/log if necessary, but pass full text to service.
    # Note: text_content is now used instead of the mock string.

    # Initial Report Entry
    new_report = VerificationReport(
        id=report_id,
        status=ReportStatus.PENDING,
        filename=file.filename,
        uploaded_at=datetime.now()
    )
    
    await report_repo.save(new_report)

    # Dispatch Background Task
    # We pass the resolved dependencies explicitly
    background_tasks.add_task(
        run_audit_workflow, 
        report_id=report_id, 
        text_content=text_content,
        report_repo=report_repo,
        extraction_service=extraction_service,
        satellite_service=satellite_service,
        fact_check_service=fact_check_service
    )

    return new_report

@app.get("/status/{report_id}", response_model=VerificationReport)
async def get_report_status(
    report_id: str,
    report_repo: IReportRepository = Depends(deps.get_report_repo)
):
    """
    Check the status of a verification report.
    """
    report = await report_repo.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report

@app.get("/")
def root():
    return {"message": "GreenAudit API is running. Upload a report to /upload-report."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
