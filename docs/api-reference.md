# API Reference

Complete API documentation for the Tier-0 Enterprise SRE System.

---

## 📡 Backend API (Port 8000)

Base URL: `http://localhost:8000`

### Health & Status

#### GET `/health`

Check backend service health.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-16T12:30:45.123456",
  "services": {
    "postgres": "connected",
    "mongodb": "connected",
    "redis": "connected",
    "rabbitmq": "connected",
    "mqtt": "connected"
  }
}
```

**Status Codes**:
- `200 OK`: Service healthy
- `503 Service Unavailable`: Service unhealthy

---

### Device Telemetry

#### GET `/api/devices`

Retrieve device telemetry data.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_id` | string | No | Filter by specific device ID |
| `site_id` | string | No | Filter by site (e.g., "WY-ALPHA") |
| `device_type` | string | No | Filter by type: "turbine", "thermal_engine", "electrical_rotor", "ogd" |
| `limit` | integer | No | Max results (default: 100, max: 1000) |
| `offset` | integer | No | Pagination offset (default: 0) |

**Example Request**:
```bash
curl "http://localhost:8000/api/devices?site_id=WY-ALPHA&device_type=turbine&limit=10"
```

**Response**:
```json
[
  {
    "id": 12345,
    "device_id": "TURB-00912",
    "device_type": "turbine",
    "site_id": "WY-ALPHA",
    "timestamp_utc": "2025-11-16T12:30:45Z",
    "metrics": {
      "rpm": 3487,
      "inlet_temp_c": 412.6,
      "outlet_temp_c": 389.2,
      "power_kw": 12850.4,
      "vibration_mm": 0.08
    },
    "status": {
      "state": "OK",
      "code": "TURB-OK"
    },
    "created_at": "2025-11-16T12:30:47Z"
  }
]
```

**Metrics by Device Type**:

**Turbine**:
- `rpm`: Rotations per minute
- `inlet_temp_c`: Inlet temperature (Celsius)
- `outlet_temp_c`: Outlet temperature (Celsius)
- `power_kw`: Power output (kilowatts)
- `vibration_mm`: Vibration level (millimeters)

**Thermal Engine**:
- `coolant_temp_c`: Coolant temperature
- `exhaust_temp_c`: Exhaust temperature
- `fuel_flow_lph`: Fuel flow (liters per hour)
- `load_percent`: Load percentage

**Electrical Rotor**:
- `rpm`: Rotations per minute
- `voltage_v`: Voltage
- `current_a`: Current (amperes)
- `power_factor`: Power factor
- `temperature_c`: Temperature

**Oil & Gas Device (OGD)**:
- `pressure_psi`: Pressure (PSI)
- `flow_rate_bpd`: Flow rate (barrels per day)
- `temperature_c`: Temperature
- `valve_position_percent`: Valve position

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Server error

---

### User Sessions

#### GET `/api/users`

Retrieve user session information.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string | No | Filter by status: "active", "idle", "disconnected" |
| `region` | string | No | Filter by region |
| `limit` | integer | No | Max results (default: 100) |

**Example Request**:
```bash
curl "http://localhost:8000/api/users?status=active"
```

**Response**:
```json
{
  "active_users": 487,
  "total_sessions": 1000,
  "regions": {
    "NA-WEST": 312,
    "NA-EAST": 175,
    "EU-CENTRAL": 201,
    "APAC": 312
  },
  "sessions": [
    {
      "id": 123,
      "user_id": "user_0042",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "connection_status": "active",
      "region": "NA-WEST",
      "login_time": "2025-11-16T08:30:00Z",
      "logout_time": null,
      "last_activity": "2025-11-16T12:30:45Z"
    }
  ]
}
```

**Session States**:
- `active`: User actively using system
- `idle`: User inactive >5 minutes
- `disconnected`: User logged out

**Status Codes**:
- `200 OK`: Success
- `500 Internal Server Error`: Server error

---

### System Logs

#### GET `/api/logs`

