from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import StructField, StructType, DoubleType, LongType

KAFKA_BROKERS = "kafka-broker-1:19092,kafka-broker-2:19092,kafka-broker-3:19092"
SOURCE_TOPIC = "financial_transactions"
AGGREGATES_TOPIC = "transaction_aggregates"
ANOMOLIES_TOPIC = "transaction_anomalies"
CHECKPOINT_DIR = "mnt/spark-checkpoint"
STATES_DIR = "mnt/spark-state"

spark = (SparkSession
  .builder
  .appName("FinancialTransactionsProcessor")
  .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13")
  .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_DIR)
  .config("spark.sql.streaming.stateStoreDir", STATES_DIR)
  .config("spark.sql.shuffle.partitions", 5)
  .getOrCreate()
  )

spark.sparkContext.setLogLevel("WARN")

transaction_schema = StructType([
    StructField("transactionId", StringType(), True),
    StructField("userId", StringType(), True),
    StructField("merchantId", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("transactionTime", LongType(), True),
    StructField("transactionType", StringType(), True),
    StructField("location", StringType(), True),
    StructField("paymentMethod", StringType(), True),
    StructField("isInternational", StringType(), True),
    StructField("currency", StringType(), True),
])

kafka_stream = (spark.readStream
  .format("kafka")
  .option("kafka.bootstrap.servers", KAFKA_BROKERS)
  .option("subscribe", SOURCE_TOPIC)
  .option("startingOffsets", "earliest")
  .load()
)

transactions_df = kafka_stream.selectExpr("CAST(value AS STRING) as transaction").select(from_json(col("transaction"), transaction_schema).alias("data")).select("data.*")

print("transaction df schema", transactions_df)

transactions_df = transactions_df.withColumn("transactionTimestamp", date_format(from_unixtime(col("transactionTime")), "yyyy-MM-dd HH:mm:ss"))

aggregated_df = (transactions_df.groupby("merchantId")
    .agg(
    sum("amount").alias('totalAmount'),
    count("*").alias("transactionCount"))
  )

aggregation_query = (aggregated_df
    .withColumn("key", col('merchantId').cast("string"))
    .withColumn("value", to_json(
      struct(
        col("merchantId"),
        col('totalAmount'),
        col("transactionCount")
      )
    )).selectExpr("key", "value")
    .writeStream
    .format('kafka')
    .outputMode('update')
    .option('kafka.bootstrap.servers', KAFKA_BROKERS)
    .option('topic', AGGREGATES_TOPIC)
    .option('checkpointLocation', f'{CHECKPOINT_DIR}/aggregates')
    .start().awaitTermination()
  )