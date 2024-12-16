from kafka_client import *


if __name__ == "__main__":
    topic_list = []

    print("Admin connecting...")
    admin_client = init_kafka_client()
    print("Adming Connection Success...")

    print("Creating Topic [sh-topic]")
    topic = NewTopic(name="sh-topic", num_partitions=1, replication_factor=1)
    topic_list.append(topic)
    admin_client.create_topics(new_topics=topic_list, validate_only=False)
    print("Topic Created Success [sh-topic]")
