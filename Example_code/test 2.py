
import subprocess
import os
from datetime import date, datetime, time, timedelta

import matplotlib.pyplot as plt
import numpy as np
np.random.seed(42)
import geopandas as gpd

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
                         SentinelHubRequest, SHConfig, bbox_to_dimensions, UtmZoneSplitter)

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


if __name__ == '__main__':

  config = SHConfig()

  config.sh_client_id = 'ad7914e4-e35e-479d-9639-544d652a3cbf'
  config.sh_client_secret = 'G?[k1-2<(tjYC0[L(<-&Y8uol8.mQz/X{?n<Iex2'
  config.save()

  path = os.path.abspath('')
  # Folder where data for running the notebook is stored
  DATA_FOLDER = os.path.join('..', '..', 'example_data')
  # Locations for collected data and intermediate results
  EOPATCH_FOLDER = os.path.join('.', 'eopatches')
  EOPATCH_SAMPLES_FOLDER = os.path.join('.', 'eopatches_sampled')
  RESULTS_FOLDER = os.path.join('.', 'results')
  os.makedirs(EOPATCH_FOLDER, exist_ok=True)
  os.makedirs(EOPATCH_SAMPLES_FOLDER, exist_ok=True)
  os.makedirs(RESULTS_FOLDER, exist_ok=True)

  country = gpd.read_file(f'{path}/Example_code/denmark.geojson')
  country = country.buffer(500)
  country_shape = country.geometry.values[0]
  bbox_splitter = UtmZoneSplitter([country_shape], country.crs, 5000)

  bbox_list = np.array(bbox_splitter.get_bbox_list())
  info_list = np.array(bbox_splitter.get_info_list())

  ID = 461

  patchIDs = []
  for idx, (bbox, info) in enumerate(zip(bbox_list, info_list)):
      if (abs(info['index_x'] - info_list[ID]['index_x']) <= 2 and
        abs(info['index_y'] - info_list[ID]['index_y']) <= 2):
        patchIDs.append(idx)
  
  patchIDs = np.transpose(np.fliplr(np.array(patchIDs).reshape(7, 7))).ravel()

    # Display bboxes over country
  fig, ax = plt.subplots(figsize=(30, 30))
  ax.set_title('Selected 5x5 tiles from Denmark', fontsize=25)
  country.plot(ax=ax, facecolor='w', edgecolor='b', alpha=0.5)

  for bbox, info in zip(bbox_list, info_list):
      geo = bbox.geometry
      ax.text(geo.centroid.x, geo.centroid.y, info['index'], ha='center', va='center')
      
  # Mark bboxes of selected area
  country[country.index.isin(patchIDs)].plot(ax=ax, facecolor='g', edgecolor='r', alpha=0.5)

  plt.axis('off')

  # BAND DATA
  # Add a request for S2 bands.
  # Here we also do a simple filter of cloudy scenes (on tile level).
  # The s2cloudless masks and probabilities are requested via additional data.
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


  # CALCULATING NEW FEATURES
  # NDVI: (B08 - B04)/(B08 + B04)
  # NDWI: (B03 - B08)/(B03 + B08)
  # NDBI: (B11 - B08)/(B11 + B08)
  ndvi = NormalizedDifferenceIndexTask((FeatureType.DATA, 'BANDS'), (FeatureType.DATA, 'NDVI'), 
                                      [band_names.index('B08'), band_names.index('B04')])
  ndwi = NormalizedDifferenceIndexTask((FeatureType.DATA, 'BANDS'), (FeatureType.DATA, 'NDWI'), 
                                      [band_names.index('B03'), band_names.index('B08')])
  ndbi = NormalizedDifferenceIndexTask((FeatureType.DATA, 'BANDS'), (FeatureType.DATA, 'NDBI'), 
                                      [band_names.index('B11'), band_names.index('B08')])



  # VALIDITY MASK
  # Validate pixels using SentinelHub's cloud detection mask and region of acquisition 
  add_sh_validmask = AddValidDataMaskTask(SentinelHubValidData(), 'IS_VALID')

  # COUNTING VALID PIXELS
  # Count the number of valid observations per pixel using valid data mask 
  add_valid_count = AddValidCountTask('IS_VALID', 'VALID_COUNT')

  # SAVING TO OUTPUT (if needed)
  save = SaveTask(EOPATCH_FOLDER, overwrite_permission=OverwritePermission.OVERWRITE_PATCH)

  # Define the workflow
  workflow = LinearWorkflow(
      add_data,
      ndvi,
      ndwi,
      ndbi,
      add_sh_validmask,
      add_valid_count,
      save
  )

  # Let's visualize it
  workflow.dependency_graph()

  # Time interval for the SH request
  time_interval = ['2019-01-01', '2019-12-31'] 

  # Define additional parameters of the workflow
  execution_args = []
  for idx, bbox in enumerate(bbox_list[patchIDs]):
    execution_args.append({
        add_data: {'bbox': bbox, 'time_interval': time_interval},
        save: {'eopatch_folder': f'eopatch_{idx}'}
    })
      
  # Execute the workflow
  executor = EOExecutor(workflow, execution_args, save_logs=True)
  executor.run(workers=5, multiprocess=True)

  executor.make_report()

  failed_ids = executor.get_failed_executions()
  if failed_ids:
      raise RuntimeError(f'Execution failed EOPatches with IDs:\n{failed_ids}\n'
                        f'For more info check report at {executor.get_report_filename()}')

  eopatch = EOPatch.load(os.path.join(EOPATCH_FOLDER, f'eopatch_{0}'), lazy_loading=True)
  ndvi = eopatch.data['NDVI']
  mask = eopatch.mask['IS_VALID']
  time = np.array(eopatch.timestamp)
  t, w, h, _ = ndvi.shape

  ndvi_clean = ndvi.copy()
  ndvi_clean[~mask] = np.nan  # Set values of invalid pixels to NaN's
  print(t, w, h, ndvi.reshape(t, w * h))
  # Calculate means, remove NaN's from means
  ndvi_mean = np.nanmean(ndvi.reshape(t, w * h), axis=1)
  ndvi_mean_clean = np.nanmean(ndvi_clean.reshape(t, w * h), axis=1)
  time_clean = time[~np.isnan(ndvi_mean_clean)]
  ndvi_mean_clean = ndvi_mean_clean[~np.isnan(ndvi_mean_clean)]

  fig = plt.figure(figsize=(20,5))
  plt.plot(time_clean, ndvi_mean_clean, 's-', label = 'Mean NDVI with cloud cleaning')
  plt.plot(time, ndvi_mean, 'o-', label='Mean NDVI without cloud cleaning')
  plt.xlabel('Time', fontsize=15)
  plt.ylabel('Mean NDVI over patch', fontsize=15)
  plt.xticks(fontsize=15)
  plt.yticks(fontsize=15)

  plt.legend(loc=2, prop={'size': 15});