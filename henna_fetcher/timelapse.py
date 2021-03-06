
import subprocess

from datetime import date, datetime, time, timedelta
from kafka import KafkaProducer
from confluent_kafka import Producer
from json import dumps
import matplotlib.pyplot as plt
import numpy as np
import base64
import cv2
from producer_config import config as producer_config

from ipyleaflet import GeoJSON, Map, basemaps


from eolearn.core import (EOExecutor, EOPatch, EOTask, FeatureType,
                          LinearWorkflow, LoadTask, OverwritePermission,
                          SaveTask, ZipFeatureTask)
from eolearn.coregistration import ECCRegistration
from eolearn.features import LinearInterpolation, SimpleFilterTask, NormalizedDifferenceIndexTask
from eolearn.io import ExportToTiff, ImportFromTiff, SentinelHubInputTask, SentinelHubEvalscriptTask
from eolearn.mask import CloudMaskTask, AddValidDataMaskTask

from sentinelhub import (CRS, BatchSplitter, BBox, BBoxSplitter,
                         DataCollection, Geometry, MimeType, SentinelHubBatch,
                         SentinelHubRequest, SHConfig, bbox_to_dimensions)

config = SHConfig()

#config.sh_client_id = 'c2ddde9c-9bd8-4c8f-a716-2d7426875b24'
#config.sh_client_secret = 'ksTZi62t[J(R[t%/<t})[Hw3I:;0+dqKNI{23nrw'
config.sh_client_id = 'f938531f-ad28-4e9d-bccc-d43f39658c54'
config.sh_client_secret = '5&o>M,le~]:@6;-0tWLe::jEx<FA+-5>8vX*<mRG'
config.save()

producer = Producer(producer_config)


class AnimateTask(EOTask):
    def __init__(self, image_dir, out_dir, out_name, feature=(FeatureType.DATA, 'indices'), scale_factor=2.5, duration=3, dpi=150, pad_inches=None, shape=None):
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
        images = np.clip(eopatch[self.feature]*self.scale_factor, 0, 1)
        subprocess.run(f'rm -rf {self.image_dir} && mkdir {self.image_dir}', shell=True)
        
        for idx, image in enumerate(images):
            if self.shape:
                fig = plt.figure(figsize=(self.shape[0], self.shape[1]))
            image = image[...,0].squeeze()
            _, img_buffer_arr = cv2.imencode(".jpg", image)
            producer.produce('images', img_buffer_arr.tobytes())
            producer.flush()
            plt.imshow(image)
            plt.axis(False)
            plt.savefig(f'{self.image_dir}/image_{idx:03d}.png', bbox_inches='tight', dpi=self.dpi, pad_inches = self.pad_inches)
            plt.close()
        return eopatch

# https://twitter.com/Valtzen/status/1270269337061019648
bbox = BBox(bbox=[9.094491, 55.473442, 9.102162, 55.476142], crs=CRS.WGS84)
resolution = 1
time_interval = ('2021-10-01', '2021-11-01')
print(f'Image size: {bbox_to_dimensions(bbox, resolution)}')

geom, crs = bbox.geometry, bbox.crs
wgs84_geometry = Geometry(geom, crs).transform(CRS.WGS84)
geometry_center = wgs84_geometry.geometry.centroid

map1 = Map(
    basemap=basemaps.Esri.WorldImagery,
    center=(geometry_center.y, geometry_center.x),
    zoom=13
)

area_geojson = GeoJSON(data=wgs84_geometry.geojson)
map1.add_layer(area_geojson)

download_task = SentinelHubInputTask(
    bands = ['B04', 'B03', 'B02'],
    bands_feature = (FeatureType.DATA, 'RGB'),
    resolution=resolution,
    maxcc=0.9,
    time_difference=timedelta(minutes=120),
    data_collection=DataCollection.SENTINEL2_L2A,
    max_threads=10,
    mosaicking_order='leastCC',
    additional_data=[
        (FeatureType.MASK, 'CLM'),
        (FeatureType.MASK, 'dataMask')
    ]
)

indices_evalscript = """
    //VERSION=3

    function setup() {
        return {
            input: ["B03","B04","B08","dataMask"],
            output:[{
                id: "indices",
                bands: 2,
                sampleType: SampleType.FLOAT32
            }]
        }
    }

    function evaluatePixel(sample) {
        let ndvi = index(sample.B08, sample.B04);
        let ndwi = index(sample.B03, sample.B08);
        return {
           indices: [ndvi, ndwi]
        };
    }
"""

add_indices = SentinelHubEvalscriptTask(
    features=[(FeatureType.DATA, 'indices')],
    evalscript=indices_evalscript,
    data_collection=DataCollection.SENTINEL2_L1C,
    resolution=resolution,
    maxcc=0.9,
    time_difference=timedelta(minutes=120),
    config=config,
    max_threads=3
)

def valid_coverage_thresholder_f(valid_mask, more_than=0.95):
    coverage = np.count_nonzero(valid_mask)/np.prod(valid_mask.shape)
    return coverage > more_than

valid_mask_task = ZipFeatureTask({FeatureType.MASK: ['CLM', 'dataMask']}, (FeatureType.MASK, 'VALID_DATA'),
                                 lambda clm, dm: np.all([clm == 0, dm], axis=0))

filter_task = SimpleFilterTask((FeatureType.MASK, 'VALID_DATA'), valid_coverage_thresholder_f)

name = 'clm_service'
anim_task = AnimateTask(image_dir = './images', out_dir = './animations', out_name=name, duration=5, dpi=200)

workflow = LinearWorkflow(
    download_task,
    add_indices,
    valid_mask_task,
    filter_task,
    anim_task,
    #coreg_task,
    #anim_task_after
)

result = workflow.execute({
    download_task: {'bbox': bbox, 'time_interval': time_interval}
})
print(result.eopatch())