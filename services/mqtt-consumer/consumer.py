import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import Json
import json
import time
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "tier0_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "tier0user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "tier0pass")

class MQTTConsumer:
    def __init__(self):
        self.mqtt_client = None
        self.postgres_conn = None
        self.message_count = 0
        self.batch = []
        self.batch_size = 100  # Insert in batches for performance

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

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info("✓ Connected to MQTT broker")
            # Subscribe to all device telemetry topics
            topic = "og/field/#"
            client.subscribe(topic)
            logger.info(f"✓ Subscribed to topic: {topic}")
        else:
            logger.error(f"✗ Failed to connect to MQTT broker (rc={rc})")

    def on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        try:
            # Parse the message
            payload = json.loads(msg.payload.decode())

            # Add to batch
            self.batch.append(payload)
            self.message_count += 1

            # Log progress every 100 messages
            if self.message_count % 100 == 0:
                logger.info(f"Received {self.message_count} messages")

            # Insert batch when it reaches batch_size
            if len(self.batch) >= self.batch_size:
                self.insert_batch()

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def insert_batch(self):
        """Insert a batch of telemetry records"""
        if not self.batch:
            return

        try:
            cur = self.postgres_conn.cursor()

            # Prepare batch insert
            insert_query = """
                INSERT INTO device_telemetry
                (device_id, device_type, site_id, timestamp_utc, firmware, metrics, status, location, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """

            batch_data = []
            for record in self.batch:
                batch_data.append((
                    record.get('device_id'),
                    record.get('device_type'),
                    record.get('site_id'),
                    record.get('timestamp_utc'),
                    record.get('firmware'),
                    Json(record.get('metrics', {})),
                    Json(record.get('status', {})),
                    Json(record.get('location', {})),
                    Json(record.get('tags', {}))
                ))

            # Execute batch insert
            cur.executemany(insert_query, batch_data)
            self.postgres_conn.commit()
            cur.close()

            logger.info(f"✓ Inserted batch of {len(self.batch)} telemetry records")
            self.batch = []

        except Exception as e:
            logger.error(f"Error inserting batch: {e}")
            self.postgres_conn.rollback()
            self.batch = []  # Clear batch to avoid reprocessing

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        max_retries = 30
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to MQTT broker (attempt {attempt + 1}/{max_retries})...")

                self.mqtt_client = mqtt.Client()
                self.mqtt_client.on_connect = self.on_connect
                self.mqtt_client.on_message = self.on_message

                self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
                logger.info("✓ MQTT connection initiated")
                return True

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"MQTT connection failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to MQTT after {max_retries} attempts")
                    return False

    def run(self):
        """Main consumer loop"""
        logger.info("Starting MQTT Consumer Service...")

        # Connect to PostgreSQL
        if not self.connect_postgres():
            logger.error("Failed to connect to PostgreSQL, exiting...")
            return

        # Connect to MQTT
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker, exiting...")
            return

        logger.info("✓ MQTT Consumer ready - listening for device telemetry...")

        # Start MQTT loop
        try:
            self.mqtt_client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Stopping MQTT consumer...")
            # Insert any remaining batch
            if self.batch:
                self.insert_batch()
            if self.postgres_conn:
                self.postgres_conn.close()
            if self.mqtt_client:
                self.mqtt_client.disconnect()

if __name__ == "__main__":
    consumer = MQTTConsumer()
    consumer.run()