Retrieve Apache-style HTTP access logs.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ip_address` | string | No | Filter by IP address |
| `status_code` | integer | No | Filter by HTTP status (e.g., 404, 500) |
| `method` | string | No | Filter by HTTP method (GET, POST, etc.) |
| `limit` | integer | No | Max results (default: 100, max: 1000) |

**Example Request**:
```bash
curl "http://localhost:8000/api/logs?status_code=404&limit=20"
```

**Response**:
```json
[
  {
    "id": 456,
    "ip_address": "192.168.1.100",
    "timestamp": "2025-11-16T12:30:45Z",
    "method": "GET",
    "endpoint": "/api/missing-resource",
    "protocol": "HTTP/1.1",
    "status_code": 404,
    "response_size_bytes": 1234,
    "referrer": "https://example.com/page",
    "user_agent": "Mozilla/5.0..."
  }
]
```

**Common Status Codes**:
- `200`: Success
- `301`: Redirect
- `400`: Bad Request
- `404`: Not Found
- `500`: Server Error

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Server error

---

### Image Metadata

#### GET `/api/images`

Retrieve processed image metadata with safety compliance.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_type` | string | No | Filter by device type |
| `site_id` | string | No | Filter by site |
| `has_hard_hat` | boolean | No | Filter by hard hat presence |
| `has_safety_vest` | boolean | No | Filter by safety vest presence |
| `min_compliance` | integer | No | Minimum compliance score (0-100) |
| `limit` | integer | No | Max results (default: 50) |

**Example Request**:
```bash
curl "http://localhost:8000/api/images?has_hard_hat=false&limit=10"
```

**Response**:
```json
{
  "total_images": 156,
  "avg_compliance": 78.4,
  "images": [
    {
      "filename": "IMG_20240615_143052.jpg",
      "device_type": "turbine",
      "site_id": "WY-ALPHA",
      "description": "Worker inspecting turbine equipment",
      "keywords": ["hard hat", "safety vest", "outdoor", "inspection"],
      "safety_compliance": {
        "has_hard_hat": false,
        "has_safety_vest": true,
        "has_inspection_equipment": true,
        "compliance_score": 70
      },
      "processed": true,
      "processed_at": "2025-11-16T10:00:00Z"
    }
  ]
}
```

**Compliance Score Calculation**:
- Hard Hat: 40% weight
- Safety Vest: 30% weight
- Inspection Equipment: 30% weight
- Total: 0-100%

**Status Codes**:
- `200 OK`: Success
- `500 Internal Server Error`: Server error

---

### Natural Language Query (AI-Driven Routing)

#### POST `/api/query`

Execute natural language queries with **AI-driven intelligent routing** using OpenAI function calling or Cohere tool use.

**How It Works**:
1. AI analyzes your question semantically
2. AI selects appropriate data source(s): images, documents, or logs
3. Can query multiple sources for comprehensive answers
4. Falls back to keyword routing if AI unavailable (Tier-0 reliability)

**Request Body**:
```json
{
  "question": "How many safety incidents occurred in BP operations in 2024?"
}
```

**Example Requests**:
```bash
# AI routes to images (MongoDB)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me sites where workers do not have hard hats"}'

# AI routes to documents (FAISS vector search)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "BP Tier 1 and Tier 2 safety events in 2024"}'

# AI routes to BOTH documents AND images (multi-source)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare BP safety reports to camera footage"}'
```

**Response**:
```json
{
  "question": "Show me sites where workers do not have hard hats",
  "result": {
    "answer": "Found 12 images showing workers WITHOUT proper safety equipment...",
    "routing_method": "ai_function_calling",
    "tools_called": ["search_images"],
    "data": [...],
    "sites": ["turbine", "thermal_engine"],
    "count": 12,
    "avg_compliance": 45.2,
    "type": "image_analysis"
  },
  "timestamp": "2025-11-16T12:30:45Z"
}
```

**Routing Methods** (in `routing_method` field):
- `ai_function_calling` - OpenAI gpt-4o function calling (preferred)
- `ai_tool_use` - Cohere command-a-vision tool use (fallback)
- `keyword_fallback` - Keyword-based routing (Tier-0 reliability)

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Missing or invalid question
- `500 Internal Server Error`: RAG service error

