import base64
import json
import pika
from llm import LLM
import os
from urllib.parse import urlparse


class LLMConsumer:
    def __init__(self, amqp_url):
        # Parse the AMQP URL
        url_parts = urlparse(amqp_url)

        rabbitmq_params = {
            "host": url_parts.hostname,
            "port": url_parts.port or 5672,  # Default port for AMQP
            "virtualhost": url_parts.path[1:] if url_parts.path else "/",
            "login": url_parts.username,
            "password": url_parts.password,
        }

        # Establish a secure connection using the AMQPS protocol
        connection_params = pika.ConnectionParameters(
            host=rabbitmq_params["host"],
            port=rabbitmq_params["port"],
            virtual_host=rabbitmq_params["virtualhost"],
            credentials=pika.PlainCredentials(
                rabbitmq_params["login"], rabbitmq_params["password"]
            ),
        )

        self.connection = pika.BlockingConnection(connection_params)
        self.channel = self.connection.channel()

    def create_consumer(self):
        # Specify the exchange type when creating the exchange
        self.channel.exchange_declare(
            exchange="upload_exchange", exchange_type="direct", durable=True
        )

        queue = self.channel.queue_declare(queue="upload_queue", durable=True)
        self.channel.queue_bind(
            exchange="upload_exchange", queue="upload_queue", routing_key="resume_pdf"
        )

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue="upload_queue", on_message_callback=self.on_message
        )

        print("Waiting for messages")
        self.channel.start_consuming()

    def on_message(self, channel, method_frame, header_frame, body):
        message = json.loads(body.decode())
        username = message.get("username")
        job_desc = message.get("job_desc")

        # Decode the base64-encoded content back to bytes
        file_content_base64 = message.get("file_content")
        file_content = base64.b64decode(file_content_base64.encode())

        pdf_filename = f"{username}.pdf"  # Adjust the filename as needed
        with open(pdf_filename, "wb") as pdf_file:
            pdf_file.write(file_content)

        pdf_processor = LLM(pdf_filename)
        documents = pdf_processor.load_pdf()
        # embedding = pdf_processor.generate_embedings(documents)
        print(job_desc)
        print(documents)
        os.remove(pdf_filename)
        self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)


if __name__ == "__main__":
    consumer = LLMConsumer()
    consumer.create_consumer()
