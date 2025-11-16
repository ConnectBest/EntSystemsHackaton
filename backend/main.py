from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
import pika
import paho.mqtt.client as mqtt
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.responses import Response
import json
import os
from typing import List, Dict, Any, Optional
from config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
http_requests_total = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
http_request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
active_users_gauge = Gauge('active_users', 'Number of active users')
active_devices_gauge = Gauge('active_devices', 'Number of active devices')
system_uptime_gauge = Gauge('system_uptime_seconds', 'System uptime')

# Pydantic models for request/response
class ImageDescribeRequest(BaseModel):
    device_type: str

class QueryRequest(BaseModel):
    question: str

# Global connections
redis_client = None
postgres_conn = None
mongo_client = None
mqtt_client = None
rabbitmq_connection = None
start_time = datetime.utcnow()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global redis_client, postgres_conn, mongo_client, mqtt_client, rabbitmq_connection

    logger.info("Starting Tier-0 Enterprise SRE System...")

    # Initialize Redis
    try:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5
        )
        redis_client.ping()
        logger.info("✓ Redis connected")
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")

    # Initialize PostgreSQL
    try:
        postgres_conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD
        )
        logger.info("✓ PostgreSQL connected")
    except Exception as e:
        logger.error(f"✗ PostgreSQL connection failed: {e}")

    # Initialize MongoDB
    try:
        mongo_client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command('ping')
        logger.info("✓ MongoDB connected")
    except Exception as e:
        logger.error(f"✗ MongoDB connection failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Tier-0 Enterprise SRE System...")
    if redis_client:
        redis_client.close()
    if postgres_conn:
        postgres_conn.close()
    if mongo_client:
        mongo_client.close()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Tier-0 Enterprise Reliability Engineering System - 99.99999% SLA Target",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= HEALTH & MONITORING ENDPOINTS =============

@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "uptime_seconds": (datetime.utcnow() - start_time).total_seconds(),
        "services": {}
    }

    # Check Redis
    try:
        redis_client.ping()
        health_status["services"]["redis"] = "healthy"
    except:
        health_status["services"]["redis"] = "unhealthy"
        health_status["status"] = "degraded"

    # Check PostgreSQL
    try:
        cur = postgres_conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        health_status["services"]["postgres"] = "healthy"
    except:
        health_status["services"]["postgres"] = "unhealthy"
        health_status["status"] = "degraded"

    # Check MongoDB
    try:
        mongo_client.admin.command('ping')
        health_status["services"]["mongodb"] = "healthy"
    except:
        health_status["services"]["mongodb"] = "unhealthy"
        health_status["status"] = "degraded"

    # Update uptime metric
    system_uptime_gauge.set((datetime.utcnow() - start_time).total_seconds())

    return health_status

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "sla_target": f"{settings.SLA_TARGET}%",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "devices": "/api/devices",
            "users": "/api/users",
            "sites": "/api/sites",
            "images": "/api/images",
            "logs": "/api/logs",
            "query": "/api/query",
            "failover": "/api/failover/summary"
        }
    }

# ============= DEVICE TELEMETRY ENDPOINTS =============

