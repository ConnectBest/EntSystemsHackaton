import pika
import psycopg2
import json
import time
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "tier0admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "tier0secure")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "tier0_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "tier0user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "tier0pass")

class RabbitMQConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.postgres_conn = None
        self.message_count = 0

    def connect_postgres(self):
        """Connect to PostgreSQL with retry logic"""
        max_retries = 30
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to PostgreSQL (attempt {attempt + 1}/{max_retries})...")
                self.postgres_conn = psycopg2.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    database=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD
                )
                self.postgres_conn.autocommit = False
                logger.info("✓ PostgreSQL connected")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"PostgreSQL connection failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to PostgreSQL after {max_retries} attempts")
                    return False

    def connect_rabbitmq(self):
        """Connect to RabbitMQ with retry logic"""
        max_retries = 30
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to RabbitMQ (attempt {attempt + 1}/{max_retries})...")

                credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
                parameters = pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )

                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # Ensure queue exists
                self.channel.queue_declare(queue='webapp_active_users', durable=True)

                logger.info("✓ RabbitMQ connected")
                return True

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"RabbitMQ connection failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to RabbitMQ after {max_retries} attempts")
                    return False

    def process_message(self, ch, method, properties, body):
        """Process a user activity message"""
        try:
            data = json.loads(body)

            # Extract user list
            active_users_list = data.get('active_users_list', [])

            if not active_users_list:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # Insert users into database
            cur = self.postgres_conn.cursor()

            insert_query = """
                INSERT INTO user_sessions
                (user_id, username, session_id, login_time, ip_address, region, connection_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    connection_status = EXCLUDED.connection_status,
                    updated_at = CURRENT_TIMESTAMP
            """

            for user in active_users_list:
                cur.execute(insert_query, (
                    user.get('user_id'),
                    user.get('username'),
                    user.get('session_id'),
                    user.get('login_time'),
                    user.get('ip_address'),
                    user.get('region'),
                    user.get('connection_status')
                ))

            self.postgres_conn.commit()
            cur.close()

            self.message_count += 1

            if self.message_count % 10 == 0:
                logger.info(f"✓ Processed {self.message_count} user activity messages ({len(active_users_list)} users in last batch)")

            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.postgres_conn.rollback()
            # Reject and requeue the message
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def run(self):
        """Main consumer loop"""
        logger.info("Starting RabbitMQ Consumer Service...")

        # Connect to PostgreSQL
        if not self.connect_postgres():
            logger.error("Failed to connect to PostgreSQL, exiting...")
            return

        # Connect to RabbitMQ
        if not self.connect_rabbitmq():
            logger.error("Failed to connect to RabbitMQ, exiting...")
            return

        logger.info("✓ RabbitMQ Consumer ready - listening for user activity...")

        # Set up consumer
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue='webapp_active_users',
            on_message_callback=self.process_message
        )

        # Start consuming
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping RabbitMQ consumer...")
            self.channel.stop_consuming()
            if self.connection:
                self.connection.close()
            if self.postgres_conn:
                self.postgres_conn.close()

if __name__ == "__main__":
    consumer = RabbitMQConsumer()
    consumer.run()
