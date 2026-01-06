from datetime import datetime
import asyncio
from app.schemas.report import VerificationReport, ReportStatus, VerificationResult
from app.core.interfaces import IReportRepository, IExtractionService, ISatelliteService

async def run_audit_workflow(
    report_id: str, 
    text_content: str,
    report_repo: IReportRepository,
    extraction_service: IExtractionService,
    satellite_service: ISatelliteService
):
    """
    Orchestrates the GreenAudit workflow:
    1. Extract claims from text (LangChain).
    2. For each claim, fetch satellite data (SentinelHub).
    3. Verify claim vs reality.
    4. Update report status.
    """
    print(f"Starting audit workflow for report {report_id}")
    
    # 1. Retrieve the report to update status
    report = await report_repo.get(report_id)
    if not report:
        print(f"Report {report_id} not found.")
        return

    report.status = ReportStatus.PROCESSING
    await report_repo.update(report_id, report)

    try:
        # 2. Extract Claims
        claims = await extraction_service.extract_claims(text_content)
        report.claims = claims
        
        # 3. Analyze Claims
        verification_results = []
        for claim in claims:
            satellite_data = None
            verified = False
            confidence = 0.0

            if claim.location:
                # Fetch Satellite Data
                satellite_data = await satellite_service.analyze_location(claim.location)
                
                # Simple Verification Logic (Mock)
                # If claim is about vegetation and NDVI > 0.4, we verify it.
                if satellite_data.vegetation_detected:
                    verified = True
                    confidence = 0.85 + (satellite_data.ndvi_score * 0.1) # Dummy math
                else:
                    verified = False
                    confidence = 0.90
            
            result = VerificationResult(
                claim=claim,
                satellite_data=satellite_data,
                is_verified=verified,
                confidence_score=confidence
            )
            verification_results.append(result)

        report.results = verification_results
        report.status = ReportStatus.COMPLETED
        await report_repo.update(report_id, report)
        print(f"Audit completed for report {report_id}")

    except Exception as e:
        print(f"Error in audit workflow: {e}")
        report.status = ReportStatus.FAILED
        report.error = str(e)
        await report_repo.update(report_id, report)
