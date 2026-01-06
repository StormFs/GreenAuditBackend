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
    async def analyze_location(self, coords: GeoCoordinates) -> SatelliteAnalysis:
        pass

class IExtractionService(ABC):
    @abstractmethod
    async def extract_claims(self, text: str) -> List[EnvironmentalClaim]:
        pass
