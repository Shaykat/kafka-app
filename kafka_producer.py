import json
from kafka import KafkaProducer
from kafka.errors import KafkaError


def on_send_success(record_metadata):
    print(record_metadata.topic)
    print(record_metadata.partition)
    print(record_metadata.offset)

def on_send_error(excp):
    print(f'I am an errback {excp}')
    

if __name__ == "__main__":
    producer = KafkaProducer(
        bootstrap_servers=['10.0.0.38:9092'], 
        value_serializer=lambda m: json.dumps(m).encode('ascii'), 
        retries=5
    )
    print("Producer Created Successfully")

    for _ in range(10):
        producer.send(topic='sh-topic', value={'name': f'shaykat-message-{_}'}).add_callback(on_send_success).add_errback(on_send_error)
        # producer.send('sh-topic', {'name': f'shaykat-message-{_}'})
        print(f"Message {_} is produced successfully...")
    
    # block until all async messages are sent
    producer.flush()
