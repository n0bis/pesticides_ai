import subprocess

from datetime import date, datetime, time, timedelta

import matplotlib.pyplot as plt
import numpy as np

from ipyleaflet import GeoJSON, Map, basemaps


from eolearn.core import (
    EOExecutor,
    EOPatch,
    EOTask,
    FeatureType,
    LinearWorkflow,
    LoadTask,
    OverwritePermission,
    SaveTask,
    ZipFeatureTask,
)
from eolearn.coregistration import ECCRegistration
from eolearn.features import (
    LinearInterpolation,
    SimpleFilterTask,
    NormalizedDifferenceIndexTask,
)
from eolearn.io import (
    ExportToTiff,
    ImportFromTiff,
    SentinelHubInputTask,
    SentinelHubEvalscriptTask,
)
from eolearn.mask import CloudMaskTask, AddValidDataMaskTask

from sentinelhub import (
    CRS,
    BatchSplitter,
    BBox,
    BBoxSplitter,
    DataCollection,
    Geometry,
    MimeType,
    SentinelHubBatch,
    SentinelHubRequest,
    SHConfig,
    bbox_to_dimensions,
)

config = SHConfig()

config.sh_client_id = "7850cd4c-504b-4996-9e2d-9b75dadd9b2a"
config.sh_client_secret = "26jJvL>j<u_WIl&OP@S]jk|TEU|~mLW3pgH}-RSh"
# 26jJvL>j<u_WIl&OP@S]jk|TEU|~mLW3pgH}-RSh
config.save()

dates = []
ndvi = []

class SentinelHubValidData:
    """
    Combine Sen2Cor's classification map with `IS_DATA` to define a `VALID_DATA_SH` mask
    The SentinelHub's cloud mask is asumed to be found in eopatch.mask['CLM']
    """
    def __call__(self, eopatch):      
        return eopatch.mask['IS_DATA'].astype(bool) & np.logical_not(eopatch.mask['CLM'].astype(bool))
    
class AddValidCountTask(EOTask):   
    """
    The task counts number of valid observations in time-series and stores the results in the timeless mask.
    """
    def __init__(self, count_what, feature_name):
        self.what = count_what
        self.name = feature_name
        
    def execute(self, eopatch):
        eopatch[(FeatureType.MASK_TIMELESS, self.name)] = np.count_nonzero(eopatch.mask[self.what], axis=0)
        return eopatch

class AnimateTask(EOTask):
    def __init__(
        self,
        image_dir,
        out_dir,
        out_name,
        feature=(FeatureType.DATA, "NDVI"),
        scale_factor=2.5,
        duration=3,
        dpi=150,
        pad_inches=None,
        shape=None,
    ):
        self.image_dir = image_dir
        self.out_name = out_name
        self.out_dir = out_dir
        self.feature = feature
        self.scale_factor = scale_factor
        self.duration = duration
        self.dpi = dpi
        self.pad_inches = pad_inches
        self.shape = shape

    def execute(self, eopatch):
        images = np.clip(eopatch[self.feature] * self.scale_factor, 0, 1)
        fps = len(images) / self.duration
        subprocess.run(f"rm -rf {self.image_dir} && mkdir {self.image_dir}", shell=True)

        for idx, image in enumerate(images):
            if self.shape:
                fig = plt.figure(figsize=(self.shape[0], self.shape[1]))
            ndvi = eopatch.data['NDVI'][idx]
            mask = eopatch.mask['IS_VALID'][idx]
            t, w, h = ndvi.shape

            ndvi_clean = ndvi.copy()
            ndvi_clean[~mask] = np.nan  # Set values of invalid pixels to NaN's

            # Calculate means, remove NaN's from means
            ndvi_mean_clean = np.nanmean(ndvi_clean.reshape(t, w * h), axis=1)
            ndvi_mean_clean = ndvi_mean_clean[~np.isnan(ndvi_mean_clean)]
            image = image[..., 0].squeeze()
            print(ndvi_mean_clean)
            plt.imshow(image)
            plt.axis(False)
            plt.savefig(
                f'{self.image_dir}/image_{eopatch["timestamp"][idx]}.png',
                bbox_inches="tight",
                dpi=self.dpi,
                pad_inches=self.pad_inches,
            )
            plt.close()
        return eopatch


