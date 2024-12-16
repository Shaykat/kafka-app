# kafka-app
This is very simple kafka project where covered the following things
- Easy containerized infrastructure setup using docker
- Create Kafka Topic
- Create Kafka Producer and Produce Messages to Topic
- Create Kafka Consumer and Consume Messages from the Topic

** Here I only used the single partition inside the topic to keep it simple. I will include that in the next release.

# Pre-requirement
You need to have docker desktop installed in your desktop

# Setup Docker & Local
- ```git clone git@github.com:Shaykat/kafka-app.git``` Clone the repository
- Navigate to the kafka-app directory
- Run the ```docker compose up -d``` It will up the kafka service with zoopkeer 
- Activate the python environment included into the repository ```source .venv/bin/activate```
- Create Topic ```python3 kafka_admin.py```
- Run Kafka Consumer so it listens for Messages to be produced in the Topic. ```python3 kafka_consumer.py```
- From Another terminal Run Producer so it produces messages to the Topic. ```python3 kafka_producer```

Now whatever messages are published to the topic will be available in the consumber console. 

# Setup Full Docker 
- ```git clone git@github.com:Shaykat/kafka-app.git``` Clone the repository
- Navigate to the kafka-app directory
- Run the ```docker compose up -d``` It will up the kafka service with zoopkeer 
- Build the Dockerfileadmin, Dockerfileproducer and Dockerfileconsumer images.
    ```
        docker build -f Dockerfileadmin -t kafka-python-admin
        docker build -f Dockerfileproducer -t kafka-python-producer
        docker build -f Dockerfileconsumer -t kafka-python-consumer
    ```
- Create Topic ```docker run -it kafka-python-admin``` This will create the kafka-topic.
- Run Kafka Consumer so it listens for Messages to be produced in the Topic. ```docker run -it kafka-python-consumer```
- From Another terminal Run Producer so it produces messages to the Topic. ```docker run -it kafka-python-producer```

Now whatever messages are published to the topic will be available in the consumber console. 