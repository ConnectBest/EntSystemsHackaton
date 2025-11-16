#!/usr/bin/env python3
"""
Data Cleanup Service - Periodic cleanup to prevent unbounded growth
Implements time-based and count-based retention policies
"""
import os
import time
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
import redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "300"))  # Default: 5 minutes
RETENTION_HOURS = int(os.getenv("RETENTION_HOURS", "24"))  # Keep last 24 hours
MAX_RECORDS_PER_TABLE = int(os.getenv("MAX_RECORDS_PER_TABLE", "100000"))  # Max 100K records per table

# Database connections
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "tier0_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "tier0user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "tier0pass")

MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_USER = os.getenv("MONGODB_USER", "tier0admin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "tier0mongo")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

class DataCleanupService:
    def __init__(self):
        self.postgres_conn = None
        self.mongo_client = None
        self.redis_client = None

    def connect(self):
        """Connect to all data stores"""
        try:
            # PostgreSQL
            logger.info("Connecting to PostgreSQL...")
            self.postgres_conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            self.postgres_conn.autocommit = False
            logger.info("✓ PostgreSQL connected")

            # MongoDB
            logger.info("Connecting to MongoDB...")
            mongo_url = f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/"
            self.mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
            self.mongo_client.admin.command('ping')
            logger.info("✓ MongoDB connected")

            # Redis
            logger.info("Connecting to Redis...")
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("✓ Redis connected")

            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def cleanup_postgres(self):
        """Clean up old PostgreSQL data"""
        logger.info("Starting PostgreSQL cleanup...")

        try:
            cur = self.postgres_conn.cursor(cursor_factory=RealDictCursor)
            cutoff_time = datetime.utcnow() - timedelta(hours=RETENTION_HOURS)

            # Cleanup tables with timestamps
            tables_with_timestamps = [
                ('device_telemetry', 'timestamp'),
                ('user_sessions', 'login_time'),
                ('system_logs', 'timestamp')
            ]

            total_deleted = 0

            for table_name, timestamp_col in tables_with_timestamps:
                # Count before deletion
                cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                before_count = cur.fetchone()['count']

                # Delete old records
                cur.execute(f"""
                    DELETE FROM {table_name}
                    WHERE {timestamp_col} < %s
                """, (cutoff_time,))

                deleted = cur.rowcount
                total_deleted += deleted

                # If still too many records, keep only the most recent MAX_RECORDS_PER_TABLE
                cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                current_count = cur.fetchone()['count']

                if current_count > MAX_RECORDS_PER_TABLE:
                    excess = current_count - MAX_RECORDS_PER_TABLE
                    cur.execute(f"""
                        DELETE FROM {table_name}
                        WHERE id IN (
                            SELECT id FROM {table_name}
                            ORDER BY {timestamp_col} ASC
                            LIMIT %s
                        )
                    """, (excess,))
                    deleted += cur.rowcount
                    total_deleted += cur.rowcount

                logger.info(f"  {table_name}: deleted {deleted} records (was {before_count}, now {before_count - deleted})")

            # Commit all changes
            self.postgres_conn.commit()
            cur.close()

            # Run VACUUM to reclaim space
            old_isolation_level = self.postgres_conn.isolation_level
            self.postgres_conn.set_isolation_level(0)
            auto_cur = self.postgres_conn.cursor()
            auto_cur.execute("VACUUM ANALYZE")
            auto_cur.close()
            self.postgres_conn.set_isolation_level(old_isolation_level)

            logger.info(f"✓ PostgreSQL cleanup complete: {total_deleted} total records deleted")

        except Exception as e:
            logger.error(f"Error cleaning PostgreSQL: {e}")
            self.postgres_conn.rollback()

    def cleanup_mongodb(self):
        """Clean up old MongoDB data"""
        logger.info("Starting MongoDB cleanup...")

        try:
            db = self.mongo_client['tier0_images']

            # Clean up processed images older than retention period
            cutoff_time = datetime.utcnow() - timedelta(hours=RETENTION_HOURS)

            # Delete old processed images
            result = db.images.delete_many({
                'processed': True,
                'processed_at': {'$lt': cutoff_time}
            })
            deleted_images = result.deleted_count

            # If still too many images, keep only most recent
            image_count = db.images.count_documents({})
            if image_count > MAX_RECORDS_PER_TABLE:
                # Find oldest images to delete
                excess = image_count - MAX_RECORDS_PER_TABLE
                oldest_images = list(db.images.find({}, {'_id': 1}).sort('processed_at', 1).limit(excess))
                if oldest_images:
                    image_ids = [img['_id'] for img in oldest_images]
                    result = db.images.delete_many({'_id': {'$in': image_ids}})
                    deleted_images += result.deleted_count

            logger.info(f"✓ MongoDB cleanup complete: {deleted_images} images deleted")

        except Exception as e:
            logger.error(f"Error cleaning MongoDB: {e}")

    def cleanup_redis(self):
        """Clean up Redis cache"""
        logger.info("Starting Redis cleanup...")

        try:
            # Get memory info
            info = self.redis_client.info('memory')
            used_memory_mb = info['used_memory'] / (1024 * 1024)

            logger.info(f"  Redis memory usage: {used_memory_mb:.2f} MB")

            # Redis is configured with LRU eviction, so we just need to monitor
            # Optional: Can clear specific key patterns if needed

            # Count keys
            key_count = self.redis_client.dbsize()
            logger.info(f"  Redis key count: {key_count}")

            # If memory is high, we could selectively delete old keys
            if used_memory_mb > 1500:  # 1.5GB threshold (max is 2GB)
                logger.warning(f"Redis memory high ({used_memory_mb:.2f} MB), clearing old cache keys...")

                # Clear device telemetry cache (these can be reloaded from PostgreSQL)
                deleted = 0
                for key in self.redis_client.scan_iter("device:*", count=100):
                    self.redis_client.delete(key)
                    deleted += 1
                    if deleted >= 1000:  # Limit deletions per cycle
                        break

                logger.info(f"  Cleared {deleted} cache keys")

            logger.info("✓ Redis cleanup complete")

        except Exception as e:
            logger.error(f"Error cleaning Redis: {e}")

    def get_stats(self):
        """Get current data statistics"""
        stats = {}

        try:
            # PostgreSQL stats
            cur = self.postgres_conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("SELECT COUNT(*) as count FROM device_telemetry")
            stats['device_telemetry_count'] = cur.fetchone()['count']

            cur.execute("SELECT COUNT(*) as count FROM user_sessions")
            stats['user_sessions_count'] = cur.fetchone()['count']

            cur.execute("SELECT COUNT(*) as count FROM system_logs")
            stats['system_logs_count'] = cur.fetchone()['count']

            cur.close()

            # MongoDB stats
            db = self.mongo_client['tier0_images']
            stats['images_count'] = db.images.count_documents({})

            # Redis stats
            stats['redis_keys'] = self.redis_client.dbsize()
            info = self.redis_client.info('memory')
            stats['redis_memory_mb'] = round(info['used_memory'] / (1024 * 1024), 2)

        except Exception as e:
            logger.error(f"Error getting stats: {e}")

        return stats

    def run_cleanup_cycle(self):
        """Run a complete cleanup cycle"""
        logger.info("=" * 60)
        logger.info("Starting cleanup cycle...")
        logger.info(f"Retention policy: {RETENTION_HOURS} hours, max {MAX_RECORDS_PER_TABLE} records per table")

        # Get stats before cleanup
        stats_before = self.get_stats()
        logger.info(f"Before cleanup: {stats_before}")

        # Run cleanups
        self.cleanup_postgres()
        self.cleanup_mongodb()
        self.cleanup_redis()

        # Get stats after cleanup
        stats_after = self.get_stats()
        logger.info(f"After cleanup: {stats_after}")

        logger.info("✓ Cleanup cycle complete")
        logger.info("=" * 60)

def main():
    logger.info("Data Cleanup Service starting...")
    logger.info(f"Cleanup interval: {CLEANUP_INTERVAL_SECONDS} seconds")
    logger.info(f"Retention period: {RETENTION_HOURS} hours")
    logger.info(f"Max records per table: {MAX_RECORDS_PER_TABLE}")

    service = DataCleanupService()

    # Wait for services to be ready
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        if service.connect():
            break
        retry_count += 1
        logger.warning(f"Connection failed, retrying in 10 seconds... ({retry_count}/{max_retries})")
        time.sleep(10)

    if retry_count >= max_retries:
        logger.error("Failed to connect after max retries, exiting")
        return

    logger.info("✓ Data Cleanup Service ready")

    # Run cleanup loop
    while True:
        try:
            service.run_cleanup_cycle()
            logger.info(f"Next cleanup in {CLEANUP_INTERVAL_SECONDS} seconds...")
            time.sleep(CLEANUP_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
            break
        except Exception as e:
            logger.error(f"Error in cleanup cycle: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

    logger.info("Data Cleanup Service stopped")

if __name__ == "__main__":
    main()
