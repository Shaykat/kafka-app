import sys
import json
import redis
import aiohttp
import backoff
import asyncio
import logging
from confluent_kafka import Producer, KafkaException
from confluent_kafka.serialization import StringSerializer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WikimediaKafkaProducer:
    def __init__(self, bootstrap_servers, topic, event_url, redis_host, redis_port, redis_db):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.event_source_url = event_url
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.producer = None
        self.session = None
        self.redis_client = None
        self.running = False

    async def start_producer(self):
        try:
            conf = {
                'bootstrap.servers': self.bootstrap_servers,
            }
            self.producer = Producer(conf)
            self.string_serializer = StringSerializer('utf_8')
            logger.info("Kafka producer started.")
            await self._start_redis_client()
            self.session = aiohttp.ClientSession()
            self.running = True
        except Exception as e:
            logger.error(f"Error starting producer: {e}")
            self.running = False
            raise

    async def stop_producer(self):
        self.running = False
        if self.producer:
            try:
                self.producer.flush()
                logger.info("Kafka producer stopped.")
            except Exception as e:
                logger.error(f"Error stopping producer: {e}")
        if self.session:
            try:
                await self.session.close()
                logger.info("Aiohttp session closed.")
            except Exception as e:
                logger.error(f"Error closing aiohttp session: {e}")
        if self.redis_client:
            try:
                await self._stop_redis_client()
            except Exception as e:
                logger.error(f"Error closing redis client: {e}")

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

    def extract_id(self, json_string):
        try:
            # data = json.loads(json_string)
            data = json_string
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

    @backoff.on_exception(backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=5)
    async def fetch_events(self):
        async with self.session.get(self.event_source_url) as resp:
            async for line in resp.content.iter_any():
                yield line

    def on_success_or_error(self, err, msg):
        if err is not None:
            logger.error(f'Message delivery failed: {err}')
        else:
            # self.redis_client.incr(window_key)
            message_value = msg.value()
            message_string = json.loads(message_value.decode('utf-8'))
            message_id = self.extract_id(message_string)
            print(message_id)
            self.redis_client.incr(message_id)
            logger.info(f'Message delivered to {msg.topic()} [{msg.partition()}] {message_id}')

    async def produce_message(self, message):
        try:
            message_str = json.dumps(message)
            try:
                self.producer.produce(
                    self.topic,
                    self.string_serializer(message_str, None),
                    callback=self.on_success_or_error
                )
                self.producer.flush()
            except KafkaException as e:
                logger.error(f"Kafka error: {e}")
            except BufferError as e:
                logger.error(f"Local producer queue is full ({len(self.producer)} messages awaiting delivery): try increasing queue.buffering.max.messages")
            except Exception as e:
                logger.exception(f"Error producing message: {e}")
        except Exception as e:
            logger.exception(f"Error in produce_message(): {e}")

    async def produce_changes(self):
        try:
            async for event in self.fetch_events():
                event = event.strip()
                event = event.split(b"\n\n")[0]
                if event.startswith(b'event:'):
                    continue
                if event.startswith(b'data:'):
                    try:
                        message = json.loads(event.decode()[len('data:'):].strip())
                        message_id = self.extract_id(message) # "04582276-f073-42e6-8cf7-7ee2383d3858"
                        logger.info(f"message_id: {message_id}")
                        if "type" not in message:
                            logger.warning(f"Skipping invalid message: {message}")
                            continue
                        count = self.redis_client.get(message_id)
                        print(count)
                        if not count:
                            await self.produce_message(message)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON: {e}, event: {event}")
                    except Exception as ex:
                        logger.exception(f"Error processing event: {ex}")
        except Exception as e:
            logger.exception(f"Error in produce_changes(): {e}")

    async def run(self):
        try:
            await self.start_producer()
            if self.running:
                while self.running:
                    await self.produce_changes()
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in run(): {e}")
        finally:
            await self.stop_producer()


async def main():
    bootstrap_servers = "localhost:9092"
    topic = "wikimedia.local"
    redis_host = "localhost"
    redis_port = 6379
    redis_db = 0
    source_event_url = "https://stream.wikimedia.org/v2/stream/recentchange"
    producer = WikimediaKafkaProducer(bootstrap_servers, topic, source_event_url, redis_host, redis_port, redis_db)
    try:
        await producer.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
    finally:
        await producer.stop_producer()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        else:
            raise
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
