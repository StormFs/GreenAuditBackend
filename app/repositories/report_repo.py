from typing import Dict, Optional
from app.schemas.report import VerificationReport
from app.core.interfaces import IReportRepository

class InMemoryReportRepository(IReportRepository):
    def __init__(self):
        # In-memory storage simulated with a dictionary
        self._reports: Dict[str, VerificationReport] = {}

    async def save(self, report: VerificationReport) -> VerificationReport:
        self._reports[report.id] = report
        return report

    async def get(self, report_id: str) -> Optional[VerificationReport]:
        return self._reports.get(report_id)

    async def update(self, report_id: str, report: VerificationReport) -> VerificationReport:
        self._reports[report_id] = report
        return report
