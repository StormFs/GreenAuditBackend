import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends
from app.schemas.report import VerificationReport, ReportStatus
from app.services.workflow import run_audit_workflow
from app.core.interfaces import IReportRepository, IExtractionService, ISatelliteService
from app.api import deps
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

@app.post("/upload-report", response_model=VerificationReport)
async def upload_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    report_repo: IReportRepository = Depends(deps.get_report_repo),
    extraction_service: IExtractionService = Depends(deps.get_extraction_service),
    satellite_service: ISatelliteService = Depends(deps.get_satellite_service)
):
    """
    Upload a corporate sustainability report (PDF) for verification.
    Starts an async background task to process the claim.
    """
    report_id = str(uuid.uuid4())
    
    # In a real app, we would parse the PDF here.
    # For this scaffold, we simulate extracting text from the file.
    # content = await file.read()
    # text_content = content.decode("utf-8") 
    
    # Mock text content for the scaffold
    text = (
        "Sustainability Report 2025. "
        "We have successfully planted 5000 trees in the Amazon Rainforest at location -3.4653, -62.2159. "
        "We also restored 50 hectares of mangroves at 9.9281, -84.0907."
    )

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
        text_content=text,
        report_repo=report_repo,
        extraction_service=extraction_service,
        satellite_service=satellite_service
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
