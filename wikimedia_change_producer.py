import asyncio
import json
import logging
from aiokafka import AIOKafkaProducer
from urllib.parse import urlparse
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WikimediaKafkaProducer:
    def __init__(self, bootstrap_servers, topic, event_url, loop=None):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.loop = loop or asyncio.get_event_loop()
        self.event_source_url = event_url
        self.producer = None  # Initialize producer here
        self.session = None  # Initialize aiohttp session here

    async def start_producer(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka producer started.")
        self.session = aiohttp.ClientSession()

    async def stop_producer(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped.")
        if self.session:
            await self.session.close()
            logger.info("Aiohttp session closed.")

    async def produce_changes(self):
        try:
            async with self.session.get("https://stream.wikimedia.org/v2/stream/recentchange") as resp:
                async for line in resp.content:
                    line = line.strip() #remove leading/trailing whitespace
                    if line.startswith(b'event:'): #ignore event headers
                        continue
                    if line.startswith(b'data:'):
                        try:
                            message = json.loads(line.decode()[len('data:'):].strip()) # remove data: prefix, decode to string
                            # Add basic message validation if needed
                            if "type" not in message:
                                logger.warning(f"Skipping invalid message: {message}")
                                continue
                            await self.producer.send_and_wait(self.topic, message)
                            logger.info(f"Sent message: {message}")
                        except json.JSONDecodeError as e:
                            logger.error(f"Error decoding JSON: {e}, line: {line}")
                        except Exception as ex:
                            logger.exception(f"Error in produce_changes(): {ex}")

        except Exception as e:
            logger.exception(f"Error in produce_changes(): {e}")

    async def run(self):
        await self.start_producer()
        await self.produce_changes()
        await self.stop_producer()


async def main():
    bootstrap_servers = "localhost:9092"  # Replace with your Kafka bootstrap servers
    topic = "wikimedia.local"  # Replace with your desired topic
    source_event_url = "https://stream.wikimedia.org/v2/stream/recentchange"
    producer = WikimediaKafkaProducer(bootstrap_servers, topic, source_event_url)
    await producer.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
