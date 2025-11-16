# Development Guide

This guide covers local development workflows, common commands, debugging, and contribution guidelines.

---

## 🛠️ Development Setup

### Prerequisites

- Docker Desktop installed and running
- Git for version control
- Code editor (VS Code, PyCharm, etc.)
- Basic knowledge of Python, JavaScript, Docker

### Quick Start

```bash
# Clone repository
git clone https://github.com/your-org/EntSystemsHackaton.git
cd EntSystemsHackaton

# Start development environment
docker-compose up --build

# Open in browser
open http://localhost:3000
```

---

## 📝 Common Development Commands

### Service Management

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up backend

# Start in background
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart backend

# View running services
docker-compose ps
```

### Logs & Debugging

```bash
# View all logs
docker-compose logs

# Follow logs (live tail)
docker-compose logs -f

# View logs for specific service
docker-compose logs backend
docker-compose logs rag-service

# Follow logs with filter
docker-compose logs -f | grep ERROR

# Last 100 lines
docker-compose logs --tail=100 backend

# Since timestamp
docker-compose logs --since 2025-11-16T12:00:00
```

### Rebuilding Services

```bash
# Rebuild specific service
docker-compose up -d --build backend

# Rebuild without cache (force fresh build)
docker-compose build --no-cache backend
docker-compose up -d backend

# Rebuild all services
docker-compose down
docker-compose up --build
```

### Database Access

```bash
# PostgreSQL primary
docker exec -it tier0-postgres psql -U tier0user -d tier0_db

# PostgreSQL replica
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db

# MongoDB
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo

# Redis master
docker exec -it tier0-redis redis-cli

# Redis replica
docker exec -it tier0-redis-replica redis-cli

# Redis Sentinel
docker exec -it tier0-redis-sentinel redis-cli -p 26379
```

**Useful SQL Queries**:
```sql
-- Device telemetry count
SELECT COUNT(*) FROM device_telemetry;

-- Recent devices
SELECT device_id, device_type, site_id, timestamp_utc
FROM device_telemetry
ORDER BY timestamp_utc DESC
LIMIT 10;

-- Active users
SELECT user_id, connection_status, region, login_time
FROM user_sessions
WHERE connection_status='active'
ORDER BY login_time DESC;

-- System logs with errors
SELECT ip_address, method, endpoint, status_code, COUNT(*) as error_count
FROM system_logs
WHERE status_code >= 400
GROUP BY ip_address, method, endpoint, status_code
ORDER BY error_count DESC
LIMIT 20;
```

**Useful MongoDB Queries**:
```javascript
// Switch to images database
use tier0_images

// Count processed images
db.images.countDocuments({processed: true})

// Find images without hard hats
db.images.find({"safety_compliance.has_hard_hat": false}).limit(5)

// Average safety compliance by device type
db.images.aggregate([
  {$group: {
    _id: "$device_type",
    avg_compliance: {$avg: "$safety_compliance.compliance_score"}
  }}
])
```

**Useful Redis Commands**:
```bash
# Info about replication
INFO replication

# Get all keys
KEYS *

# Get cached devices
GET "devices:all"

# Monitor real-time commands
MONITOR

# Get Sentinel info
docker exec -it tier0-redis-sentinel redis-cli -p 26379 SENTINEL masters
```

---

## 🧪 Testing During Development

### API Testing

```bash
# Health check
curl http://localhost:8000/health

# Device telemetry
curl http://localhost:8000/api/devices | jq

# User sessions
curl http://localhost:8000/api/users | jq

# RAG query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me sites with safety violations"}' | jq

# Failover status
curl http://localhost:8003/status | jq
```

### MQTT Testing

```bash
# Subscribe to all device telemetry
mosquitto_sub -h localhost -p 1883 -t "og/field/#" -v

# Subscribe to specific site
mosquitto_sub -h localhost -p 1883 -t "og/field/WY-ALPHA/#" -v

# Subscribe to specific device type
mosquitto_sub -h localhost -p 1883 -t "og/field/+/turbine/+" -v

# Publish test message
mosquitto_pub -h localhost -p 1883 \
  -t "og/field/TEST/turbine/TEST-001" \
  -m '{"device_id":"TEST-001","device_type":"turbine","site_id":"TEST","timestamp_utc":"2025-11-16T12:00:00Z","metrics":{"rpm":3500},"status":{"state":"OK"}}'
