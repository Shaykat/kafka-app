import asyncio
import json
import logging
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from opensearchpy import OpenSearch, helpers
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OpenSearchIndexer:
    def __init__(self, host, port, index_name, username=None, password=None):
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=(username, password) if username else None,
            use_ssl=False,  # Adjust if using SSL
            verify_certs=False, # Adjust if using SSL
            ssl_assert_hostname=False, # Adjust if using SSL
        )
        self.index_name = index_name
        self.actions = []
        self.max_bulk_size = 1000

    async def create_index(self):
        if not self.client.indices.exists(index=self.index_name):
            try:
                self.client.indices.create(index=self.index_name)
                logger.info(f"Index '{self.index_name}' created.")
            except Exception as e:
                logger.error(f"Error creating index: {e}")

    async def index_document(self, doc_id, document):
        action = {
            "_index": self.index_name,
            "_id": doc_id,
            "_source": document
        }
        self.actions.append(action)
        if len(self.actions) >= self.max_bulk_size:
            await self.bulk_index()

    async def bulk_index(self):
        if self.actions:
            try:
                helpers.bulk(self.client, self.actions)
                logger.info(f"Indexed {len(self.actions)} documents.")
                self.actions = []  # Clear the actions list after successful bulk indexing
            except Exception as e:
                logger.error(f"Error during bulk indexing: {e}")

    async def close(self):
        await self.bulk_index()  # Index any remaining documents before closing
        self.client.close()
        logger.info("OpenSearch client closed.")


class KafkaToOpenSearch:
    def __init__(self, bootstrap_servers, topic, opensearch_indexer):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.indexer = opensearch_indexer

    async def consume_and_index(self):
        consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda v: json.loads(v),
            auto_offset_reset='latest'
        )
        await consumer.start()
        try:
            while True:
                async for msg in consumer:
                    try:
                        if 'meta' in msg.value and 'id' in msg.value['meta']:
                            doc_id = msg.value['meta']['id']
                            await self.indexer.index_document(doc_id, msg.value)
                        else:
                            logger.warning(f"Message does not contain id: {msg.value}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}, Message: {msg.value}")
        finally:
            await consumer.stop()
            await self.indexer.close()

async def main():
    bootstrap_servers = "localhost:9092"  # Replace with your Kafka bootstrap servers
    topic = "wikimedia.local"    # Replace with your Kafka topic
    opensearch_host = "localhost"      # Replace with your OpenSearch host
    opensearch_port = 9200             # Replace with your OpenSearch port
    index_name = "wikimedia"            # Replace with your OpenSearch index name

    # Create indexer object
    indexer = OpenSearchIndexer(opensearch_host, opensearch_port, index_name)
    await indexer.create_index()

    # Create Kafka to OpenSearch object
    kafka_opensearch = KafkaToOpenSearch(bootstrap_servers, topic, indexer)
    await kafka_opensearch.consume_and_index()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
