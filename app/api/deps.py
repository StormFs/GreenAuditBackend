from functools import lru_cache
from typing import Generator

from app.core.interfaces import IReportRepository, ISatelliteService, IExtractionService
from app.repositories.report_repo import InMemoryReportRepository
from app.services.satellite import MockSatelliteService
from app.services.extraction import MockExtractionService, GeminiExtractionService
from app.core.config import settings

# Singleton instances (could be scoped per request if using DB session)
_report_repo = InMemoryReportRepository()
_satellite_service = MockSatelliteService()

# Conditionally instantiate the extraction service
if settings.GOOGLE_API_KEY:
    _extraction_service = GeminiExtractionService()
else:
    print("GOOGLE_API_KEY not found. Using MockExtractionService.")
    _extraction_service = MockExtractionService()

def get_report_repo() -> IReportRepository:
    return _report_repo

def get_satellite_service() -> ISatelliteService:
    return _satellite_service

def get_extraction_service() -> IExtractionService:
    return _extraction_service
