from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.report import VerificationReport, GeoCoordinates, SatelliteAnalysis, EnvironmentalClaim

class IReportRepository(ABC):
    @abstractmethod
    async def save(self, report: VerificationReport) -> VerificationReport:
        pass

    @abstractmethod
    async def get(self, report_id: str) -> Optional[VerificationReport]:
        pass

    @abstractmethod
    async def update(self, report_id: str, report: VerificationReport) -> VerificationReport:
        pass

class ISatelliteService(ABC):
    @abstractmethod
    async def analyze_location(self, coords: GeoCoordinates, mode: str = "vegetation") -> SatelliteAnalysis:
        """
        Analyze the location. Mode can be "vegetation", "solar", or "water".
        """
        pass

class IExtractionService(ABC):
    @abstractmethod
    async def extract_claims(self, text: str) -> List[EnvironmentalClaim]:
        pass

class IFactCheckService(ABC):
    @abstractmethod
    async def verify_claim(self, claim: EnvironmentalClaim) -> dict:
        """
        Returns a dict with:
        - verified: bool
        - confidence: float
        - evidence: str
        - sources: List[str]
        """
        pass