---

### Specialized Query Endpoints (Explicit Routing)

Use these endpoints to bypass AI routing and directly query specific data sources.

#### POST `/api/query/images`

Search MongoDB image embeddings for safety compliance analysis.

**Request**:
```bash
curl -X POST http://localhost:8000/api/query/images \
  -H "Content-Type: application/json" \
  -d '{"question": "Workers with tablets and hard hats"}'
```

**Response**:
```json
{
  "question": "Workers with tablets and hard hats",
  "answer": "Found 8 images showing workers with proper safety equipment...",
  "data": [...],
  "sites": ["turbine", "electrical_rotor"],
  "count": 8,
  "avg_compliance": 92.5,
  "source": "mongodb_images"
}
```

---

#### POST `/api/query/documents`

Search BP Annual Reports using FAISS vector semantic search.

**Request**:
```bash
curl -X POST http://localhost:8000/api/query/documents \
  -H "Content-Type: application/json" \
  -d '{"question": "BP Tier 1 and Tier 2 process safety events"}'
```

**Response**:
```json
{
  "question": "BP Tier 1 and Tier 2 process safety events",
  "answer": "According to BP's 2024 Annual Report, there were 38 Tier 1 and Tier 2...",
  "sources": [
    {
      "text": "In 2024, BP reported 38 Tier 1 and Tier 2 process safety events...",
      "source": "BP_Annual_Report_2024.pdf",
      "year": 2024,
      "similarity_score": 0.89
    }
  ],
  "source": "bp_documents_vector_search"
}
```

---

#### POST `/api/query/logs`

Search PostgreSQL operational logs for system analytics.

**Request**:
```bash
curl -X POST http://localhost:8000/api/query/logs \
  -H "Content-Type: application/json" \
  -d '{"question": "Top IP addresses by traffic"}'
```

**Response**:
```json
{
  "question": "Top IP addresses by traffic",
  "answer": "The IP address generating the most requests is 192.168.1.100 with 1,234 requests...",
  "data": [
    {
      "ip_address": "192.168.1.100",
      "request_count": 1234,
      "error_count": 45
    }
  ],
  "source": "postgresql_logs"
}
```

---

## 🤖 RAG Service API (Port 8001)

Base URL: `http://localhost:8001`

### Health Check

#### GET `/health`

Check RAG service health.

**Response**:
```json
{
  "status": "healthy",
  "service": "RAG Service"
}
```

---

### Statistics Endpoint

#### GET `/stats`

Get RAG service statistics.

**Response**:
```json
{
  "bp_documents_loaded": 2,
  "log_entries_cached": 10000,
  "cohere_enabled": false,
  "openai_enabled": true,
  "ai_provider": "OpenAI",
  "vector_index_size": 1247,
  "endpoints": {
    "unified": "/query (auto-routes based on keywords)",
    "images": "/query/images (MongoDB image embeddings)",
    "documents": "/query/documents (FAISS vector search on PDFs)",
    "logs": "/query/logs (PostgreSQL operational logs)"
  }
}
```

---

### Query Endpoint

#### POST `/query`

Execute natural language queries with AI synthesis using **vector-based semantic search**.

**RAG Architecture**:
- **Vector Search**: Cohere `embed-english-v3.0` embeddings (1024 dimensions)
- **FAISS Index**: Fast similarity search with cosine distance
- **Hybrid Retrieval**: Combines vector search + pattern matching + keyword search
- **Chunking**: Overlapping 1500-character chunks with 300-char overlap
- **Synthesis**: Cohere `command-a-vision-07-2025` for answer generation

**Request Body**:
```json
{
  "question": "string (required)",
  "context": "string (optional)"
}
```

**Example Requests**:

**BP Document Query**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many Tier 1 and Tier 2 process safety events did BP have in 2024?"
  }'
```

**Image Analysis Query**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show turbine sites where workers are not wearing hard hats"
  }'
```

