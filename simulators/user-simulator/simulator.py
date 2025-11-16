import pika
import json
import time
import random
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "tier0admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "tier0secure")
NUM_USERS = int(os.getenv("NUM_USERS", "1000"))
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "10"))

# Site configurations
SITES = [
    {"id": "SFO-WEB-01", "region": "US-WEST", "name": "San Francisco"},
    {"id": "NYC-WEB-01", "region": "US-EAST", "name": "New York"},
    {"id": "LON-WEB-01", "region": "EU-WEST", "name": "London"},
    {"id": "TOK-WEB-01", "region": "APAC", "name": "Tokyo"},
    {"id": "SYD-WEB-01", "region": "APAC", "name": "Sydney"},
    {"id": "FRA-WEB-01", "region": "EU-CENTRAL", "name": "Frankfurt"},
    {"id": "MUM-WEB-01", "region": "APAC", "name": "Mumbai"},
    {"id": "SAO-WEB-01", "region": "SA", "name": "Sao Paulo"},
    {"id": "DXB-WEB-01", "region": "ME", "name": "Dubai"},
    {"id": "TOR-WEB-01", "region": "US-NORTH", "name": "Toronto"}
]

# Common usernames
FIRST_NAMES = ["alex", "maria", "chen", "david", "sarah", "raj", "emily", "james",
               "ana", "michael", "lisa", "john", "emma", "william", "sophia"]
LAST_NAMES = ["j", "k", "li", "smith", "johnson", "patel", "garcia", "chen",
              "brown", "wilson", "lee", "rodriguez", "martinez"]

