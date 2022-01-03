from eolearn.core import EOTask, EOPatch, LinearWorkflow, FeatureType

# We'll use Sentinel-2 imagery (Level-1C) provided through Sentinel Hub
# If you don't know what `Level 1C` means, don't worry. It doesn't matter.

from eolearn.io import SentinelHubInputTask

from eolearn.mask import AddValidDataMaskTask

# filtering of scenes
from eolearn.features import SimpleFilterTask, NormalizedDifferenceIndexTask

# burning the vectorised polygon to raster
from eolearn.geometry import VectorToRasterTask

# The golden standard: numpy and matplotlib
import numpy as np

# import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

# For manipulating geo-spatial vector dataset (polygons of nominal water extent)
import geopandas as gpd

# Image manipulations  
# Our water detector is going to be based on a simple threshold 
# of Normalised Difference Water Index (NDWI) grayscale image
from skimage.filters import threshold_otsu

# Loading polygon of nominal water extent
import shapely.wkt
import shapely.geometry
from shapely.geometry import Polygon

# sentinelhub-py package
from sentinelhub import BBox, CRS, DataCollection

import os
from datetime import timedelta

path = os.path.abspath('')

bbox = BBox(bbox=[9.094491, 55.473442, 9.102162, 55.476142], crs=CRS.WGS84)

download_task = SentinelHubInputTask(
    data_collection=DataCollection.SENTINEL2_L2A, 
    bands_feature=(FeatureType.DATA, 'BANDS'),
    resolution=1, 
    maxcc=0.5,
    #time_difference=timedelta(720),
    #mosaicking_order='leastCC',
    bands=['B02', 'B03', 'B04', 'B08'], 
    additional_data=[(FeatureType.MASK, 'dataMask', 'IS_DATA'), (FeatureType.MASK, 'CLM')]
)

calculate_ndvi = NormalizedDifferenceIndexTask((FeatureType.DATA, 'BANDS'), (FeatureType.DATA, 'NDVI'), (1, 3))

def calculate_valid_data_mask(eopatch):
    is_data_mask = eopatch.mask['IS_DATA'].astype(np.bool)
    cloud_mask = ~eopatch.mask['CLM'].astype(np.bool)
    return np.logical_and(is_data_mask, cloud_mask)

add_valid_mask = AddValidDataMaskTask(predicate=calculate_valid_data_mask)

def calculate_coverage(array):
    return 1.0 - np.count_nonzero(array) / np.size(array)

class AddValidDataCoverageTask(EOTask):
    
    def execute(self, eopatch):
        
        valid_data = eopatch.get_feature(FeatureType.MASK, 'VALID_DATA')
        time, height, width, channels = valid_data.shape
        
        coverage = np.apply_along_axis(calculate_coverage, 1,
                                       valid_data.reshape((time, height * width * channels)))
        
        eopatch[FeatureType.SCALAR, 'COVERAGE'] = coverage[:, np.newaxis]
        return eopatch
    
add_coverage = AddValidDataCoverageTask()

cloud_coverage_threshold = 0.05 

class ValidDataCoveragePredicate:
    
    def __init__(self, threshold):
        self.threshold = threshold
        
    def __call__(self, array):
        return calculate_coverage(array) < self.threshold
    
remove_cloudy_scenes = SimpleFilterTask((FeatureType.MASK, 'VALID_DATA'),
                                        ValidDataCoveragePredicate(cloud_coverage_threshold))

workflow = LinearWorkflow(
    download_task,
    calculate_ndvi,
    add_valid_mask,
    add_coverage,
    remove_cloudy_scenes,
)

time_interval = ['2021-01-01','2021-12-01']
result = workflow.execute({
    download_task: {
        'bbox': bbox,
        'time_interval': time_interval
    },
})

patch = list(result.values())[-1]

def plot_pesticide_levels(eopatch):
    fig, ax = plt.subplots(figsize=(20, 7))

    dates = np.asarray(eopatch.timestamp)
    ndvi = [np.abs(np.mean(ndvi)) for ndvi in eopatch.data['NDVI']]
    ax.plot(dates,
            ndvi,
            'bo-', alpha=0.7)
    ax.set_xlabel('Date')
    ax.set_ylabel('NDVI level')
    ax.set_title('Field NDVI Levels')
    ax.grid(axis='y')
    return ax

ax = plot_pesticide_levels(patch)

plt.show()