**Log Analysis Query**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which IP addresses generated the most 404 errors?"
  }'
```

**Response Format**:

**BP Documents** (with vector search):
```json
{
  "answer": "BP reported 38 Tier 1 and Tier 2 process safety events in 2024, a decrease from 39 in 2023...",
  "sources": [
    {
      "text": "Process safety events decreased to 38...",
      "source": "bp-annual-report-and-form-20f-2024.pdf",
      "year": 2024,
      "similarity_score": 0.89,
      "rank": 1,
      "match_type": "vector"
    }
  ],
  "type": "bp_documents",
  "synthesized": true
}
```

**Source Fields**:
- `text`: Extracted text chunk containing relevant information
- `source`: Source document filename
- `year`: Year extracted from filename
- `similarity_score`: Cosine similarity (0-1, higher is better)
- `rank`: Ranking position in results
- `match_type`: "vector" (semantic), "pattern" (regex), or "keyword" (literal)

**Images**:
```json
{
  "answer": "Analysis reveals 12 images from 4 sites showing workers without proper hard hat PPE. Turbine sites show 56.7% compliance...",
  "data": [
    {
      "filename": "IMG_20240615_143052.jpg",
      "device_type": "turbine",
      "site_id": "WY-ALPHA",
      "safety_compliance": {...}
    }
  ],
  "sites": ["turbine", "thermal_engine"],
  "avg_compliance": 56.7,
  "type": "image_analysis",
  "synthesized": true,
  "query_time_ms": 892
}
```

**Logs**:
```json
{
  "answer": "The top error-generating IP addresses are 192.168.1.100 with 45 404 errors, 10.0.0.15 with 32 errors...",
  "data": {
    "top_ips": [
      {"ip_address": "192.168.1.100", "error_count": 45},
      {"ip_address": "10.0.0.15", "error_count": 32}
    ]
  },
  "type": "log_analysis",
  "synthesized": true,
  "query_time_ms": 234
}
```

**Fallback Mode** (Cohere unavailable or vector search failed):
```json
{
  "answer": "Found 5 safety-related sections in BP Annual Reports. From bp-annual-report-2024.pdf: [excerpt from documents]",
  "sources": [
    {
      "text": "...",
      "source": "bp-annual-report-2024.pdf",
      "year": 2024,
      "relevance": 12,
      "match_type": "keyword"
    }
  ],
  "type": "bp_documents",
  "synthesized": false
}
```

**How Hybrid Search Works**:

1. **Vector Search** (Primary): Generates query embedding → searches FAISS index → retrieves top 10 semantically similar chunks
2. **Pattern Search** (Specific metrics): Regex patterns to find exact numbers like "38 Tier 1 and Tier 2"
3. **Keyword Search** (Fallback): Literal string matching if vector search unavailable
4. **Deduplication**: Removes duplicate results by comparing first 100 characters
5. **Ranking**: Sorts by relevance score (vector similarity × 30 or keyword count)
6. **Synthesis**: Top 5 results sent to Cohere LLM for natural language answer

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Missing question
- `500 Internal Server Error`: RAG processing error

---

### Statistics Endpoint

#### GET `/stats`

Get RAG service statistics.

**Response**:
```json
{
  "total_queries": 1234,
  "queries_by_type": {
    "bp_documents": 456,
    "image_analysis": 389,
    "log_analysis": 245,
    "combined": 144
  },
  "avg_query_time_ms": 1456,
  "cohere_success_rate": 0.96
}
```

---

## 🔄 Failover Orchestrator API (Port 8003)

Base URL: `http://localhost:8003`

### Health Check

#### GET `/health`

Check failover orchestrator health.

**Response**:
```json
{
  "status": "healthy",
  "current_region": "region1",
  "postgres_primary_healthy": true,
  "postgres_replica_healthy": true,
  "redis_master_healthy": true,
  "redis_sentinel_healthy": true
}
```

---

### Status Endpoint

#### GET `/status`

Get current failover status and history.