@app.get("/api/devices")
async def get_devices(
    site_id: Optional[str] = None,
    device_type: Optional[str] = None,
    limit: int = 100
):
    """Get device telemetry data from Redis cache"""
    try:
        # First try Redis cache
        cache_key = f"devices:{site_id}:{device_type}" if site_id and device_type else "devices:all"
        cached = redis_client.get(cache_key)

        if cached:
            http_requests_total.labels(method='GET', endpoint='/api/devices', status='200').inc()
            return JSONResponse(content=json.loads(cached))

        # Fall back to PostgreSQL
        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM device_telemetry WHERE 1=1"
        params = []

        if site_id:
            query += " AND site_id = %s"
            params.append(site_id)
        if device_type:
            query += " AND device_type = %s"
            params.append(device_type)

        query += f" ORDER BY timestamp_utc DESC LIMIT {limit}"
        cur.execute(query, params)
        devices = cur.fetchall()
        cur.close()

        # Cache result
        redis_client.setex(cache_key, 60, json.dumps(devices, default=str))

        active_devices_gauge.set(len(devices))
        http_requests_total.labels(method='GET', endpoint='/api/devices', status='200').inc()

        return devices
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        http_requests_total.labels(method='GET', endpoint='/api/devices', status='500').inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices/count")
async def get_device_count():
    """Get total device count per site and type"""
    try:
        # Try Redis cache first
        cached = redis_client.get("device:count")
        if cached:
            return JSONResponse(content=json.loads(cached))

        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                site_id,
                device_type,
                COUNT(*) as count,
                MAX(timestamp_utc) as last_seen
            FROM device_telemetry
            GROUP BY site_id, device_type
            ORDER BY site_id, device_type
        """)
        counts = cur.fetchall()
        cur.close()

        # Cache for 30 seconds
        redis_client.setex("device:count", 30, json.dumps(counts, default=str))

        return counts
    except Exception as e:
        logger.error(f"Error fetching device count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= USER SESSION ENDPOINTS =============

@app.get("/api/users")
async def get_active_users(site_id: Optional[str] = None):
    """Get active user sessions"""
    try:
        # Try Redis cache
        cache_key = f"users:{site_id}" if site_id else "users:all"
        cached = redis_client.get(cache_key)

        if cached:
            return JSONResponse(content=json.loads(cached))

        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT * FROM user_sessions
            WHERE connection_status = 'active'
            AND logout_time IS NULL
        """
        params = []

        if site_id:
            query += " AND region LIKE %s"
            params.append(f"%{site_id}%")

        query += " ORDER BY login_time DESC LIMIT 1000"
        cur.execute(query, params)
        users = cur.fetchall()
        cur.close()

        # Cache for 10 seconds
        redis_client.setex(cache_key, 10, json.dumps(users, default=str))

        active_users_gauge.set(len(users))

        return {
            "active_users": len(users),
            "users": users,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/stats")
async def get_user_stats():
    """Get user statistics"""
    try:
        cached = redis_client.get("users:stats")
        if cached:
            return JSONResponse(content=json.loads(cached))

        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE connection_status = 'active') as active_users,
                COUNT(*) FILTER (WHERE connection_status = 'idle') as idle_users,
                COUNT(DISTINCT region) as regions,
                COUNT(DISTINCT DATE(login_time)) as active_days
            FROM user_sessions
            WHERE logout_time IS NULL
        """)
        stats = cur.fetchone()
        cur.close()

        redis_client.setex("users:stats", 30, json.dumps(stats, default=str))

        return stats
    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= SITE ENDPOINTS =============

@app.get("/api/sites")
async def get_sites():
    """Get all site information"""
    try:
        cached = redis_client.get("sites:all")
        if cached:
            return JSONResponse(content=json.loads(cached))

        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM sites WHERE active = true ORDER BY site_id")
        sites = cur.fetchall()
        cur.close()

        # Cache for 5 minutes
        redis_client.setex("sites:all", 300, json.dumps(sites, default=str))

        return sites
    except Exception as e:
        logger.error(f"Error fetching sites: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= IMAGE & EMBEDDING ENDPOINTS =============

@app.get("/api/images")
async def get_images(site_id: Optional[str] = None, device_type: Optional[str] = None):
    """Get image metadata from MongoDB"""
    try:
        db = mongo_client['tier0_images']
        collection = db['images']

        query = {}
        if site_id:
            query['site_id'] = site_id
        if device_type:
            query['device_type'] = device_type

        images = list(collection.find(query, {'_id': 0}).limit(100))

        return {
            "count": len(images),
            "images": images
        }
    except Exception as e:
        logger.error(f"Error fetching images: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/images/describe")
async def describe_image_context(request: ImageDescribeRequest):
    """Generate word cloud description for site images"""
    try:
        db = mongo_client['tier0_images']
        collection = db['images']

        # Query images by device type
        query = {"device_type": request.device_type, "processed": True}
        images = list(collection.find(query, {
            "_id": 0,
            "keywords": 1,
            "description": 1,
            "safety_compliance": 1
        }).limit(100))

        if not images:
            return {
                "device_type": request.device_type,
                "description": f"No processed images found for {request.device_type}. The image processor may still be analyzing site camera feeds.",
                "keywords": [],
                "image_count": 0,
                "timestamp": datetime.utcnow().isoformat()
            }

        # Aggregate keywords from all images
        all_keywords = []
        for img in images:
            if "keywords" in img:
                all_keywords.extend(img["keywords"])

        # Get most common keywords
        from collections import Counter
        keyword_counts = Counter(all_keywords)
        top_keywords = [kw for kw, count in keyword_counts.most_common(10)]

        # Calculate average safety compliance
        compliance_scores = [
            img.get("safety_compliance", {}).get("compliance_score", 0)
            for img in images if "safety_compliance" in img
        ]
        avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0

        # Generate description
        description = f"Analyzed {len(images)} {request.device_type} images. "
        description += f"Average safety compliance: {avg_compliance:.1f}%. "
        description += f"Common themes: {', '.join(top_keywords[:5])}."

        return {
            "device_type": request.device_type,
            "description": description,
            "keywords": top_keywords,
            "image_count": len(images),
            "avg_compliance": round(avg_compliance, 1),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error describing images: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============= LOG ANALYSIS ENDPOINTS =============

@app.get("/api/logs/errors")
async def get_error_logs(limit: int = 100):
    """Get error logs (4xx and 5xx status codes)"""
    try:
        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT ip_address, method, endpoint, status_code, COUNT(*) as error_count
            FROM system_logs
            WHERE status_code >= 400
            GROUP BY ip_address, method, endpoint, status_code
            ORDER BY error_count DESC
            LIMIT %s
        """, (limit,))
        errors = cur.fetchall()
        cur.close()

        return {
            "total_errors": len(errors),
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Error fetching error logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs/top-ips")
async def get_top_ips(limit: int = 20):
    """Get IP addresses generating the most requests"""
    try:
        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                ip_address,
                COUNT(*) as request_count,
                COUNT(*) FILTER (WHERE status_code >= 400) as error_count,
                AVG(response_time) as avg_response_time
            FROM system_logs
            GROUP BY ip_address
            ORDER BY request_count DESC
            LIMIT %s
        """, (limit,))
        ips = cur.fetchall()
        cur.close()

        return {
            "top_ips": ips
        }
    except Exception as e:
        logger.error(f"Error fetching top IPs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= RAG QUERY ENDPOINT =============

@app.post("/api/query")
async def natural_language_query(request: QueryRequest):
    """Process natural language queries using RAG"""
    try:
        import httpx

        question = request.question

        # Call the RAG service
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://rag-service:8001/query",
                    json={"question": question}
                )

                if response.status_code == 200:
                    rag_response = response.json()
                    result = rag_response.get("result", {})

                    return {
                        "question": question,
                        "answer": result.get("answer", "No answer available"),
                        "sources": result.get("sources", []),
                        "bp_sources": result.get("bp_sources", []),
                        "image_data": result.get("image_data", []),
                        "sites": result.get("sites", []),
                        "avg_compliance": result.get("avg_compliance"),
                        "count": result.get("count"),
                        "type": result.get("type", "unknown"),
                        "data": result.get("data"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    logger.error(f"RAG service returned status {response.status_code}")
                    return {
                        "question": question,
                        "answer": "Error contacting RAG service. Please try again.",
                        "sources": [],
                        "timestamp": datetime.utcnow().isoformat()
                    }

        except httpx.ConnectError:
            logger.error("Cannot connect to RAG service")
            return {
                "question": question,
                "answer": "RAG service is not available. Please check if all services are running.",
                "sources": [],
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============= FAILOVER TEST ENDPOINTS =============

@app.post("/api/failover/test")
async def run_failover_test(test_type: str, duration_seconds: int = 30):
    """Run a failover test"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://failover-test:8002/test/run",
                json={
                    "test_type": test_type,
                    "duration_seconds": duration_seconds
                }
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failover test service returned status {response.status_code}")
                raise HTTPException(status_code=500, detail="Failover test failed")

    except Exception as e:
        logger.error(f"Error running failover test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/failover/results")
async def get_failover_results(limit: int = 10):
    """Get failover test results"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://failover-test:8002/test/results?limit={limit}"
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"count": 0, "tests": []}

    except Exception as e:
        logger.error(f"Error getting failover results: {e}")
        return {"count": 0, "tests": []}

@app.get("/api/failover/summary")
async def get_failover_summary():
    """Get failover test summary"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://failover-test:8002/test/summary")

            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "total_tests": 0,
                    "successful_tests": 0,
                    "failed_tests": 0,
                    "average_availability": 0,
                    "tier0_compliant": False
                }

    except Exception as e:
        logger.error(f"Error getting failover summary: {e}")
        return {
            "total_tests": 0,
            "successful_tests": 0,
            "failed_tests": 0,
            "average_availability": 0,
            "tier0_compliant": False
        }

