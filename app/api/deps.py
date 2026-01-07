from functools import lru_cache
from typing import Generator

from app.core.interfaces import IReportRepository, ISatelliteService, IExtractionService, IFactCheckService
from app.repositories.report_repo import InMemoryReportRepository
from app.services.satellite import MockSatelliteService, SentinelSatelliteService
from app.services.extraction import MockExtractionService, LLMExtractionService
from app.services.factcheck import WebFactCheckService, MockFactCheckService
from app.core.config import settings

# Singleton instances (could be scoped per request if using DB session)
_report_repo = InMemoryReportRepository()

# Conditionally instantiate the satellite service
if settings.SENTINELHUB_CLIENT_ID and settings.SENTINELHUB_CLIENT_SECRET:
    _satellite_service = SentinelSatelliteService()
else:
    print("SentinelHub credentials not found. Using MockSatelliteService.")
    _satellite_service = MockSatelliteService()

# Conditionally instantiate the extraction service
# We are temporarily forcing MOCK services because the keys are exhausted/rate-limited
FORCE_MOCK_AI = True 

if (settings.GOOGLE_API_KEY or settings.GROQ_API_KEY) and not FORCE_MOCK_AI:
    _extraction_service = LLMExtractionService()
    _fact_check_service = WebFactCheckService()
else:
    print("No AI API Key found (Gemini/Groq) or Mock Forced. Using Mock Services for Extraction and FactCheck.")
    _extraction_service = MockExtractionService()
    _fact_check_service = MockFactCheckService()

def get_report_repo() -> IReportRepository:
    return _report_repo

def get_satellite_service() -> ISatelliteService:
    return _satellite_service

def get_extraction_service() -> IExtractionService:
    return _extraction_service

def get_fact_check_service() -> IFactCheckService:
    return _fact_check_service
