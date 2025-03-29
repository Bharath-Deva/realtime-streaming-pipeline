import json
from locale import currency
from math import e
import random
import threading
import time
import uuid
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

import logging
logging.basicConfig(
  level=logging.INFO,
)
logger = logging.getLogger(__name__)

KAFKA_BROKERS = "localhost:29092,localhost:39092,localhost:49092"
NUM_PARTITIONS = 5
REPLICATION_FACTOR = 3
TOPIC_NAME = "financial_transactions"
AGGREGATES_TOPIC = "transaction_aggregates"
ANOMOLIES_TOPIC = "transaction_anomalies"


producer_conf = {
  "bootstrap.servers": KAFKA_BROKERS,
  "queue.buffering.max.messages": 10000,
  "queue.buffering.max.kbytes": 512000,
  "batch.num.messages": 1000,
  "linger.ms": 50,
  "acks": 1,
  "compression.type": "gzip"
}

producer = Producer(producer_conf)

def create_topic(topic_name):
  admin_client = AdminClient({"bootstrap.servers": KAFKA_BROKERS})
  
  try:
    metadata = admin_client.list_topics()
    print(metadata.topics)
    if topic_name not in metadata.topics:
      topic = NewTopic(
        topic_name, 
        num_partitions=NUM_PARTITIONS, 
        replication_factor=REPLICATION_FACTOR
      )
      
      fs = admin_client.create_topics([topic])
      for topic, f in fs.items():
        try:
          f.result()
          logger.info(f"Topic {topic} created")
        except Exception as e:
          logger.error(f"Failed to create topic {topic}: {e}")
  except Exception as e:
    logger.error(f"Error creating Topic: {e}")
  return

def generate_transaction():
  return dict(
    transactionId = str(uuid.uuid4()),
    userId = f"user_{random.randint(1, 100)}",
    amount = random.uniform(500, 150000),
    transactionTime = int(time.time()),
    merchantId = random.choice(["merchant_1", "merchant_2", "merchant_3", "merchant_4", "merchant_5"]),
    transactionType = random.choice(["purchase", "refund"]),
    location = f'location_{random.randint(1, 50)}',
    payment_method = random.choice(["credit_card", "debit_card", "upi", "net_banking"]),
    isInternational = random.choice([True, False]),
    currency = random.choice(["USD", "INR", "EUR", "GBP", "JPY"])
  )

def produce_transaction(thread_id):
  while True:
    transaction = generate_transaction()
    
    try:
      producer.produce(
        topic=TOPIC_NAME, 
        key=transaction["userId"],
        value = json.dumps(transaction).encode("utf-8"),
        on_delivery = lambda err, msg: logger.info(f"Failed to deliver message: {err}") if err else logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")
      )
      print(f"Thread {thread_id} Produced transaction: {transaction}")
      producer.flush()
    except Exception as e:
      logger.error(f"Error producing transaction: {e}")


if __name__ == "__main__":
  create_topic(TOPIC_NAME)
  create_topic(AGGREGATES_TOPIC)
  create_topic(ANOMOLIES_TOPIC)
  threads = []
  try:
    for i in range(5):
      thread = threading.Thread(target=produce_transaction, args=(i,))
      thread.daemon = True
      thread.start()
      threads.append(thread)
      
    for thread in threads:
      thread.join()
  except Exception as e:
    print(f"Error in main: {e}")