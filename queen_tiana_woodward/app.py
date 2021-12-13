from pyspark.sql import SparkSession

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
  .option("kafka.bootstrap.servers", "host.docker.internal:9092") \
  .option("subscribe", "images") \
  .load()

# Cast to string
image_bytes = df.selectExpr("CAST(value AS BINARY)")

query = image_bytes \
  .writeStream \
  .queryName("Persist data") \
  .outputMode("append") \
  .format("parquet") \
  .option("path", "hdfs://namenode:9000/stream-data/") \
  .option("checkpointLocation", "hdfs://namenode:9000/stream-checkpoint/") \
  .option("truncate", False) \
  .start() \
  .awaitTermination()

#df_pd = image_bytes.toPandas()
#print(df_pd)