class UserSimulator:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.active_users = []

    def connect(self):
        """Connect to RabbitMQ"""
        try:
            logger.info(f"Connecting to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}...")

            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )

            # Retry connection
            max_retries = 30
            retry_count = 0

            while retry_count < max_retries:
                try:
                    self.connection = pika.BlockingConnection(parameters)
                    self.channel = self.connection.channel()

                    # Declare queue
                    self.channel.queue_declare(queue='webapp_active_users', durable=True)

                    logger.info("✓ Connected to RabbitMQ")
                    return True

                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Connection attempt {retry_count}/{max_retries} failed: {e}")
                    time.sleep(2)

            logger.error("Failed to connect to RabbitMQ after maximum retries")
            return False

        except Exception as e:
            logger.error(f"RabbitMQ connection error: {e}")
            return False

    def generate_users(self):
        """Generate initial user pool"""
        logger.info(f"Generating {NUM_USERS} user sessions...")

        for i in range(NUM_USERS):
            site = random.choice(SITES)

            # Generate realistic login times (within last 4 hours)
            login_offset = random.randint(0, 240)  # 0-240 minutes ago
            login_time = datetime.utcnow() - timedelta(minutes=login_offset)

            # IP address generation
            ip_ranges = {
                "US-WEST": "192.168",
                "US-EAST": "10.10",
                "EU-WEST": "172.16",
                "APAC": "172.20",
                "EU-CENTRAL": "172.18",
                "SA": "10.20",
                "ME": "172.24",
                "US-NORTH": "10.30"
            }

            ip_prefix = ip_ranges.get(site["region"], "192.168")
            ip_address = f"{ip_prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"

            # Connection status (90% active, 10% idle)
            connection_status = random.choices(
                ["active", "idle"],
                weights=[0.9, 0.1]
            )[0]

            user = {
                "user_id": f"USR-{i:05d}",
                "username": f"{random.choice(FIRST_NAMES)}_{random.choice(LAST_NAMES)}",
                "session_id": f"SESS-{random.randint(100000, 999999):06X}",
                "login_time": login_time.isoformat() + "Z",
                "ip_address": ip_address,
                "region": site["region"],
                "connection_status": connection_status,
                "site_id": site["id"]
            }

            self.active_users.append(user)

        logger.info(f"✓ Generated {len(self.active_users)} user sessions")

    def generate_user_activity_message(self):
        """Generate user activity metrics message"""
        # Randomly update some users' status
        for user in random.sample(self.active_users, min(50, len(self.active_users))):
            user["connection_status"] = random.choice(["active", "active", "active", "idle"])

        # Group users by site
        site_metrics = {}
        for site in SITES:
            site_users = [u for u in self.active_users if u["site_id"] == site["id"]]
            active_count = sum(1 for u in site_users if u["connection_status"] == "active")

            site_metrics[site["id"]] = {
                "message_id": f"MSG-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(10000, 99999)}",
                "timestamp_utc": datetime.utcnow().isoformat() + "Z",
                "site_id": site["id"],
                "metrics": {
                    "active_users": active_count,
                    "active_connections": active_count + random.randint(-10, 10),
                    "server_cpu_pct": round(random.uniform(45, 85), 1),
                    "server_memory_gb": round(random.uniform(12, 24), 1),
                    "average_latency_ms": round(random.uniform(50, 150), 1)
                },
                "active_users_list": site_users[:20],  # Send first 20 users
                "queue_metadata": {
                    "topic": "webapp/active_users",
                    "producer": "SiteSimEngine",
                    "priority": "normal",
                    "retries": 0
                }
            }

        return site_metrics

    def publish_activity(self):
        """Publish user activity to RabbitMQ"""
        try:
            site_metrics = self.generate_user_activity_message()

            for site_id, metrics in site_metrics.items():
                message = json.dumps(metrics, indent=2)

                self.channel.basic_publish(
                    exchange='',
                    routing_key='webapp_active_users',
                    body=message,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                        content_type='application/json'
                    )
                )

            return len(site_metrics)

        except Exception as e:
            logger.error(f"Error publishing activity: {e}")
            # Try to reconnect
            self.connect()
            return 0

    def simulate_user_churn(self):
        """Simulate users logging in and out"""
        # 5% chance to logout random users
        if random.random() < 0.05:
            logout_count = random.randint(1, 5)
            for _ in range(logout_count):
                if self.active_users:
                    user = random.choice(self.active_users)
                    self.active_users.remove(user)

        # 5% chance to add new users
        if random.random() < 0.05:
            new_count = random.randint(1, 5)
            for _ in range(new_count):
                site = random.choice(SITES)

                ip_ranges = {
                    "US-WEST": "192.168",
                    "US-EAST": "10.10",
                    "EU-WEST": "172.16",
                    "APAC": "172.20"
                }

                ip_prefix = ip_ranges.get(site["region"], "192.168")
                ip_address = f"{ip_prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"

                new_user = {
                    "user_id": f"USR-{random.randint(10000, 99999)}",
                    "username": f"{random.choice(FIRST_NAMES)}_{random.choice(LAST_NAMES)}",
                    "session_id": f"SESS-{random.randint(100000, 999999):06X}",
                    "login_time": datetime.utcnow().isoformat() + "Z",
                    "ip_address": ip_address,
                    "region": site["region"],
                    "connection_status": "active",
                    "site_id": site["id"]
                }

                self.active_users.append(new_user)

    def run(self):
        """Main simulation loop"""
        if not self.connect():
            logger.error("Failed to connect to RabbitMQ, exiting...")
            return

        self.generate_users()

        logger.info(f"Starting user activity simulation (publishing every {PUBLISH_INTERVAL}s)...")

        cycle = 0
        while True:
            try:
                # Simulate user churn
                self.simulate_user_churn()

                # Publish activity
                published_count = self.publish_activity()

                cycle += 1
                if cycle % 5 == 0:
                    logger.info(f"Published user activity for {published_count} sites "
                              f"({len(self.active_users)} active users)")

                time.sleep(PUBLISH_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Stopping user simulator...")
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                time.sleep(5)

        if self.connection:
            self.connection.close()

if __name__ == "__main__":
    simulator = UserSimulator()
    simulator.run()
