from kafka import KafkaConsumer


if __name__ == "__main__":
    consumer = KafkaConsumer(
        'sh-topic',
        group_id='sh-group',
        bootstrap_servers=['10.0.0.38:9092']
    )

    for message in consumer:
        print(f"{message.topic}:{message.partition}:{message.offset}: value={message.value}")
