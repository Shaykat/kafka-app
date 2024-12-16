from kafka.admin import KafkaAdminClient, NewTopic

def init_kafka_client():
    admin_client = KafkaAdminClient(
        bootstrap_servers="10.0.0.38:9092", # Copy the private ip of your local machine
        client_id='kafka-app'
    )
    return admin_client