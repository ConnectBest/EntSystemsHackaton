# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Tier-0 Enterprise Reliability Engineering System** demonstrating 99.99999% (seven-nines) availability through a simulated Fortune 500 environment. The system integrates IoT telemetry from 100,000 devices, user session monitoring, AI-driven visual intelligence, and distributed message-driven architecture.

## Common Commands

### Start/Stop Services

```bash
# Start all 15 services (initial build takes 3-5 minutes)
docker-compose up --build

# Start in detached mode
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart backend
docker-compose restart device-simulator
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f device-simulator
docker-compose logs -f mqtt-consumer
docker-compose logs -f rag-service
docker-compose logs -f failover-test
```

### Check Service Status

```bash
# List all services
docker-compose ps

# Health check
curl http://localhost:8000/health
curl http://localhost:9090/-/healthy
curl http://localhost:8002/health  # Failover test service
```

### Failover Testing (HA/DR)

The system includes automated failover testing to validate the 99.99999% availability target:

```bash
# View failover test logs
docker-compose logs -f failover-test

# Run tests via API
curl -X POST "http://localhost:8000/api/failover/test?test_type=redis_failover&duration_seconds=30"
curl -X POST "http://localhost:8000/api/failover/test?test_type=database_resilience&duration_seconds=30"
curl -X POST "http://localhost:8000/api/failover/test?test_type=service_availability&duration_seconds=30"

# Get test summary
curl "http://localhost:8000/api/failover/summary"

# Get recent test results
curl "http://localhost:8000/api/failover/results?limit=10"
```

**Via UI:** Open http://localhost:3000, click "Failover Test" tab, and run tests with one click.

**Test Scenarios:**
- 🔴 **Redis Cache Failover**: Simulates Redis failure, measures recovery time
- 💾 **Database Resilience**: Tests database connection stability under load
- 🌐 **Service Availability**: Measures API endpoint responsiveness

**Success Criteria:**
- Availability >= 99.99999%
- Recovery time < 5 seconds
- No data loss during failover

See `FAILOVER_TESTING.md` for complete documentation.

### Database Access

```bash
# PostgreSQL (relational data - device telemetry, user sessions)
docker exec -it tier0-postgres psql -U tier0user -d tier0_db

# MongoDB (images & embeddings)
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo

# Redis (Tier-0 cache)
docker exec -it tier0-redis redis-cli
```

### Data Retention & Cleanup

The system includes an automatic cleanup service to prevent unbounded data growth:

```bash
# View cleanup service logs
docker-compose logs -f data-cleanup

# Manually trigger cleanup (restart service)
docker-compose restart data-cleanup

# Configure retention policies (edit docker-compose.yml environment variables):
# - CLEANUP_INTERVAL_SECONDS: 300  (run every 5 minutes)
# - RETENTION_HOURS: 24  (keep last 24 hours)
# - MAX_RECORDS_PER_TABLE: 100000  (max 100K records)
```

**Manual cleanup commands:**

```bash
# Clear PostgreSQL tables
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c "
TRUNCATE TABLE device_telemetry, user_sessions, system_logs RESTART IDENTITY;
"

# Clear Redis cache
docker exec -it tier0-redis redis-cli FLUSHALL

# Clear MongoDB collections
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo --eval "
use tier0_images;
db.images.deleteMany({});
db.image_embeddings.deleteMany({});
"

# Full system reset (WARNING: Deletes all data)
docker-compose down -v
docker-compose up -d --build
```

### MQTT Testing

```bash
# Subscribe to all device telemetry
mosquitto_sub -h localhost -p 1883 -t "og/field/#" -v

# Subscribe to specific site
mosquitto_sub -h localhost -p 1883 -t "og/field/WY-ALPHA/#" -v

# Test publish
mosquitto_pub -h localhost -p 1883 -t "og/field/TEST/turbine/TEST-001" -m '{"test": true}'
```