```

### RabbitMQ Testing

Access management UI: http://localhost:15672 (tier0admin / tier0secure)

```bash
# View queues
docker exec -it tier0-rabbitmq rabbitmqctl list_queues

# View connections
docker exec -it tier0-rabbitmq rabbitmqctl list_connections

# Purge queue (clear all messages)
docker exec -it tier0-rabbitmq rabbitmqctl purge_queue user_activity_queue
```

---

## 🔧 Modifying Services

### Backend API (FastAPI)

**Location**: `backend/main.py`

```python
# Add new endpoint
@app.get("/api/custom")
async def custom_endpoint():
    return {"message": "Hello from custom endpoint"}
```

**Restart after changes**:
```bash
docker-compose up -d --build backend
docker-compose logs -f backend
```

**Test**:
```bash
curl http://localhost:8000/api/custom
```

### RAG Service

**Location**: `services/rag-service/rag_server.py`

**Architecture**:
- **Vector Search**: Uses FAISS + Cohere embeddings for semantic retrieval
- **Hybrid RAG**: Combines vector search + pattern matching + keyword search
- **Dependencies**: `faiss-cpu`, `cohere`, `numpy`, `scikit-learn` (see `requirements.txt`)

**Example: Add new query type**:
```python
def query_custom(self, question: str) -> Dict:
    """Answer custom questions"""
    return {
        "answer": "Custom response",
        "type": "custom"
    }
```

**Development Notes**:
- Vector index builds on startup (may take 1-2 minutes)
- Monitor logs for "✓ Built vector index with X chunks"
- Requires COHERE_API_KEY in environment for full functionality

**Restart**:
```bash
docker-compose build --no-cache rag-service
docker-compose up -d rag-service
docker-compose logs -f rag-service
```

### Frontend

**Location**: `frontend/dashboard.html`, `frontend/dashboard.js`, `frontend/dashboard.css`

**Live reload**: Changes to static files require container restart:
```bash
docker-compose restart frontend
```

**Or rebuild**:
```bash
docker-compose up -d --build frontend
```

---

## 🐞 Debugging

### Container Shell Access

```bash
# Backend container
docker exec -it tier0-backend /bin/bash

# RAG service container
docker exec -it tier0-rag-service /bin/bash

# Inside container, you can:
ls -la
cat main.py
printenv
python -c "import cohere; print(cohere.__version__)"
```

### View Environment Variables

```bash
# View all env vars in backend
docker exec -it tier0-backend printenv

# View specific variable
docker exec -it tier0-backend printenv COHERE_API_KEY
```

### Check Service Health

```bash
# Backend health
docker exec -it tier0-backend curl -f http://localhost:8000/health || echo "Backend unhealthy"

# PostgreSQL health
docker exec -it tier0-postgres pg_isready -U tier0user || echo "PostgreSQL unhealthy"

# MongoDB health
docker exec -it tier0-mongodb mongosh --eval "db.adminCommand('ping')" || echo "MongoDB unhealthy"

# Redis health
docker exec -it tier0-redis redis-cli ping || echo "Redis unhealthy"
```

### Python Debugging in Containers

**Add breakpoint in code**:
```python
import pdb; pdb.set_trace()
```

**Run container in interactive mode**:
```bash
docker-compose up backend
# Container will pause at breakpoint
# Type 'c' to continue, 'n' for next, 'p variable' to print
```

---

## 📦 Working with Dependencies

### Python Dependencies

**Backend** (`backend/requirements.txt`):
```bash
# Add new dependency
echo "new-package==1.0.0" >> backend/requirements.txt

# Rebuild
docker-compose up -d --build backend
```

**Verify installation**:
```bash
docker exec -it tier0-backend pip list | grep new-package
```

### Node.js Dependencies (if applicable)

```bash
# Add to frontend (if using npm)
echo "new-package@1.0.0" >> frontend/package.json

# Rebuild
docker-compose up -d --build frontend
```

---

## 🧬 Database Migrations

### PostgreSQL Schema Changes

**Option 1: Manual Migration**
```bash
# Connect to PostgreSQL
docker exec -it tier0-postgres psql -U tier0user -d tier0_db

# Run migration SQL
ALTER TABLE device_telemetry ADD COLUMN new_field TEXT;
```

**Option 2: Update init.sql**
```bash
# Edit config/postgres/init.sql
nano config/postgres/init.sql