# ============= SYSTEM STATS ENDPOINT =============

@app.get("/api/stats")
async def get_system_stats():
    """Get overall system statistics"""
    try:
        cur = postgres_conn.cursor(cursor_factory=RealDictCursor)

        # Get device count
        cur.execute("SELECT COUNT(DISTINCT device_id) as device_count FROM device_telemetry")
        device_stats = cur.fetchone()

        # Get user count
        cur.execute("""
            SELECT COUNT(*) as active_users
            FROM user_sessions
            WHERE connection_status = 'active' AND logout_time IS NULL
        """)
        user_stats = cur.fetchone()

        # Get site count
        cur.execute("SELECT COUNT(*) as site_count FROM sites WHERE active = true")
        site_stats = cur.fetchone()

        cur.close()

        uptime = (datetime.utcnow() - start_time).total_seconds()
        availability = 100.0 - ((uptime - uptime * 0.9999999) / uptime * 100)

        return {
            "system_name": settings.APP_NAME,
            "version": settings.VERSION,
            "sla_target": settings.SLA_TARGET,
            "current_availability": round(availability, 7),
            "uptime_seconds": round(uptime, 2),
            "total_devices": device_stats.get('device_count', 0),
            "active_users": user_stats.get('active_users', 0),
            "total_sites": site_stats.get('site_count', 0),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching system stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