### RAG Query Testing (AI-Driven Routing)

The RAG service uses **OpenAI function calling** or **Cohere tool use** to intelligently route queries to the appropriate data source(s).

```bash
# Test AI routing (unified endpoint - routes automatically)
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "Show engineers with hard hats and tablets"}'

# Test explicit endpoints (bypass AI routing)
curl -X POST "http://localhost:8000/api/query/images" \
  -H "Content-Type: application/json" \
  -d '{"question": "Workers without hard hats"}'

curl -X POST "http://localhost:8000/api/query/documents" \
  -H "Content-Type: application/json" \
  -d '{"question": "BP Tier 1 safety events in 2024"}'

curl -X POST "http://localhost:8000/api/query/logs" \
  -H "Content-Type: application/json" \
  -d '{"question": "Top IP addresses by traffic"}'

# Check AI routing status
curl http://localhost:8001/stats | jq '.ai_provider, .routing_method'

# Watch AI routing decisions in real-time
docker logs -f tier0-rag-service | grep -E "(Processing query|AI selected|routing)"
```

**Query Endpoints:**
- `/api/query` - AI-driven routing (auto-selects data source)
- `/api/query/images` - Direct MongoDB image search
- `/api/query/documents` - Direct FAISS vector search (BP PDFs)
- `/api/query/logs` - Direct PostgreSQL log queries

**AI Routing Examples:**
- "Show workers with hard hats" → Routes to MongoDB images
- "BP safety incidents" → Routes to FAISS documents
- "Compare BP reports to camera footage" → Routes to BOTH (multi-source)
- "Top error IPs" → Routes to PostgreSQL logs

**Configuration:**
Set `OPENAI_API_KEY` or `COHERE_API_KEY` in `docker-compose.yml` to enable AI routing. Without API keys, system uses keyword-based fallback routing (Tier-0 reliability).

**Routing Methods (check in response):**
- `"routing_method": "ai_function_calling"` → OpenAI gpt-4o active
- `"routing_method": "ai_tool_use"` → Cohere active
- `"routing_method": "keyword_fallback"` → AI unavailable, using keywords

### Development Workflow

```bash
# Rebuild single service after code changes
docker-compose up --build backend

# View backend logs during development
docker-compose logs -f backend

# Exec into backend container for debugging
docker exec -it tier0-backend /bin/bash
```

## Architecture

### Service Communication Flow

1. **Data Ingestion Layer**
   - `device-simulator` → MQTT (port 1883) → `mqtt-consumer` → PostgreSQL
   - `user-simulator` → RabbitMQ (port 5672) → `rabbitmq-consumer` → PostgreSQL
   - Topic pattern: `og/field/{site_id}/{device_type}/{device_id}`

2. **API Layer**
   - `backend` (FastAPI on port 8000) serves as orchestration middleware
   - Connects to Redis (Tier-0 cache), PostgreSQL, MongoDB, RabbitMQ, MQTT
   - Exposes REST endpoints for frontend

3. **AI Processing Layer**
   - `image-processor`: Processes images from `CMPE273HackathonData/`, generates Cohere embeddings → MongoDB
   - `rag-service`: **AI-driven query routing** using OpenAI/Cohere function calling
     - Analyzes logs (`LogData/logfiles.log`) and BP PDFs using RAG
     - Intelligently routes queries to MongoDB (images), FAISS (documents), or PostgreSQL (logs)
     - Supports multi-source queries with synthesized answers
     - Falls back to keyword routing for 99.99999% reliability

4. **Frontend Layer**
   - Nginx static site on port 3000
   - JavaScript frontend communicates with backend API

5. **Monitoring Layer**
   - Prometheus (port 9090): Metrics collection from backend
   - Grafana (port 3001): Visualization dashboards

6. **Data Lifecycle Layer**
   - `data-cleanup`: Periodic cleanup service to prevent unbounded growth
   - Implements time-based (24h default) and count-based retention (100K records max)
   - Cleans PostgreSQL, MongoDB, and Redis every 5 minutes