**Response**:
```json
{
  "current_region": "region1",
  "last_failover": {
    "target_region": "region2",
    "success": true,
    "total_failover_time": 3.4,
    "tier0_compliant": true,
    "timestamp": "2025-11-16T12:30:00Z",
    "steps": {
      "health_check": 0.2,
      "database_promotion": 1.2,
      "redis_failover": 0.8,
      "routing_update": 0.1,
      "validation": 1.1
    }
  },
  "postgres_replication_lag": 0.15,
  "redis_sentinel_status": "healthy"
}
```

**Fields**:
- `current_region`: Active region (region1 or region2)
- `last_failover`: Details of most recent failover
- `total_failover_time`: Seconds taken for complete failover
- `tier0_compliant`: Whether failover met <5s requirement
- `postgres_replication_lag`: Replication lag in seconds
- `steps`: Timing breakdown for each failover phase

---

### Trigger Failover

#### POST `/failover/{target_region}`

Initiate multi-region failover.

**Path Parameters**:
- `target_region`: Target region ("region1" or "region2")

**Example Request**:
```bash
curl -X POST http://localhost:8003/failover/region2
```

**Response** (Success):
```json
{
  "success": true,
  "target_region": "region2",
  "total_failover_time": 3.4,
  "tier0_compliant": true,
  "steps": {
    "health_check": {
      "duration": 0.2,
      "postgres_replica_healthy": true,
      "postgres_replication_lag": 0.15
    },
    "database_promotion": {
      "duration": 1.2,
      "promoted": true,
      "new_primary": "postgres-replica"
    },
    "redis_failover": {
      "duration": 0.8,
      "sentinel_triggered": true,
      "new_master": "redis-replica"
    },
    "routing_update": {
      "duration": 0.1,
      "updated": true
    },
    "validation": {
      "duration": 1.1,
      "write_test_passed": true,
      "api_responsive": true
    }
  },
  "timestamp": "2025-11-16T12:30:45Z"
}
```

**Response** (Failure):
```json
{
  "success": false,
  "target_region": "region2",
  "error": "Replica not healthy: replication lag too high (5.2s)",
  "timestamp": "2025-11-16T12:30:45Z"
}
```

**Status Codes**:
- `200 OK`: Failover initiated successfully
- `400 Bad Request`: Invalid target region
- `409 Conflict`: Already in target region
- `500 Internal Server Error`: Failover failed

**Important Notes**:
- Failover is a critical operation - test in non-production first
- Target SLA: <5 seconds total downtime
- Validates health before proceeding
- Performs write test to confirm success
- Updates routing automatically

---

### Validate Failover

#### GET `/validate`

Validate current failover state consistency.

**Response**:
```json
{
  "valid": true,
  "current_region": "region2",
  "postgres_primary": "postgres-replica",
  "postgres_is_primary": true,
  "redis_master": "redis-replica",
  "all_checks_passed": true
}
```

---

## 📊 Prometheus Metrics API (Port 9090)

Base URL: `http://localhost:9090`

### Available Metrics

Backend API exposes Prometheus metrics at `/metrics`:

**Example Metrics**:
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/devices",status="200"} 1234

# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1"} 1000
http_request_duration_seconds_bucket{le="0.5"} 1200
http_request_duration_seconds_bucket{le="1.0"} 1234

# HELP cache_hit_rate Redis cache hit rate
# TYPE cache_hit_rate gauge
cache_hit_rate 0.82

# HELP database_connections PostgreSQL active connections
# TYPE database_connections gauge
database_connections 15
```

**Query Examples**:
```bash
# Query metrics
curl "http://localhost:9090/api/v1/query?query=http_requests_total"

# Query range
curl "http://localhost:9090/api/v1/query_range?query=rate(http_requests_total[5m])&start=2025-11-16T12:00:00Z&end=2025-11-16T13:00:00Z&step=15s"
```

---

## 🔌 MQTT Broker (Port 1883)

### Topic Structure

**Topic Pattern**: `og/field/{site_id}/{device_type}/{device_id}`

**Examples**:
- `og/field/WY-ALPHA/turbine/TURB-00912`
- `og/field/TX-EAGLE/thermal_engine/THERM-01234`
- `og/field/CA-DELTA/electrical_rotor/ROTOR-05678`
- `og/field/OK-BRAVO/ogd/OGD-09876`

### Subscribe to Topics

```bash
# All devices
mosquitto_sub -h localhost -p 1883 -t "og/field/#" -v

