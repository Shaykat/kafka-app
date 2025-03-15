import asyncio
import json
from kafka import KafkaConsumer, KafkaProducer
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from datetime import datetime, timedelta
import redis
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WindowedTimeSeriesCounter:
    def __init__(self, bootstrap_servers, input_topic, output_topic, redis_host="redis", redis_port=6379, redis_db="redis", window_size_seconds=10):
        self.bootstrap_servers = bootstrap_servers
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.window_size_seconds = window_size_seconds
        self.redis_client = None
        self.producer = None
        self.consumer = None

    def extract_id(json_string):
        """Extracts the 'id' field from a JSON string, handling potential errors."""
        try:
            data = json.loads(json_string)
            if isinstance(data, dict) and "meta" in data and isinstance(data["meta"], dict) and "id" in data["meta"]:
                return data["meta"]["id"]
            else:
                logger.warning("JSON structure does not contain 'meta' or 'id': %s", json_string)
                return None
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON: %s, Error: %s", json_string, e)
            return None 
        except Exception as e:
            logger.exception("An unexpected error occurred:", exc_info=True)
            return None

    
    async def _start_redis_client(self):
        self.redis_client = redis.StrictRedis(
            host=self.redis_host, 
            port=self.redis_port, 
            db=self.redis_db
        )
        logger.info("Redis client created.")
    
    async def _stop_redis_client(self):
        await self.redis_client.close()
        logger.info("Redis client closed.")

    async def _start_producer(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka producer started.")

    async def _stop_producer(self):
        if self.producer:
            await self.producer.flush()
            await self.producer.stop()
            logger.info("Kafka producer stopped.")

    async def _start_consumer(self):
        self.consumer = AIOKafkaConsumer(
            self.input_topic,
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda v: json.loads(v),
            auto_offset_reset='latest'
        )
        await self.consumer.start()
        logger.info("Kafka Consumer started.")

    async def _stop_consumer(self):
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped.")

    async def process_events(self):
        try:
            while True:
                async for msg in self.consumer:
                    try:
                        key = "event_count"
                        event_data = msg.value
                        timestamp = datetime.fromtimestamp(event_data["timestamp"])  #assuming timestamp is in ms
                        await self.update_window_counts(key, timestamp)
                        self.consumer.commit() #commit offset to avoid re-processing
                    except Exception as e:
                        logger.error(f"Error processing message: {e}, Message:{msg.value}")
        except Exception as e:
            logger.exception("An unexpected error occurred in the main loop")
        finally:
            self.close()

    async def update_window_counts(self, key, timestamp):
        window_start = timestamp - timedelta(seconds=timestamp.second % self.window_size_seconds, microseconds=timestamp.microsecond)
        window_end = window_start + timedelta(seconds=self.window_size_seconds)

        window_key = f"{key}:{window_start.isoformat()}:{window_end.isoformat()}"

        # Atomically increment the count in Redis
        self.redis_client.incr(window_key)

        # Check if it's time to send data to output topic
        if datetime.now() > window_end:
            count = self.redis_client.get(window_key)
            if count:
                self.send_to_output(key, window_start, window_end, self.window_size_seconds * 1000, int(count))
                self.redis_client.delete(window_key) #remove after sending

    async def send_to_output(self, key, window_start, window_end, window_size_ms, count):
        record = {
            "key": key,
            "start_time": window_start.isoformat(),
            "end_time": window_end.isoformat(),
            "window_size_ms": window_size_ms,
            "event_count": count,
        }
        try:
            await self.producer.send_and_wait(self.output_topic, key=key.encode('utf-8'), value=json.dumps(record).encode('utf-8'))
            self.producer.flush()
            logger.info(f"Sent window count to {self.output_topic}: {record}")
        except Exception as e:
            logger.error(f"Error sending to output topic: {e}")


    def close(self):
        if self.consumer:
            self._stop_consumer()
        if self.producer:
            self._stop_producer()
        if self.redis_client:
            self._stop_redis_client()
    
    async def run(self):
        await self._start_producer()
        await self._start_consumer()
        await self._start_redis_client()
        await self.process_events()

async def main():
    bootstrap_servers = "localhost:9092"
    input_topic = "wikimedia.local"
    output_topic = "wikimedia.stats.timeseries"
    redis_host = "localhost"
    redis_port = 6379
    redis_db = 0
    window_size_seconds = 20
    counter = WindowedTimeSeriesCounter(bootstrap_servers, input_topic, output_topic, redis_host, redis_port, redis_db, window_size_seconds)
    await counter.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
