import random
import numpy as np
import datetime
from typing import Optional

# Conditional import to avoid crashing if sentinelhub is not installed (though we installed it)
from sentinelhub import (
    SHConfig,
    SentinelHubRequest,
    DataCollection,
    MimeType,
    BBox,
    CRS,
)

import torch
from app.core.models.unet import UNet
from app.schemas.report import GeoCoordinates, SatelliteAnalysis
from app.core.interfaces import ISatelliteService
from app.core.config import settings

class MockSatelliteService(ISatelliteService):
    def __init__(self):
        # Initialize SentinelHub client here in a real implementation
        pass

    async def analyze_location(self, coords: GeoCoordinates) -> SatelliteAnalysis:
        """
        Placeholder for fetching Sentinel-2 imagery and calculating NDVI.
        """
        # Simulating processing delay
        # await asyncio.sleep(2) 
        
        # Dummy logic: Randomly generate NDVI score between -1 and 1
        # High NDVI (> 0.5) usually indicates dense vegetation.
        ndvi = random.uniform(0.1, 0.9)
        historical_ndvi = ndvi - random.uniform(-0.1, 0.2) # Simulate some change
        
        return SatelliteAnalysis(
            ndvi_score=ndvi,
            historical_ndvi=historical_ndvi,
            vegetation_detected=ndvi > 0.4,
            vegetation_change=(ndvi - historical_ndvi) * 100,
            analysis_date=datetime.datetime.now(),
            comparison_date=datetime.datetime.now() - datetime.timedelta(days=365)
        )

class SentinelSatelliteService(ISatelliteService):
    def __init__(self):
        self.config = SHConfig()
        if settings.SENTINELHUB_CLIENT_ID and settings.SENTINELHUB_CLIENT_SECRET:
            self.config.sh_client_id = settings.SENTINELHUB_CLIENT_ID
            self.config.sh_client_secret = settings.SENTINELHUB_CLIENT_SECRET
        else:
            raise ValueError("SentinelHub credentials not configured")
        
        # Initialize U-Net (4 input channels: R, G, B, NIR; 1 output class: Vegetation)
        self.unet = UNet(n_channels=4, n_classes=1)
        self.unet.eval() # Set to evaluation mode

    def _fetch_and_process(self, bbox, time_interval):
        """
        Helper method to fetch imagery for a specific time interval and process with U-Net.
        Returns the NDVI score (float) or 0.0 if failed.
        """
        # Define EvalScript for Raw Bands (Blue, Green, Red, NIR)
        evalscript = """
        //VERSION=3
        function setup() {
          return {
            input: ["B02", "B03", "B04", "B08"],
            output: { bands: 4, sampleType: "FLOAT32" }
          };
        }

        function evaluatePixel(sample) {
          return [sample.B02, sample.B03, sample.B04, sample.B08];
        }
        """
        
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=time_interval,
                    mosaicking_order="leastCC" 
                )
            ],
            responses=[
                SentinelHubRequest.output_response("default", MimeType.TIFF)
            ],
            bbox=bbox,
            size=(256, 256),
            config=self.config
        )

        try:
            data = request.get_data()
            if not data or len(data) == 0:
                return 0.0
            
            image = data[0]
            if len(image.shape) == 4:
                image = image[0]
            
            # Run U-Net
            tensor_img = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float()
            with torch.no_grad():
                output_mask = self.unet(tensor_img)
                probs = torch.sigmoid(output_mask)
            
            return probs.mean().item()
        except Exception as e:
            print(f"SentinelSatelliteService: Error in sub-request: {e}")
            return 0.0

    async def analyze_location(self, coords: GeoCoordinates) -> SatelliteAnalysis:
        """
        Fetches Current and Historical Sentinel-2 imagery and compares them.
        """
        print(f"SentinelSatelliteService: Fetching comparison data for {coords}")
        
        # 0.02 degrees ~ 2.2km
        bbox_size = 0.02 
        bbox = BBox(bbox=[
            coords.longitude - bbox_size/2, 
            coords.latitude - bbox_size/2, 
            coords.longitude + bbox_size/2, 
            coords.latitude + bbox_size/2
        ], crs=CRS.WGS84)

        # 1. Current Data (Last 30 days)
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        print(f"Fetching CURRENT data ({start_date} to {end_date})...")
        current_ndvi = self._fetch_and_process(bbox, (start_date, end_date))
        
        # 2. Historical Data (1 Year Ago)
        hist_end_date = end_date - datetime.timedelta(days=365)
        hist_start_date = hist_end_date - datetime.timedelta(days=30)
        print(f"Fetching HISTORICAL data ({hist_start_date} to {hist_end_date})...")
        hist_ndvi = self._fetch_and_process(bbox, (hist_start_date, hist_end_date))
        
        print(f"Comparison: Current={current_ndvi:.4f} vs Historical={hist_ndvi:.4f}")
        
        # Calculate change
        change_pct = 0.0
        if hist_ndvi > 0:
            change_pct = ((current_ndvi - hist_ndvi) / hist_ndvi) * 100
        
        return SatelliteAnalysis(
            ndvi_score=current_ndvi,
            historical_ndvi=hist_ndvi,
            vegetation_detected=current_ndvi > 0.4,
            vegetation_change=change_pct,
            analysis_date=datetime.datetime.now(),
            comparison_date=datetime.datetime.combine(hist_end_date, datetime.time.min)
        )
