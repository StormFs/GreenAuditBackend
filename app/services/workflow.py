from datetime import datetime
import asyncio
from app.schemas.report import VerificationReport, ReportStatus, VerificationResult
from app.core.interfaces import IReportRepository, IExtractionService, ISatelliteService, IFactCheckService

async def run_audit_workflow(
    report_id: str, 
    text_content: str,
    report_repo: IReportRepository,
    extraction_service: IExtractionService,
    satellite_service: ISatelliteService,
    fact_check_service: IFactCheckService
):
    """
    Orchestrates the GreenAudit workflow:
    1. Extract claims from text (LangChain).
    2. Route claims:
       - Spatial (Location found) -> SentinelHub Analysis
       - Informational (No location) -> Web Fact Check (DuckDuckGo + LLM)
    3. Update report status.
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
        print(f"Extracting claims from text (length: {len(text_content)} chars)...")
        claims = await extraction_service.extract_claims(text_content)
        print(f"Extracted {len(claims)} claims.")
        for i, c in enumerate(claims):
            print(f"  Claim {i+1}: Location={c.location}")

        report.claims = claims
        
        # 3. Analyze Claims
        verification_results = []
        for claim in claims:
            satellite_data = None
            evidence_text = None
            source_urls = []
            verified = False
            confidence = 0.0

            # Route based on location presence
            if claim.location and claim.location.latitude != 0 and claim.location.longitude != 0:
                print(f"Analyzing location: {claim.location} with {type(satellite_service).__name__}")
                try:
                    # Fetch Satellite Data
                    satellite_data = await satellite_service.analyze_location(claim.location)
                    print(f"Satellite analysis result: {satellite_data}")
                except Exception as sat_err:
                    print(f"Error fetching satellite data: {sat_err}")
                
                if satellite_data:
                    # Advanced Verification Logic
                    # A change of 0.01 is usually sensor noise (clouds, shadows, atmosphere).
                    # We usually look for at least a 0.05 (5%) to 0.10 (10%) positive shift for "Reforestation".
                    # However, if the claim is "Preservation" (avoiding loss), then a change of ~0.0 is GOOD.
                    
                    # Heuristic: Detect intent from claim description
                    claim_desc = claim.description.lower()
                    is_restoration = any(w in claim_desc for w in ["planted", "restored", "increased", "grew"])
                    
                    if is_restoration:
                        # For restoration, we demand positive growth > 5%
                        if satellite_data.vegetation_change and satellite_data.vegetation_change > 5.0:
                             verified = True
                             confidence = 0.80 + min((satellite_data.vegetation_change / 100), 0.15)
                        else:
                             verified = False
                             confidence = 0.60 # Less confident it's false, could be slow growth
                    else:
                        # For "protected" or "maintained", we verify if vegetation is present and stable
                        if satellite_data.vegetation_detected and (satellite_data.vegetation_change is None or satellite_data.vegetation_change > -5.0):
                             verified = True
                             confidence = 0.90
                        else:
                             verified = False
                             confidence = 0.85

                    # Generate "Proposed vs Detected" string
                    if evidence_text is None:
                        evidence_text = ""
                    
                    if claim.measure_value is not None:
                        unit = claim.measure_unit or ""
                        detected_val = satellite_data.vegetation_change if satellite_data.vegetation_change is not None else 0.0
                        evidence_text += f" Proposed: {claim.measure_value}{unit}, Detected Change: {detected_val:.1f}%"
                    else:
                        detected_val = satellite_data.vegetation_change if satellite_data.vegetation_change is not None else 0.0
                        evidence_text += f" Detected Vegetation Change: {detected_val:.1f}%"

                else:
                    print("No satellite data returned.")
            else:
                # Non-spatial claim -> Web Search Fact Check
                print(f"Processing non-spatial claim: '{claim.description}'")
                try:
                    fc_result = await fact_check_service.verify_claim(claim)
                    verified = fc_result["verified"]
                    confidence = fc_result["confidence"]
                    evidence_text = fc_result["evidence"]
                    source_urls = fc_result["sources"]
                    print(f"Web verification result: {verified} ({confidence})")
                except Exception as fc_err:
                    print(f"Error in web fact retrieval: {fc_err}")

            
            result = VerificationResult(
                claim=claim,
                satellite_data=satellite_data,
                evidence_text=evidence_text, # New field
                source_urls=source_urls,     # New field
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
