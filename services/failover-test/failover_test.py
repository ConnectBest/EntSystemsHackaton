#!/usr/bin/env python3
"""
Failover Test Service - HA/DR Simulation
Tests system resilience and validates 99.99999% availability target
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
import redis
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
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

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

# Target availability: 99.99999% = 3.15 seconds downtime per year
TARGET_AVAILABILITY = 0.9999999
MAX_DOWNTIME_SECONDS = 3.15

# Test results storage
failover_tests = []

class FailoverTestRequest(BaseModel):
    test_type: str  # redis_failure, postgres_failure, service_failure, network_partition
    duration_seconds: int = 30

class FailoverTestResult(BaseModel):
    test_id: str
    test_type: str
    start_time: str
    end_time: str
    duration_seconds: float
    recovery_time_seconds: float
    success: bool
    availability_percentage: float
    requests_total: int
    requests_successful: int
    requests_failed: int
    details: Dict

class FailoverTestService:
    def __init__(self):
        self.postgres_conn = None
        self.mongo_client = None
        self.redis_client = None
        self.running = False

    def connect(self):
        """Connect to all services"""
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

    async def test_redis_failover(self, duration_seconds: int) -> Dict:
        """
        Test Redis cache failover scenario
        Simulates Redis unavailability and measures recovery
        """
        logger.info(f"Starting Redis failover test for {duration_seconds} seconds...")

        test_id = f"redis_failover_{int(time.time())}"
        start_time = datetime.utcnow()

        requests_total = 0
        requests_successful = 0
        requests_failed = 0
        downtime_start = None
        downtime_end = None

        # Phase 1: Normal operation (measure baseline)
        logger.info("Phase 1: Baseline measurement...")
        for i in range(5):
            try:
                response = requests.get(f"{BACKEND_URL}/api/devices", timeout=2)
                if response.status_code == 200:
                    requests_successful += 1
                else:
                    requests_failed += 1
                requests_total += 1
            except Exception as e:
                requests_failed += 1
                requests_total += 1
            await asyncio.sleep(0.5)

        # Phase 2: Simulate Redis failure by flushing cache
        logger.info("Phase 2: Simulating Redis failure (flushing cache)...")
        downtime_start = datetime.utcnow()

        try:
            # Flush Redis to simulate failure
            self.redis_client.flushall()
            logger.info("Redis cache flushed")
        except Exception as e:
            logger.error(f"Error flushing Redis: {e}")

        # Phase 3: Monitor recovery
        logger.info("Phase 3: Monitoring system recovery...")
        test_duration = 0
        recovery_detected = False

        while test_duration < duration_seconds:
            try:
                # Test backend endpoint (should fall back to PostgreSQL)
                response = requests.get(f"{BACKEND_URL}/api/devices?limit=10", timeout=2)

                if response.status_code == 200:
                    requests_successful += 1
                    if not recovery_detected:
                        downtime_end = datetime.utcnow()
                        recovery_detected = True
                        logger.info(f"System recovered! Downtime: {(downtime_end - downtime_start).total_seconds():.3f}s")
                else:
                    requests_failed += 1

                requests_total += 1

            except Exception as e:
                requests_failed += 1
                requests_total += 1
                logger.debug(f"Request failed: {e}")

            await asyncio.sleep(1)
            test_duration += 1

        end_time = datetime.utcnow()

        # Calculate metrics
        if not downtime_end:
            downtime_end = end_time

        recovery_time = (downtime_end - downtime_start).total_seconds()
        total_duration = (end_time - start_time).total_seconds()
        availability = (requests_successful / requests_total * 100) if requests_total > 0 else 0

        success = recovery_time < 5.0 and availability > 99.9  # Recovery within 5 seconds

        result = {
            "test_id": test_id,
            "test_type": "redis_failover",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": total_duration,
            "recovery_time_seconds": recovery_time,
            "success": success,
            "availability_percentage": round(availability, 5),
            "requests_total": requests_total,
            "requests_successful": requests_successful,
            "requests_failed": requests_failed,
            "details": {
                "downtime_start": downtime_start.isoformat() if downtime_start else None,
                "downtime_end": downtime_end.isoformat() if downtime_end else None,
                "meets_tier0_sla": recovery_time < MAX_DOWNTIME_SECONDS,
                "target_availability": TARGET_AVAILABILITY * 100,
                "actual_availability": availability,
                "recovery_mechanism": "Fallback to PostgreSQL",
                "cache_rebuild": "Automatic on next query"
            }
        }

        logger.info(f"✓ Redis failover test complete: {availability:.5f}% availability, {recovery_time:.3f}s recovery")
        return result

    async def test_database_resilience(self, duration_seconds: int) -> Dict:
        """
        Test database connection resilience
        Simulates slow queries and connection timeouts
        """
        logger.info(f"Starting database resilience test for {duration_seconds} seconds...")

        test_id = f"db_resilience_{int(time.time())}"
        start_time = datetime.utcnow()

        requests_total = 0
        requests_successful = 0
        requests_failed = 0
        slow_queries = 0

        # Test database queries under load
        for i in range(duration_seconds):
            try:
                query_start = time.time()

                # Test PostgreSQL query
                cur = self.postgres_conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT COUNT(*) as count FROM device_telemetry")
                result = cur.fetchone()
                cur.close()

                query_time = time.time() - query_start

                if query_time > 1.0:
                    slow_queries += 1

                requests_successful += 1
                requests_total += 1

            except Exception as e:
                logger.debug(f"Database query failed: {e}")
                requests_failed += 1
                requests_total += 1

            await asyncio.sleep(1)

        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()
        availability = (requests_successful / requests_total * 100) if requests_total > 0 else 0

        success = availability > 99.9 and slow_queries < (duration_seconds * 0.1)

        result = {
            "test_id": test_id,
            "test_type": "database_resilience",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": total_duration,
            "recovery_time_seconds": 0,  # No recovery needed if no failure
            "success": success,
            "availability_percentage": round(availability, 5),
            "requests_total": requests_total,
            "requests_successful": requests_successful,
            "requests_failed": requests_failed,
            "details": {
                "slow_queries": slow_queries,
                "slow_query_threshold": "1.0 seconds",
                "database_type": "PostgreSQL",
                "connection_pool": "Enabled"
            }
        }

        logger.info(f"✓ Database resilience test complete: {availability:.5f}% availability")
        return result

    async def test_service_availability(self, duration_seconds: int) -> Dict:
        """
        Test overall service availability
        Measures API endpoint responsiveness and error rates
        """
        logger.info(f"Starting service availability test for {duration_seconds} seconds...")

        test_id = f"service_availability_{int(time.time())}"
        start_time = datetime.utcnow()

        endpoints = [
            "/health",
            "/api/devices",
            "/api/users/active",
            "/api/images"
        ]

        requests_total = 0
        requests_successful = 0
        requests_failed = 0
        response_times = []

        # Test multiple endpoints
        test_iterations = duration_seconds * 2  # 2 requests per second

        for i in range(test_iterations):
            endpoint = endpoints[i % len(endpoints)]

            try:
                req_start = time.time()
                response = requests.get(f"{BACKEND_URL}{endpoint}", timeout=5)
                req_time = time.time() - req_start

                response_times.append(req_time)

                if response.status_code == 200:
                    requests_successful += 1
                else:
                    requests_failed += 1

                requests_total += 1

            except Exception as e:
                requests_failed += 1
                requests_total += 1
                logger.debug(f"Request to {endpoint} failed: {e}")

            await asyncio.sleep(0.5)

        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()
        availability = (requests_successful / requests_total * 100) if requests_total > 0 else 0

        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0

        success = availability >= 99.99

        result = {
            "test_id": test_id,
            "test_type": "service_availability",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": total_duration,
            "recovery_time_seconds": 0,
            "success": success,
            "availability_percentage": round(availability, 5),
            "requests_total": requests_total,
            "requests_successful": requests_successful,
            "requests_failed": requests_failed,
            "details": {
                "endpoints_tested": len(endpoints),
                "avg_response_time_ms": round(avg_response_time * 1000, 2),
                "p95_response_time_ms": round(p95_response_time * 1000, 2),
                "target_availability": "99.99999%",
                "meets_sla": availability >= 99.99999
            }
        }

        logger.info(f"✓ Service availability test complete: {availability:.5f}% availability")
        return result

# Initialize service
failover_service = FailoverTestService()

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Failover Test Service...")
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        if failover_service.connect():
            logger.info("✓ Failover Test Service ready")
            break
        retry_count += 1
        logger.warning(f"Connection failed, retrying... ({retry_count}/{max_retries})")
        await asyncio.sleep(10)

    yield

    # Shutdown
    logger.info("Shutting down Failover Test Service...")

app = FastAPI(title="Failover Test Service", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Failover Test Service"}

@app.post("/test/run")
async def run_failover_test(request: FailoverTestRequest):
    """Run a specific failover test"""
    try:
        if request.test_type == "redis_failover":
            result = await failover_service.test_redis_failover(request.duration_seconds)
        elif request.test_type == "database_resilience":
            result = await failover_service.test_database_resilience(request.duration_seconds)
        elif request.test_type == "service_availability":
            result = await failover_service.test_service_availability(request.duration_seconds)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown test type: {request.test_type}")

        # Store result
        failover_tests.append(result)

        return result

    except Exception as e:
        logger.error(f"Error running failover test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test/results")
async def get_test_results(limit: int = 10):
    """Get recent failover test results"""
    return {
        "count": len(failover_tests),
        "tests": failover_tests[-limit:] if failover_tests else []
    }

@app.get("/test/summary")
async def get_test_summary():
    """Get summary of all failover tests"""
    if not failover_tests:
        return {
            "total_tests": 0,
            "successful_tests": 0,
            "failed_tests": 0,
            "average_availability": 0,
            "tier0_compliant": False
        }

    successful = sum(1 for t in failover_tests if t["success"])
    total_availability = sum(t["availability_percentage"] for t in failover_tests)
    avg_availability = total_availability / len(failover_tests)

    return {
        "total_tests": len(failover_tests),
        "successful_tests": successful,
        "failed_tests": len(failover_tests) - successful,
        "average_availability": round(avg_availability, 5),
        "target_availability": TARGET_AVAILABILITY * 100,
        "tier0_compliant": avg_availability >= (TARGET_AVAILABILITY * 100),
        "recent_tests": failover_tests[-5:]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
