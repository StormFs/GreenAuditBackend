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

    async def analyze_location(self, coords: GeoCoordinates, mode: str = "vegetation") -> SatelliteAnalysis:
        """
        Placeholder for fetching Sentinel-2 imagery and calculating NDVI.
        Now supports simulating 'solar' and 'water' modes.
        Also hardcodes 'success' for demo coordinates.
        """
        # Simulating processing delay
        # await asyncio.sleep(2) 
        
        # DEMO: Hardcoded Success for User Scenarios
        # 1. Amazonia (Restoration)
        if -3.6 < coords.latitude < -3.3 and -62.4 < coords.longitude < -62.0:
            return SatelliteAnalysis(
                ndvi_score=0.75,
                metric_name="NDVI",
                historical_ndvi=0.60,
                vegetation_detected=True,
                vegetation_change=15.0, # +15% Boost (Verified!)
                analysis_date=datetime.datetime.now(),
                comparison_date=datetime.datetime.now() - datetime.timedelta(days=365)
            )

        # 2. Mojave Solar (Solar)
        if 34.7 < coords.latitude < 35.0 and -117.0 < coords.longitude < -116.5:
             return SatelliteAnalysis(
                ndvi_score=0.1, 
                metric_name="Visual Change Confidence",
                historical_ndvi=0.1,
                vegetation_detected=True, 
                vegetation_change=92.0, # 92% Confidence score for Solar
                analysis_date=datetime.datetime.now(),
                comparison_date=datetime.datetime.now() - datetime.timedelta(days=365)
            )

        # 3. Mangroves Thailand (Water/Coastal)
        if 14.3 < coords.latitude < 14.6 and 100.0 < coords.longitude < 100.3:
             return SatelliteAnalysis(
                ndvi_score=0.65, 
                metric_name="NDVI/NDWI Composite",
                historical_ndvi=0.55,
                vegetation_detected=True,
                vegetation_change=10.0, # 10% Increase (Verified)
                analysis_date=datetime.datetime.now(),
                comparison_date=datetime.datetime.now() - datetime.timedelta(days=365)
            )

        # Dummy logic: Randomly generate scores based on mode
        ndvi = random.uniform(0.1, 0.9)
        historical_ndvi = ndvi - random.uniform(-0.1, 0.2)
        
        # Determine if verified based on mode
        if mode == "solar":
             # Solar: Low NDVI (desert/roof), distinct spectral signature (simulated)
             # We reuse 'vegetation_change' field to store the 'confidence' or 'change' metric for solar
             score = random.uniform(0.7, 0.99) # High confidence for solar mock
             return SatelliteAnalysis(
                ndvi_score=0.1, # Solar isn't plants
                metric_name="Visual Change Confidence",
                historical_ndvi=0.1,
                vegetation_detected=True, # Reusing field as 'feature_detected'
                vegetation_change=score * 100, # Reusing as confidence/presence score
                analysis_date=datetime.datetime.now(),
                comparison_date=datetime.datetime.now() - datetime.timedelta(days=365)
            )
        elif mode == "water":
             # Water/Mangroves: High NDWI (Water) + High NDVI (if mangrove)
             score = random.uniform(0.6, 0.9)
             return SatelliteAnalysis(
                ndvi_score=0.6, 
                metric_name="NDWI (Water Index)",
                historical_ndvi=0.5,
                vegetation_detected=True,
                vegetation_change=15.0, # 15% increase in coastal protection zone
                analysis_date=datetime.datetime.now(),
                comparison_date=datetime.datetime.now() - datetime.timedelta(days=365)
            )
        
        # Default Vegetation Logic
        return SatelliteAnalysis(
            ndvi_score=ndvi,
            metric_name="NDVI (Vegetation Index)",
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

    def _fetch_data(self, bbox, time_interval, mode="vegetation"):
        """
        Helper method to fetch imagery based on mode.
        """
        # dynamic evalscript based on mode
        if mode == "water":
            # NDWI (McFeeters): (Green - NIR) / (Green + NIR)
            # Returns single channel NDWI
            evalscript = """
            //VERSION=3
            function setup() {
              return {
                input: ["B03", "B08"],
                output: { bands: 1, sampleType: "FLOAT32" }
              };
            }
            function evaluatePixel(sample) {
              let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);
              return [ndwi];
            }
            """
            num_bands = 1
        elif mode == "solar":
            # RGB for Visual Change Detection
            evalscript = """
            //VERSION=3
            function setup() {
              return {
                input: ["B04", "B03", "B02"],
                output: { bands: 3, sampleType: "FLOAT32" }
              };
            }
            function evaluatePixel(sample) {
              return [sample.B04, sample.B03, sample.B02];
            }
            """
            num_bands = 3
        else:
            # Vegetation (Default) - 4 Bands for U-Net
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
            num_bands = 4
        
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
                return None
            
            image = data[0]
            if len(image.shape) == 4:
                image = image[0]
            
            return image
        except Exception as e:
            print(f"SentinelSatelliteService: Error in sub-request: {e}")
            return None

    def _process_image(self, image, mode):
        """Processes raw image data based on mode"""
        if image is None: return 0.0

        if mode == "vegetation":
            # Run U-Net
            tensor_img = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float()
            with torch.no_grad():
                output_mask = self.unet(tensor_img)
                probs = torch.sigmoid(output_mask)
            return probs.mean().item()
        
        elif mode == "water":
            # Image is 1 channel NDWI. Mean > 0 implies water.
            # Return mean NDWI
            return np.mean(image)

        elif mode == "solar":
            # Image is 3 channel RGB. Return raw image for comparison later.
            return image
            
        return 0.0

    async def analyze_location(self, coords: GeoCoordinates, mode: str = "vegetation") -> SatelliteAnalysis:
        """
        Fetches Current and Historical Sentinel-2 imagery and compares them using mode-specific logic.
        """
        print(f"SentinelSatelliteService: Fetching comparison data for {coords} (Mode: {mode})")
        
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
        
        current_img = self._fetch_data(bbox, (start_date.isoformat(), end_date.isoformat()), mode)
        current_score = self._process_image(current_img, mode)

        # 2. Historical Data (1 year ago)
        hist_end_date = end_date - datetime.timedelta(days=365)
        hist_start_date = hist_end_date - datetime.timedelta(days=30)
        
        hist_img = self._fetch_data(bbox, (hist_start_date.isoformat(), hist_end_date.isoformat()), mode)
        hist_score = self._process_image(hist_img, mode)

        # Calculate Change based on mode
        change = 0.0
        
        if mode == "solar":
            # For Solar, we compare the RGB images directly (Geographical Change)
            if isinstance(current_score, np.ndarray) and isinstance(hist_score, np.ndarray):
                # Simple Mean Absolute Difference between images
                diff = np.abs(current_score - hist_score)
                # Normalize (assuming 0-1 float reflectance usually, but can be higher)
                change = np.mean(diff) * 100 # percentage visual change
                # For report, we store this 'visual change' in vegetation_change field
                # And use ndvi_score to store a dummy value or the raw change
                return SatelliteAnalysis(
                    ndvi_score=0.0,
                    metric_name="Visual Change Confidence",
                    historical_ndvi=0.0,
                    vegetation_detected=True,
                    vegetation_change=change,
                    analysis_date=datetime.datetime.now(),
                    comparison_date=hist_end_date
                )
            else:
                 change = 0.0
        else:
            # Vegetation (NDVI/UNet) and Water (NDWI) return scalar scores
            if isinstance(current_score, float) and isinstance(hist_score, float):
                change = (current_score - hist_score) * 100
            else:
                current_score = 0.0
                hist_score = 0.0

        return SatelliteAnalysis(
            ndvi_score=float(current_score) if isinstance(current_score, (int, float)) else 0.0,
            metric_name="NDWI (Water Index)" if mode == "water" else "NDVI (Vegetation Index)",
            historical_ndvi=float(hist_score) if isinstance(hist_score, (int, float)) else 0.0,
            vegetation_detected=current_score > 0.3 if mode != "water" else current_score > 0.0,
            vegetation_change=change,
            analysis_date=datetime.datetime.now(),
            comparison_date=hist_end_date
        )
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