# Add migration script
ALTER TABLE IF EXISTS device_telemetry ADD COLUMN IF NOT EXISTS new_field TEXT;

# Rebuild (will run migrations on new tables only)
# For existing tables, run manual migration above
```

### MongoDB Schema Changes

MongoDB is schemaless, but you may need to update documents:

```javascript
// Connect to MongoDB
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo

use tier0_images

// Add field to all documents
db.images.updateMany({}, {$set: {new_field: "default_value"}})
```

---

## 🔄 Development Workflows

### Feature Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Make changes** to service code

3. **Rebuild and test**
   ```bash
   docker-compose up -d --build [service-name]
   docker-compose logs -f [service-name]
   ```

4. **Test endpoints**
   ```bash
   curl http://localhost:8000/api/new-endpoint
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "Add new feature"
   git push origin feature/new-feature
   ```

### Bug Fix Workflow

1. **Reproduce bug**
   - Check logs: `docker-compose logs [service-name]`
   - Test endpoint
   - Verify database state

2. **Identify root cause**
   - Add debug logging
   - Check service dependencies
   - Review recent changes

3. **Fix bug** in code

4. **Rebuild and verify**
   ```bash
   docker-compose build --no-cache [service-name]
   docker-compose up -d [service-name]
   # Verify fix
   ```

5. **Commit and document**
   ```bash
   git commit -m "Fix: Description of bug fix

   - Root cause: X
   - Solution: Y
   - Tested: Z"
   ```

---

## 🧪 Integration Testing

### Test Full Pipeline

**Device Telemetry Pipeline**:
```bash
# 1. Publish test message
mosquitto_pub -h localhost -p 1883 \
  -t "og/field/TEST/turbine/TEST-001" \
  -m '{"device_id":"TEST-001","device_type":"turbine","site_id":"TEST","timestamp_utc":"2025-11-16T12:00:00Z","metrics":{"rpm":3500},"status":{"state":"OK"}}'

# 2. Verify in PostgreSQL
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT * FROM device_telemetry WHERE device_id='TEST-001' ORDER BY timestamp_utc DESC LIMIT 1;"

# 3. Verify in API
curl http://localhost:8000/api/devices | jq '.[] | select(.device_id=="TEST-001")'
```

**RAG Query Pipeline**:
```bash
# Test BP document query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many safety incidents occurred in BP operations in 2024?"}' | jq

# Verify Cohere was used
docker-compose logs rag-service | grep "Cohere synthesized answer"
```

**Failover Pipeline**:
```bash
# Test failover
curl -X POST http://localhost:8003/failover/region2 | jq

# Verify PostgreSQL replica promoted
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "SELECT pg_is_in_recovery();"  # Should return 'f' (false) if promoted

# Verify Redis Sentinel updated
docker exec -it tier0-redis-sentinel redis-cli -p 26379 \
  SENTINEL get-master-addr-by-name tier0master
```

---

## 📊 Performance Profiling

### Backend API Profiling

```python
# Add profiling to endpoint
from time import time

@app.get("/api/devices")
async def get_devices():
    start = time()
    # ... existing code ...
    duration = time() - start
    logger.info(f"get_devices took {duration:.3f}s")
    return devices
```

### Database Query Performance

```sql
-- Enable query timing
\timing on

-- Explain query plan
EXPLAIN ANALYZE SELECT * FROM device_telemetry WHERE site_id='WY-ALPHA';

-- View slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## 🔒 Security During Development

### Do Not Commit Secrets

```bash
# Never commit:
.env
*.key
*.pem
credentials.json

# Add to .gitignore
echo "*.key" >> .gitignore
echo ".env" >> .gitignore
```

### Use Environment Variables

```python
# Bad
API_KEY = "sk-1234567890abcdef"

# Good
API_KEY = os.getenv("API_KEY")
```

### Scan for Secrets

```bash
# Install gitleaks
brew install gitleaks

# Scan for secrets
gitleaks detect -v
```

---

## 📚 Related Documentation

- [Deployment Guide](deployment.md) - Deployment procedures
- [API Reference](api-reference.md) - API documentation
- [Testing Guide](testing.md) - Testing strategies
- [Troubleshooting](troubleshooting.md) - Common issues

---

**Next**: Explore [Testing Guide](testing.md) for comprehensive testing procedures.
