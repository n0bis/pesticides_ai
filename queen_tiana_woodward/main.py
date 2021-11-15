from pyspark.sql import SparkSession
from pyspark.sql.types import StructType
from pyspark.sql.functions import explode, split, to_json, array, col
import locale
from PIL import Image
from StringIO import StringIO
import base64
import numpy as np
import cv2
locale.getdefaultlocale()
locale.getpreferredencoding()

def load_image_into_numpy_array(image):
        """Convert PIL image to numpy array."""
        (im_width, im_height) = image.size
        return np.array(image.getdata()).reshape(
            (im_height, im_width, 3)).astype(np.uint8)

# Create SparkSession and configure it
spark = SparkSession.builder.appName('streamTest') \
    .config('spark.master','spark://spark-master:7077') \
    .config('spark.executor.cores', 1) \
    .config('spark.cores.max',1) \
    .config('spark.executor.memory', '1g') \
    .config('spark.sql.streaming.checkpointLocation','hdfs://namenode:9000/stream-checkpoint/') \
    .getOrCreate()
    
# Create a read stream from Kafka and a topic
df = spark \
  .readStream \
  .format("kafka") \
  .option("kafka.bootstrap.servers", "kafka:9092") \
  .option("subscribe", "images") \
  .load()

# Cast to string
image_bytes = df.selectExpr("CAST(value AS STRING)")

# convert image bytes data to numpy array of dtype uint8
nparr = np.frombuffer(image_bytes.value(), np.uint8)

# decode image
img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
print(img)