7. **Reliability Testing Layer**
   - `failover-test`: HA/DR simulation service (port 8002)
   - Validates 99.99999% availability target through automated tests
   - Tests Redis failover, database resilience, and service availability
   - Provides real-time metrics and historical reporting

### Database Schemas

**PostgreSQL** (`config/postgres/init.sql`):
- `user_sessions`: User activity tracking
- `device_telemetry`: IoT device metrics (JSONB for flexible schema)
- `system_logs`: Apache-style HTTP access logs
- `image_metadata`: Image processing metadata
- `sites`: 10 global sites (WY-ALPHA, TX-EAGLE, etc.)
- `device_registry`: 100,000 device registry

**MongoDB** collections:
- `image_embeddings`: Cohere embeddings for safety compliance queries
- `bp_documents`: RAG-indexed BP Annual Reports

**Redis** keys:
- Device telemetry cache (Tier-0 proxy to PostgreSQL)
- User session state cache
- API response caching

### Message Broker Topics

**MQTT** (Eclipse Mosquitto):
- Base topic: `og/field/{site_id}/{device_type}/{device_id}`
- Device types: `turbine`, `thermal_engine`, `electrical_rotor`, `ogd` (Oil & Gas Device)
- Sites: 10 locations across US (WY-ALPHA, TX-EAGLE, ND-RAVEN, CA-DELTA, OK-BRAVO, CO-SIERRA, LA-GULF, NM-MESA, AK-NORTH, MT-PEAK)

**RabbitMQ**:
- Queue: `user_activity_queue`
- Message format: User session events (login, logout, idle, active)

## Key Files & Locations

### Backend (FastAPI)
- `backend/main.py`: Main FastAPI app with all endpoints
- `backend/config.py`: Centralized settings using Pydantic BaseSettings
- Environment variables injected via `docker-compose.yml`

### Simulators
- `simulators/device-simulator/simulator.py`: Generates telemetry for 100K devices (publishes random subset of 1,000 devices per cycle)
- `simulators/user-simulator/simulator.py`: Simulates 1,000 active users

### AI Services
- `services/image-processor/processor.py`: Cohere embeddings for safety compliance detection
- `services/rag-service/rag_server.py`: RAG for log analysis and BP document queries
- `services/mqtt-consumer/consumer.py`: Ingests MQTT messages → PostgreSQL
- `services/rabbitmq-consumer/consumer.py`: Ingests RabbitMQ messages → PostgreSQL

### Frontend
- `frontend/index.html`: Single-page dashboard
- `frontend/app.js`: Vanilla JavaScript for API communication
- `frontend/styles.css`: Custom styling

### Configuration
- `config/postgres/init.sql`: Database schema initialization
- `config/mosquitto/mosquitto.conf`: MQTT broker configuration
- `config/prometheus/prometheus.yml`: Metrics scraping configuration
- `docker-compose.yml`: Orchestrates all 15 services

### Assignment Materials (Read-Only)
- `assignment-materials/CMPE273HackathonData/`: Images organized by device type
- `assignment-materials/BP_10K/`: BP Annual Reports (2023, 2024)
- `assignment-materials/DataTemplates/`: JSON schemas for device messages

## Environment Variables

All services use environment variables defined in `docker-compose.yml`. To customize:

```bash
# Copy template
cp .env.example .env

# Add AI API keys for intelligent query routing
OPENAI_API_KEY=sk-...      # Preferred (enables gpt-4o function calling for query routing)
COHERE_API_KEY=your_key    # Fallback (enables command-a-vision tool use for query routing)
```

**AI Routing Configuration:**
- **With `OPENAI_API_KEY`**: RAG service uses gpt-4o function calling for intelligent query routing (~95% accuracy)
- **With `COHERE_API_KEY`**: RAG service uses Cohere tool use as fallback (~90% accuracy)
- **Without API keys**: System uses keyword-based routing (Tier-0 reliability, ~70-80% accuracy)

