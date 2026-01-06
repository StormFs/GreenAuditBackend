import random
from app.schemas.report import GeoCoordinates, SatelliteAnalysis
from app.core.interfaces import ISatelliteService

class MockSatelliteService(ISatelliteService):
    def __init__(self):
        # Initialize SentinelHub client here in a real implementation
        pass

    async def analyze_location(self, coords: GeoCoordinates) -> SatelliteAnalysis:
        """
        Placeholder for fetching Sentinel-2 imagery and calculating NDVI.
        In a real scenario, this would:
        1. Use sentinelhub-py to fetch bands B04 (Red) and B08 (NIR).
        2. Compute NDVI = (NIR - Red) / (NIR + Red).
        3. Analyze the trend over time.
        """
        # Simulating processing delay
        # await asyncio.sleep(2) 
        
        # Dummy logic: Randomly generate NDVI score between -1 and 1
        # High NDVI (> 0.5) usually indicates dense vegetation.
        ndvi = random.uniform(0.1, 0.9)
        
        return SatelliteAnalysis(
            ndvi_score=ndvi,
            vegetation_detected=ndvi > 0.4
        )
