from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class ReportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class GeoCoordinates(BaseModel):
    latitude: float = Field(..., description="Latitude of the location")
    longitude: float = Field(..., description="Longitude of the location")

class EnvironmentalClaim(BaseModel):
    description: str = Field(..., description="The specific environmental claim, e.g., 'Planted 500 trees'")
    location: Optional[GeoCoordinates] = Field(None, description="Geographic location associated with the claim")
    date_claimed: Optional[str] = Field(None, description="Date associated with the claim")
    measure_value: Optional[float] = Field(None, description="Quantitative value extracted from the claim (e.g. 15, 500)")
    measure_unit: Optional[str] = Field(None, description="Unit for the value (e.g. %, hectares, tons)")

class SatelliteAnalysis(BaseModel):
    ndvi_score: float = Field(..., description="Current score (NDVI, NDWI, or Change Metric)")
    metric_name: str = Field(default="NDVI", description="Name of the metric used (e.g. NDVI, NDWI, Visual Delta)")
    historical_ndvi: Optional[float] = Field(None, description="Historical score from comparison date")
    vegetation_detected: bool = Field(..., description="Whether significant features were detected")
    vegetation_change: Optional[float] = Field(None, description="Percentage change in metric (Current - Historical)")
    analysis_date: datetime = Field(default_factory=datetime.now)
    comparison_date: Optional[datetime] = Field(None, description="Date of the historical image")

class VerificationResult(BaseModel):
    claim: EnvironmentalClaim
    satellite_data: Optional[SatelliteAnalysis] = None
    evidence_text: Optional[str] = Field(None, description="Textual evidence from web search or documents")
    source_urls: List[str] = Field(default=[], description="List of source URLs for the evidence")
    is_verified: bool = Field(..., description="Whether the satellite data supports the claim")
    confidence_score: float = Field(..., description="Confidence score of the verification")

class VerificationReport(BaseModel):
    id: str
    status: ReportStatus
    filename: str
    uploaded_at: datetime
    claims: List[EnvironmentalClaim] = []
    results: List[VerificationResult] = []
    error: Optional[str] = None