# https://twitter.com/Valtzen/status/1270269337061019648
bbox = BBox(bbox=[9.094491, 55.473442, 9.102162, 55.476142], crs=CRS.WGS84)
resolution = 1
time_interval = ("2021-01-01", "2021-12-01")
print(f"Image size: {bbox_to_dimensions(bbox, resolution)}")

geom, crs = bbox.geometry, bbox.crs
wgs84_geometry = Geometry(geom, crs).transform(CRS.WGS84)
geometry_center = wgs84_geometry.geometry.centroid

map1 = Map(
    basemap=basemaps.Esri.WorldImagery,
    center=(geometry_center.y, geometry_center.x),
    zoom=13,
)

area_geojson = GeoJSON(data=wgs84_geometry.geojson)
map1.add_layer(area_geojson)

band_names = ['B02', 'B03', 'B04', 'B08', 'B11', 'B12']
add_data = SentinelHubInputTask(
    bands_feature=(FeatureType.DATA, 'BANDS'),
    bands = band_names,
    resolution=10,
    maxcc=0.8,
    time_difference=timedelta(minutes=120),
    data_collection=DataCollection.SENTINEL2_L1C,
    additional_data=[(FeatureType.MASK, 'dataMask', 'IS_DATA'),
                     (FeatureType.MASK, 'CLM'),
                     (FeatureType.DATA, 'CLP')],
    max_threads=5
)

ndvi = NormalizedDifferenceIndexTask((FeatureType.DATA, 'BANDS'), (FeatureType.DATA, 'NDVI'), 
                                     [band_names.index('B08'), band_names.index('B04')])


# VALIDITY MASK
# Validate pixels using SentinelHub's cloud detection mask and region of acquisition 
add_sh_validmask = AddValidDataMaskTask(SentinelHubValidData(), 'IS_VALID')

# COUNTING VALID PIXELS
# Count the number of valid observations per pixel using valid data mask 
add_valid_count = AddValidCountTask('IS_VALID', 'VALID_COUNT')

name = "clm_service"
anim_task = AnimateTask(
    image_dir="./ndvi_images",
    out_dir="./animations",
    out_name=name,
    duration=5,
    dpi=200,
)



workflow = LinearWorkflow(
    add_data,
    ndvi,
    add_sh_validmask,
    add_valid_count,
    anim_task
)

result = workflow.execute(
    {add_data: {"bbox": bbox, "time_interval": time_interval}}
)
patch = list(result.values())[-1]


def plot_pesticide_levels(eopatch):
    #fig, ax = plt.subplots(figsize=(20, 7))

    ndvi = eopatch.data['NDVI']
    mask = eopatch.mask['IS_VALID']
    time = np.array(eopatch.timestamp)
    t, w, h, _ = ndvi.shape

    ndvi_clean = ndvi.copy()
    ndvi_clean[~mask] = np.nan  # Set values of invalid pixels to NaN's

    # Calculate means, remove NaN's from means
    ndvi_mean = np.nanmean(ndvi.reshape(t, w * h), axis=1)
    ndvi_mean_clean = np.nanmean(ndvi_clean.reshape(t, w * h), axis=1)
    time_clean = time[~np.isnan(ndvi_mean_clean)]
    ndvi_mean_clean = ndvi_mean_clean[~np.isnan(ndvi_mean_clean)]

    #ax.plot(dates, ndvi, "bo-", alpha=0.7)
    #ax.set_ylim(0.0, 1.1)
    #ax.set_xlabel("Date")
    #ax.set_ylabel("NDVI level")
    #ax.set_title("Field NDVI Levels")
    #ax.grid(axis="y")
    #return ax
    fig, ax = plt.subplots(figsize=(20, 5))
    ax.plot(time_clean, ndvi_mean_clean, 's-', label = 'Mean NDVI with cloud cleaning')
    #plt.plot(time, ndvi_mean, 'o-', label='Mean NDVI without cloud cleaning')
    ax.set_xlabel('Time', fontsize=15)
    ax.set_ylabel('Mean NDVI', fontsize=15)
    #ax.set_xticks(fontsize=15)
    #ax.set_yticks(fontsize=15)

    plt.legend(loc=2, prop={'size': 15})
    return ax


ax = plot_pesticide_levels(patch)

plt.show()
