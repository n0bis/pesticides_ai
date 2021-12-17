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

path = os.path.abspath('')

# The polygon of the dam is written in wkt format and WGS84 coordinate reference system
with open(f'{path}/Example_code/field.wkt', 'r') as f:
    field_wkt = f.read()

field_nominal = shapely.wkt.loads(field_wkt)

# inflate the BBOX 
inflate_bbox = 0.1
minx, miny, maxx, maxy = field_nominal.bounds

delx = maxx - minx
dely = maxy - miny
minx = minx - delx * inflate_bbox
maxx = maxx + delx * inflate_bbox
miny = miny - dely * inflate_bbox
maxy = maxy + dely * inflate_bbox
    
field_bbox = BBox([minx, miny, maxx, maxy], crs=CRS.WGS84)

#field_bbox.geometry - field_nominal

download_task = SentinelHubInputTask(
    data_collection=DataCollection.SENTINEL2_L1C, 
    bands_feature=(FeatureType.DATA, 'BANDS'),
    resolution=20, 
    maxcc=0.5, 
    bands=['B02', 'B03', 'B04', 'B08'], 
    additional_data=[(FeatureType.MASK, 'dataMask', 'IS_DATA'), (FeatureType.MASK, 'CLM')]
)

calculate_ndvi = NormalizedDifferenceIndexTask((FeatureType.DATA, 'BANDS'), (FeatureType.DATA, 'NDVI'), (1, 3))

field_gdf = gpd.GeoDataFrame(crs=CRS.WGS84.pyproj_crs(), geometry=[field_nominal])

add_nominal_pesticide = VectorToRasterTask(
    field_gdf, (FeatureType.MASK_TIMELESS, 'NOMINAL_PESTICIDE'), values=1, 
    raster_shape=(FeatureType.MASK, 'IS_DATA'), raster_dtype=np.uint8
)

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

class PesticideDetectionTask(EOTask):
  @staticmethod
  def detect_pesticides(ndvi):
    """ Very simple pesticide detector based on Otsu thresholding method of NDVI.
    """
    otsu_thr = 1.0
    if len(np.unique(ndvi)) > 1:
        ndvi[np.isnan(ndvi)] = -1
        otsu_thr = threshold_otsu(ndvi)

    return ndvi > otsu_thr

  def execute(self, eopatch):
        pesticide_masks = np.asarray([self.detect_pesticides(ndvi[...,0]) for ndvi in eopatch.data['NDVI']])
        
        # we're only interested in the water within the dam borders
        pesticide_masks = pesticide_masks[...,np.newaxis] * eopatch.mask_timeless['NOMINAL_PESTICIDE']
        
        pesticide_levels = np.asarray([np.count_nonzero(mask)/np.count_nonzero(eopatch.mask_timeless['NOMINAL_PESTICIDE']) 
                                   for mask in pesticide_masks])
        
        eopatch[FeatureType.MASK, 'PESTICIDE_MASK'] = pesticide_masks
        eopatch[FeatureType.SCALAR, 'PESTICIDE_LEVEL'] = pesticide_levels[...,np.newaxis]
        
        return eopatch
    
pesticide_detection = PesticideDetectionTask()

workflow = LinearWorkflow(
    download_task,
    calculate_ndvi,
    add_nominal_pesticide,
    add_valid_mask,
    add_coverage,
    remove_cloudy_scenes,
    pesticide_detection
)

time_interval = ['2017-01-01','2020-06-01']
result = workflow.execute({
    download_task: {
        'bbox': field_bbox,
        'time_interval': time_interval
    },
})

patch = list(result.values())[-1]

from skimage.filters import sobel
from skimage.morphology import disk
from skimage.morphology import erosion, dilation, opening, closing, white_tophat

def plot_rgb_w_pesticide(eopatch, idx):
    ratio = np.abs(eopatch.bbox.max_x - eopatch.bbox.min_x) / np.abs(eopatch.bbox.max_y - eopatch.bbox.min_y)
    fig, ax = plt.subplots(figsize=(ratio * 10, 10))
    
    ax.imshow(2.5*eopatch.data['BANDS'][..., [2, 1, 0]][idx])
    
    observed = closing(eopatch.mask['PESTICIDE_MASK'][idx,...,0], disk(1))
    nominal = sobel(eopatch.mask_timeless['NOMINAL_PESTICIDE'][...,0])
    observed = sobel(observed)
    nominal = np.ma.masked_where(nominal == False, nominal)
    observed = np.ma.masked_where(observed == False, observed)
    
    ax.imshow(nominal, cmap=plt.cm.Reds)
    ax.imshow(observed, cmap=plt.cm.Blues)
    ax.axis('off')

plot_rgb_w_pesticide(patch, 0)
plot_rgb_w_pesticide(patch, -1)

def plot_pesticide_levels(eopatch, max_coverage=1.0):
    fig, ax = plt.subplots(figsize=(20, 7))

    dates = np.asarray(eopatch.timestamp)
    ax.plot(dates[eopatch.scalar['COVERAGE'][...,0] < max_coverage],
            eopatch.scalar['PESTICIDE_LEVEL'][eopatch.scalar['COVERAGE'][...,0] < max_coverage],
            'bo-', alpha=0.7)
    ax.plot(dates[eopatch.scalar['COVERAGE'][...,0] < max_coverage],
            eopatch.scalar['COVERAGE'][eopatch.scalar['COVERAGE'][...,0] < max_coverage],
            '--', color='gray', alpha=0.7)
    ax.set_ylim(0.0, 1.1)
    ax.set_xlabel('Date')
    ax.set_ylabel('Pesticide level')
    ax.set_title('Field Pesticide Levels')
    ax.grid(axis='y')
    return ax

ax = plot_pesticide_levels(patch, 1.0)

plt.show()