The system automatically falls back to keyword routing if AI providers are unavailable, ensuring 99.99999% uptime.

## Important Implementation Details

### Device Simulation Scale
- Registry contains 100,000 devices in memory (25K per device type)
- Publishes random subset of ~1,000 devices per cycle to avoid overwhelming system
- Full device list distributed across 10 sites (10K devices per site)

### Redis as Tier-0 Cache
- LRU eviction policy with 2GB max memory
- Caches recent device telemetry before PostgreSQL write
- Reduces database load for read-heavy operations

### AI Processing
- **Image Processor**: Uses Cohere embeddings to analyze safety compliance (hard hats, safety equipment)
- **RAG Service**: AI-driven query routing with three capabilities:
  - **MongoDB Image Search**: Safety compliance analysis from site cameras
  - **FAISS Vector Search**: Semantic search on BP Annual Reports (3072-dim OpenAI or 1024-dim Cohere embeddings)
  - **PostgreSQL Log Analysis**: System operational metrics and error tracking
- **Intelligent Routing**: Uses OpenAI gpt-4o function calling or Cohere tool use to automatically select appropriate data source(s)
- **Multi-Source Queries**: Can combine multiple data sources for comprehensive answers (e.g., "Compare BP reports to camera footage")
- **Tier-0 Fallback**: Automatically falls back to keyword-based routing if AI providers unavailable

### Service Dependencies
- All services depend on `redis`, `postgres`, `mongodb`, `rabbitmq`, `mqtt-broker`
- Use `depends_on` in `docker-compose.yml` - services may restart during initial startup
- Health checks ensure services are fully ready before dependent services connect

## Troubleshooting Tips

### Simulators Not Publishing Data
Check simulator logs and ensure MQTT/RabbitMQ brokers are ready:
```bash
docker-compose logs mqtt-broker
docker-compose logs rabbitmq
docker-compose restart device-simulator
```

### Backend Connection Failures
Backend connects to 5+ services - check each dependency:
```bash
docker-compose ps  # Verify all services are "Up"
docker-compose logs postgres
docker-compose logs mongodb
docker-compose logs redis
```

### Port Conflicts
Default ports: 3000 (frontend), 8000 (backend), 5432 (postgres), 6379 (redis), 27017 (mongo), 1883 (mqtt), 5672/15672 (rabbitmq), 9090 (prometheus), 3001 (grafana). Modify in `docker-compose.yml` if conflicts occur.

### No Data in Dashboard
1. Verify simulators are running: `docker-compose ps | grep simulator`
2. Check MQTT consumer is processing messages: `docker-compose logs mqtt-consumer`
3. Query PostgreSQL directly to confirm data ingestion: `SELECT COUNT(*) FROM device_telemetry;`

### AI Routing Not Working
If queries return `"routing_method": "keyword_fallback"` instead of `"ai_function_calling"`:

```bash
# Check if API keys are set in container
docker-compose config | grep -E "(OPENAI|COHERE)_API_KEY"

# Rebuild RAG service to pick up code changes
docker-compose up --build -d rag-service

# Watch for AI routing logs
docker logs -f tier0-rag-service | grep -E "(Processing query|AI selected|routing)"

# Check RAG service AI status
curl http://localhost:8001/stats | jq '.ai_provider, .openai_enabled, .cohere_enabled'
```

Expected log output when AI routing works:
```
INFO:rag_server:Processing query: Show engineers with hard hats
INFO:rag_server:Using OpenAI function calling to route query
INFO:rag_server:AI selected 1 tool(s): ['search_images']
INFO:rag_server:✓ AI routing succeeded. Tools called: ['search_images']
```

## Service URLs

- Dashboard: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- RabbitMQ Management: http://localhost:15672 (tier0admin/tier0secure)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/tier0admin)
