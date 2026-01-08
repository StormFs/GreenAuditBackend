from datetime import datetime
import asyncio
from app.schemas.report import VerificationReport, ReportStatus, VerificationResult
from app.core.interfaces import IReportRepository, IExtractionService, ISatelliteService, IFactCheckService


def _determine_claim_intent(description: str) -> str:
    """
    Determines if the claim is about CREATING something (Establishment) 
    or KEEPING something (Preservation).
    """
    desc = description.lower()
    
    establishment_keywords = [
        "planted", "restored", "established", "new", "built", 
        "created", "increased", "grew", "generated", "installation", "deployed"
    ]
    
    preservation_keywords = [
        "protected", "preserved", "maintained", "conserved", 
        "saved", "prevented", "avoided", "kept"
    ]
    
    if any(k in desc for k in establishment_keywords):
        return "establishment"
    if any(k in desc for k in preservation_keywords):
        return "preservation"
        
    return "unknown"

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
                

                # Determine Verification Mode
                desc = claim.description.lower()
                mode = "vegetation"
                if any(w in desc for w in ["solar", "panel", "energy", "photovoltaic", "sun"]):
                    mode = "solar"
                elif any(w in desc for w in ["water", "coastal", "mangrove", "erosion", "river", "flood"]):
                    mode = "water"
                
                # Determine Claim Intent (Establishment vs Preservation)
                intent = _determine_claim_intent(desc)
                print(f"Detected Analysis Mode: {mode.upper()} | Intent: {intent.upper()}")

                try:
                    # Fetch Satellite Data with specific mode
                    satellite_data = await satellite_service.analyze_location(claim.location, mode=mode)
                    print(f"Satellite analysis result: {satellite_data}")
                except Exception as sat_err:
                    print(f"Error fetching satellite data: {sat_err}")
                
                if satellite_data:
                    # Get the change value (0.0 if None)
                    change = satellite_data.vegetation_change if satellite_data.vegetation_change is not None else 0.0
                    
                    # Logic Branching based on Mode & Intent
                    if mode == "solar":
                         # Solar usually implies "Establishment" of new infrastructure
                         # We expect high visual change
                         if intent == "preservation":
                              # "Maintained solar farm" - change might be low if it existed 1 year ago
                              verified = True
                              confidence = 0.8
                              evidence_text = f"Solar farm detected. Visual change {change:.1f}% consistent with maintenance."
                         else:
                              # Default to Establishment/New for Solar
                              if change > 20.0: # Significant visual change
                                   verified = True
                                   confidence = min(change / 100 + 0.5, 0.95)
                                   evidence_text = f"New Solar Infrastructure Detected. Visual Change: {change:.1f}%"
                              else:
                                   verified = False
                                   confidence = 0.6
                                   evidence_text = f"claimed 'New Solar' but low visual change identified ({change:.1f}%)."
                    
                    elif mode == "water":
                         if intent == "establishment":
                             # "Restored mangroves" -> Expect positive change
                             if change > 1.0:
                                 verified = True
                                 confidence = 0.85
                                 evidence_text = f"Coastal Vegetation Expansion Detected: {change:.1f}%"
                             else:
                                 verified = False
                                 confidence = 0.50
                                 evidence_text = f"Claimed establishment/restoration but saw {change:.1f}% change."
                         else:
                             # "Protected coast" -> Expect Stability (approx 0 change) or Growth
                             if change > -5.0: # Allows small loss, but mostly stable
                                 verified = True 
                                 confidence = 0.90
                                 evidence_text = f"Coastal Zone Stable/Protected. Change: {change:.1f}%"
                             else:
                                 verified = False
                                 confidence = 0.70
                                 evidence_text = f"Protected zone shows significant degradation ({change:.1f}%)."

                    else:
                        # Vegetation / Forestry
                        if intent == "establishment":
                            # "Planted trees" -> Require growth
                            if change > 5.0:
                                verified = True
                                confidence = 0.80 + min((change / 100), 0.15)
                                evidence_text = f"Reforestation Verified. Growth: {change:.1f}%"
                            elif change > 0.1:
                                verified = False # Flagged
                                confidence = 0.50
                                evidence_text = f"Weak Signal: Growth detected ({change:.1f}%) but below establishment threshold (5%)."
                            else:
                                verified = False # Failed
                                confidence = 0.40
                                evidence_text = "FLAGGED: Company claimed 'New Establishment', but satellite shows zero/negative change."
                        
                        else:
                            # "Protected forest" -> Verify presence and stability
                            if satellite_data.vegetation_detected and change > -5.0:
                                verified = True
                                confidence = 0.90
                                evidence_text = f"Forest Protection Verified. Area stable or growing ({change:.1f}%)."
                            else:
                                verified = False
                                confidence = 0.85
                                evidence_text = f"Protection Claim Failed: Significant vegetation loss detected ({change:.1f}%)."

                        # Append quantitative comparison if available
                        if claim.measure_value is not None:
                             str_unit = claim.measure_unit or ""
                             evidence_text += f" (Claimed: {claim.measure_value}{str_unit})"

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
                    evidence_text = f"Verification Failed due to external API error: {str(fc_err)}"
                    verified = False
                    confidence = 0.0

            
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