# Specific site
mosquitto_sub -h localhost -p 1883 -t "og/field/WY-ALPHA/#" -v

# Specific device type across all sites
mosquitto_sub -h localhost -p 1883 -t "og/field/+/turbine/+" -v

# Specific device
mosquitto_sub -h localhost -p 1883 -t "og/field/WY-ALPHA/turbine/TURB-00912" -v
```

### Publish Messages

```bash
mosquitto_pub -h localhost -p 1883 \
  -t "og/field/TEST/turbine/TEST-001" \
  -m '{
    "device_id": "TEST-001",
    "device_type": "turbine",
    "site_id": "TEST",
    "timestamp_utc": "2025-11-16T12:30:45Z",
    "metrics": {
      "rpm": 3500,
      "inlet_temp_c": 410.0,
      "power_kw": 12500.0
    },
    "status": {
      "state": "OK",
      "code": "TURB-OK"
    }
  }'
```

**Message Schema**: See [Data Templates](../assignment-materials/DataTemplates/)

---

## 🐰 RabbitMQ API (Port 15672)

### Management UI

Access: http://localhost:15672

**Credentials**:
- Username: `tier0admin`
- Password: `tier0secure`

### HTTP API

**List Queues**:
```bash
curl -u tier0admin:tier0secure http://localhost:15672/api/queues
```

**Queue Details**:
```bash
curl -u tier0admin:tier0secure \
  http://localhost:15672/api/queues/%2F/user_activity_queue
```

**Publish Message** (via HTTP API):
```bash
curl -X POST -u tier0admin:tier0secure \
  http://localhost:15672/api/exchanges/%2F/amq.default/publish \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {},
    "routing_key": "user_activity_queue",
    "payload": "{\"user_id\":\"test_user\",\"event\":\"login\"}",
    "payload_encoding": "string"
  }'
```

---

## 🔐 Authentication & Security

### Current Implementation

**Development Mode** (Current):
- No authentication required
- All endpoints publicly accessible
- Suitable for demo and testing

**Production Recommendations**:
- Implement JWT authentication
- API key management
- Rate limiting
- TLS/SSL encryption
- Network isolation

See [Security Guide](security.md) for production hardening.

---

## 📊 Rate Limits

**Current Limits** (Development):
- No rate limiting implemented
- Suitable for demo purposes

**Recommended Production Limits**:
| Endpoint | Limit | Window |
|----------|-------|--------|
| `/api/*` | 1000 requests | per minute |
| `/query` | 100 requests | per minute |
| `/failover/*` | 10 requests | per hour |

---

## 🐛 Error Responses

### Standard Error Format

```json
{
  "error": "Error message",
  "detail": "Detailed explanation",
  "timestamp": "2025-11-16T12:30:45Z"
}
```

### Common Errors

**400 Bad Request**:
```json
{
  "error": "Invalid parameter",
  "detail": "device_type must be one of: turbine, thermal_engine, electrical_rotor, ogd"
}
```

**404 Not Found**:
```json
{
  "error": "Resource not found",
  "detail": "No device found with ID: INVALID-123"
}
```

**500 Internal Server Error**:
```json
{
  "error": "Internal server error",
  "detail": "Database connection failed"
}
```

**503 Service Unavailable**:
```json
{
  "error": "Service unavailable",
  "detail": "PostgreSQL is not responding"
}
```

---

## 📚 Related Documentation

- [Testing Guide](testing.md) - API testing procedures
- [Development Guide](development.md) - Local API development
- [Architecture](architecture.md) - System design
- [Data Pipelines](data-pipelines.md) - Data flow details

---

**Interactive API Documentation**: http://localhost:8000/docs (Swagger UI)
