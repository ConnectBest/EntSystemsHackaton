# Testing Guide

This guide covers testing strategies, validation procedures, and quality assurance for the Tier-0 Enterprise SRE System.

---

## 🧪 Testing Overview

### Testing Philosophy

The system implements multiple testing layers to ensure **99.99999% availability**:

1. **Unit Testing**: Individual component validation
2. **Integration Testing**: Service interaction verification
3. **End-to-End Testing**: Complete pipeline validation
4. **Failover Testing**: Multi-region HA/DR validation
5. **Performance Testing**: Scale and throughput verification
6. **AI/ML Testing**: RAG query accuracy validation

---

## 🚀 Quick Test Suite

### System Health Check

```bash
#!/bin/bash
# health-check.sh - Verify all services are operational

echo "=== Tier-0 System Health Check ==="

# Backend API
echo -n "Backend API: "
curl -s http://localhost:8000/health | grep -q "healthy" && echo "✓ OK" || echo "✗ FAIL"

# RAG Service
echo -n "RAG Service: "
curl -s http://localhost:8001/health | grep -q "healthy" && echo "✓ OK" || echo "✗ FAIL"

# Failover Orchestrator
echo -n "Failover Orchestrator: "
curl -s http://localhost:8003/health | grep -q "healthy" && echo "✓ OK" || echo "✗ FAIL"

# PostgreSQL Primary
echo -n "PostgreSQL Primary: "
docker exec -it tier0-postgres pg_isready -U tier0user >/dev/null 2>&1 && echo "✓ OK" || echo "✗ FAIL"

# PostgreSQL Replica
echo -n "PostgreSQL Replica: "
docker exec -it tier0-postgres-replica pg_isready -U tier0user >/dev/null 2>&1 && echo "✓ OK" || echo "✗ FAIL"

# Redis Master
echo -n "Redis Master: "
docker exec -it tier0-redis redis-cli ping 2>&1 | grep -q "PONG" && echo "✓ OK" || echo "✗ FAIL"

# Redis Sentinel
echo -n "Redis Sentinel: "
docker exec -it tier0-redis-sentinel redis-cli -p 26379 ping 2>&1 | grep -q "PONG" && echo "✓ OK" || echo "✗ FAIL"

# MongoDB
echo -n "MongoDB: "
docker exec -it tier0-mongodb mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1 && echo "✓ OK" || echo "✗ FAIL"

# MQTT Broker
echo -n "MQTT Broker: "
mosquitto_sub -h localhost -p 1883 -t "test" -C 1 -W 1 >/dev/null 2>&1 && echo "✓ OK" || echo "✗ FAIL"

# RabbitMQ
echo -n "RabbitMQ: "
docker exec -it tier0-rabbitmq rabbitmqctl status >/dev/null 2>&1 && echo "✓ OK" || echo "✗ FAIL"

echo "=== Health Check Complete ==="
```

**Run**:
```bash
chmod +x health-check.sh
./health-check.sh
```

---

## 📡 API Testing

### Backend API Endpoints

**Health Check**:
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "timestamp": "..."}
```

**Device Telemetry**:
```bash
# Get all devices
curl http://localhost:8000/api/devices | jq

# Expected response structure
[
  {
    "id": 1,
    "device_id": "TURB-00912",
    "device_type": "turbine",
    "site_id": "WY-ALPHA",
    "timestamp_utc": "2025-11-16T12:30:45Z",
    "metrics": {...},
    "status": {...}
  }
]

# Filter by site
curl http://localhost:8000/api/devices?site_id=WY-ALPHA | jq

# Filter by device type
curl http://localhost:8000/api/devices?device_type=turbine | jq

# Limit results
curl http://localhost:8000/api/devices?limit=10 | jq
```

**User Sessions**:
```bash
# Get all users
curl http://localhost:8000/api/users | jq

# Expected response
{
  "active_users": 487,
  "total_sessions": 1000,
  "regions": {
    "NA-WEST": 312,
    "NA-EAST": 175,
    ...
  },
  "sessions": [...]
}
```

**System Logs**:
```bash
# Get recent logs
curl http://localhost:8000/api/logs?limit=20 | jq

# Filter by status code
curl http://localhost:8000/api/logs?status_code=404 | jq

# Filter by IP
curl "http://localhost:8000/api/logs?ip_address=192.168.1.100" | jq
```

**Image Metadata**:
```bash
# Get images with safety compliance
curl http://localhost:8000/api/images | jq

# Expected response
{
  "total_images": 156,
  "avg_compliance": 78.4,
  "images": [
    {
      "filename": "IMG_20240615_143052.jpg",
      "device_type": "turbine",
      "safety_compliance": {
        "has_hard_hat": true,
        "has_safety_vest": true,
        "compliance_score": 100
      }
    }
  ]
}
```

### RAG Service Endpoints

**BP Document Query**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many safety incidents occurred in BP operations in 2024?"
  }' | jq

# Expected response
{
  "answer": "BP reported 38 Tier 1 and Tier 2 process safety events in 2024...",
  "sources": [...],
  "type": "bp_documents",
  "synthesized": true,
  "query_time_ms": 1234
}
```

**Image Query**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me sites where workers do not have hard hats"
  }' | jq

# Expected response
{
  "answer": "Analysis reveals 12 images from 4 sites showing workers without proper hard hat PPE...",
  "data": [...],
  "sites": ["thermal_engine", "turbine"],
  "avg_compliance": 56.7,
  "type": "image_analysis",
  "synthesized": true
}
```

**Log Query**:
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which IP addresses generated the most errors?"
  }' | jq

# Expected response
{
  "answer": "The top error-generating IPs are 192.168.1.100 (45 errors), 10.0.0.15 (32 errors)...",
  "data": {...},
  "type": "log_analysis",
  "synthesized": true
}
```

**Combined Query** (Safety Compliance):
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the safety incident trends and image compliance?"
  }' | jq

# Expected: Combined BP document + image analysis
```

### Failover Orchestrator Endpoints

**Status Check**:
```bash
curl http://localhost:8003/status | jq

# Expected response
{
  "current_region": "region1",
  "last_failover": null,
  "postgres_primary_healthy": true,
  "postgres_replica_healthy": true,
  "redis_master_healthy": true,
  "redis_sentinel_healthy": true
}
```

**Trigger Failover**:
```bash
curl -X POST http://localhost:8003/failover/region2 | jq

# Expected response
{
  "success": true,
  "target_region": "region2",
  "total_failover_time": 3.4,
  "tier0_compliant": true,
  "steps": {
    "health_check": 0.2,
    "database_promotion": 1.2,
    "redis_failover": 0.8,
    "routing_update": 0.1,
    "validation": 1.1
  },
  "timestamp": "2025-11-16T12:30:45Z"
}
```

---

## 🔄 Integration Testing

### Device Telemetry Pipeline Test

```bash
#!/bin/bash
# test-device-pipeline.sh - Validate complete device telemetry pipeline

echo "=== Testing Device Telemetry Pipeline ==="

# Step 1: Publish test message to MQTT
echo "1. Publishing test message to MQTT..."
mosquitto_pub -h localhost -p 1883 \
  -t "og/field/TEST/turbine/TEST-001" \
  -m '{
    "device_id": "TEST-001",
    "device_type": "turbine",
    "site_id": "TEST",
    "timestamp_utc": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
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

# Step 2: Wait for MQTT consumer to process
echo "2. Waiting for MQTT consumer to process (5 seconds)..."
sleep 5

# Step 3: Verify in PostgreSQL
echo "3. Verifying in PostgreSQL..."
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT device_id, device_type, site_id, timestamp_utc
   FROM device_telemetry
   WHERE device_id='TEST-001'
   ORDER BY timestamp_utc DESC
   LIMIT 1;"

# Step 4: Verify via API
echo "4. Verifying via Backend API..."
curl -s "http://localhost:8000/api/devices?device_id=TEST-001" | jq

echo "=== Device Telemetry Pipeline Test Complete ==="
```

### User Session Pipeline Test

```bash
#!/bin/bash
# test-user-pipeline.sh - Validate user session pipeline

echo "=== Testing User Session Pipeline ==="

# Note: RabbitMQ consumer handles this automatically
# We can verify by checking PostgreSQL directly

echo "1. Checking active user sessions in PostgreSQL..."
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT user_id, connection_status, region, login_time
   FROM user_sessions
   WHERE connection_status='active'
   ORDER BY login_time DESC
   LIMIT 10;"

echo "2. Verifying via Backend API..."
curl -s http://localhost:8000/api/users | jq '.active_users'

echo "=== User Session Pipeline Test Complete ==="
```

### RAG Pipeline Test

```bash
#!/bin/bash
# test-rag-pipeline.sh - Validate RAG query pipeline

echo "=== Testing RAG Query Pipeline ==="

# Test 1: BP Document Query
echo "1. Testing BP Document Query..."
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many safety incidents occurred in 2024?"}' \
  | jq '.answer, .synthesized'

# Test 2: Image Query
echo "2. Testing Image Query..."
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show turbine sites with workers without hard hats"}' \
  | jq '.answer, .avg_compliance'

# Test 3: Log Query
echo "3. Testing Log Query..."
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Which IPs generated the most errors?"}' \
  | jq '.answer'

# Test 4: Verify Cohere was used
echo "4. Checking RAG service logs for Cohere usage..."
docker-compose logs rag-service | grep "Cohere synthesized answer" | tail -3

echo "=== RAG Pipeline Test Complete ==="
```

---

## 🔄 Failover Testing

### Complete Failover Test Procedure

```bash
#!/bin/bash
# test-failover.sh - Comprehensive failover validation

echo "=== Tier-0 Failover Test ==="

# Pre-failover checks
echo "1. Pre-Failover State..."
echo "Current Region:"
curl -s http://localhost:8003/status | jq '.current_region'

echo -e "\nPostgreSQL Replication Status:"
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT client_addr, state, sync_state FROM pg_stat_replication;"

echo -e "\nPostgreSQL Replica Status:"
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "SELECT pg_is_in_recovery();"  # Should be 't' (true)

echo -e "\nRedis Sentinel Status:"
docker exec -it tier0-redis-sentinel redis-cli -p 26379 \
  SENTINEL get-master-addr-by-name tier0master

# Execute failover
echo -e "\n2. Executing Failover to Region 2..."
FAILOVER_START=$(date +%s)
FAILOVER_RESPONSE=$(curl -s -X POST http://localhost:8003/failover/region2)
FAILOVER_END=$(date +%s)
FAILOVER_DURATION=$((FAILOVER_END - FAILOVER_START))

echo "$FAILOVER_RESPONSE" | jq

# Extract timing
TOTAL_TIME=$(echo "$FAILOVER_RESPONSE" | jq -r '.total_failover_time')
TIER0_COMPLIANT=$(echo "$FAILOVER_RESPONSE" | jq -r '.tier0_compliant')

echo -e "\nFailover Duration: ${FAILOVER_DURATION}s (wall clock)"
echo "Reported Total Time: ${TOTAL_TIME}s"
echo "Tier-0 Compliant (<5s): $TIER0_COMPLIANT"

# Post-failover validation
echo -e "\n3. Post-Failover Validation..."

echo "New Current Region:"
curl -s http://localhost:8003/status | jq '.current_region'

echo -e "\nPostgreSQL Replica (now primary) Status:"
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "SELECT pg_is_in_recovery();"  # Should be 'f' (false) - promoted

echo -e "\nRedis Sentinel Status (new master):"
docker exec -it tier0-redis-sentinel redis-cli -p 26379 \
  SENTINEL get-master-addr-by-name tier0master

# Write validation test
echo -e "\n4. Write Validation Test..."
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "INSERT INTO device_telemetry (device_id, device_type, site_id, timestamp_utc, metrics, status)
   VALUES ('FAILOVER-TEST', 'turbine', 'TEST', NOW(), '{\"rpm\": 3500}', '{\"state\": \"OK\"}');"

docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "SELECT device_id, timestamp_utc FROM device_telemetry WHERE device_id='FAILOVER-TEST';"

# Performance validation
echo -e "\n5. API Response Time Validation..."
TIME_START=$(date +%s%3N)
curl -s http://localhost:8000/health >/dev/null
TIME_END=$(date +%s%3N)
API_LATENCY=$((TIME_END - TIME_START))
echo "Backend API Latency: ${API_LATENCY}ms"

if [ "$TIER0_COMPLIANT" = "true" ] && [ "$API_LATENCY" -lt 1000 ]; then
  echo -e "\n✓ FAILOVER TEST PASSED"
else
  echo -e "\n✗ FAILOVER TEST FAILED"
fi

echo "=== Failover Test Complete ==="
```

### Failover Validation Checklist

- [ ] Failover completes in <5 seconds
- [ ] PostgreSQL replica promoted successfully
- [ ] Redis Sentinel detects new master
- [ ] Write validation succeeds on new primary
- [ ] No data loss during failover
- [ ] API remains responsive after failover
- [ ] Current region updated correctly
- [ ] Health checks pass post-failover

---

## ⚡ Performance Testing

### Load Testing Script

```bash
#!/bin/bash
# load-test.sh - Performance and throughput testing

echo "=== Performance Load Test ==="

# API Throughput Test
echo "1. Backend API Throughput Test (100 requests)..."
time for i in {1..100}; do
  curl -s http://localhost:8000/api/devices?limit=10 >/dev/null &
done
wait

# RAG Query Performance Test
echo -e "\n2. RAG Query Latency Test..."
for i in {1..5}; do
  echo "Query $i:"
  TIME_START=$(date +%s%3N)
  curl -s -X POST http://localhost:8001/query \
    -H "Content-Type: application/json" \
    -d '{"question": "How many incidents occurred?"}' >/dev/null
  TIME_END=$(date +%s%3N)
  LATENCY=$((TIME_END - TIME_START))
  echo "  Latency: ${LATENCY}ms"
done

# Database Query Performance
echo -e "\n3. Database Query Performance..."
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "EXPLAIN ANALYZE SELECT * FROM device_telemetry WHERE site_id='WY-ALPHA' LIMIT 100;"

# Redis Cache Performance
echo -e "\n4. Redis Cache Hit Rate..."
docker exec -it tier0-redis redis-cli INFO stats | grep "keyspace_hits\|keyspace_misses"

echo "=== Performance Test Complete ==="
```

### Performance Benchmarks

| Operation | Target | Acceptable | Notes |
|-----------|--------|------------|-------|
| **Backend API** | <100ms | <500ms | /api/devices endpoint |
| **RAG Query** | <2000ms | <5000ms | With Cohere synthesis |
| **Failover Time** | <5s | <10s | Tier-0 requirement |
| **MQTT Throughput** | 200 msg/s | 100 msg/s | Device telemetry |
| **Cache Hit Rate** | >80% | >60% | Redis cache effectiveness |
| **DB Write Rate** | 1000/s | 500/s | PostgreSQL inserts |

---

## 🤖 AI/ML Testing

### RAG Answer Quality Validation

```bash
#!/bin/bash
# test-rag-quality.sh - Validate RAG answer accuracy

echo "=== RAG Answer Quality Test ==="

# Test 1: Factual BP Document Query
echo "1. Testing Factual Query..."
ANSWER=$(curl -s -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many Tier 1 and Tier 2 safety events did BP have in 2024?"}' \
  | jq -r '.answer')

echo "Answer: $ANSWER"

# Check for expected numbers (38 events in 2024 per BP report)
if echo "$ANSWER" | grep -q "38"; then
  echo "✓ Answer contains expected factual data"
else
  echo "✗ Answer missing expected data"
fi

# Test 2: Image Compliance Query
echo -e "\n2. Testing Image Analysis Query..."
RESPONSE=$(curl -s -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the average safety compliance score?"}')

AVG_COMPLIANCE=$(echo "$RESPONSE" | jq -r '.avg_compliance')
echo "Average Compliance: $AVG_COMPLIANCE%"

if [ "$AVG_COMPLIANCE" != "null" ]; then
  echo "✓ Image analysis returned valid data"
else
  echo "✗ Image analysis failed"
fi

# Test 3: Verify Cohere Synthesis
echo -e "\n3. Verifying Cohere Integration..."
SYNTHESIZED=$(echo "$RESPONSE" | jq -r '.synthesized')
echo "Answer Synthesized by Cohere: $SYNTHESIZED"

if [ "$SYNTHESIZED" = "true" ]; then
  echo "✓ Cohere successfully synthesized answer"
else
  echo "✗ Cohere synthesis not used (fallback mode)"
fi

echo "=== RAG Quality Test Complete ==="
```

### Image Processing Validation

```bash
# Verify image processing completed
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo --eval "
use tier0_images;
db.images.countDocuments({processed: true})
"

# Check safety compliance detection
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo --eval "
use tier0_images;
db.images.aggregate([
  {
    \$group: {
      _id: '\$device_type',
      avg_compliance: {\$avg: '\$safety_compliance.compliance_score'}
    }
  }
])
"
```

---

## 📊 Data Validation

### Database Integrity Tests

```sql
-- PostgreSQL Data Validation

-- Verify device telemetry ingestion
SELECT COUNT(*) as total_records FROM device_telemetry;
-- Expected: Thousands of records

-- Check for nulls in critical fields
SELECT COUNT(*) FROM device_telemetry
WHERE device_id IS NULL OR site_id IS NULL OR timestamp_utc IS NULL;
-- Expected: 0

-- Verify site distribution
SELECT site_id, COUNT(*) as device_count
FROM device_telemetry
GROUP BY site_id
ORDER BY device_count DESC;
-- Expected: All 10 sites represented

-- Check timestamp freshness
SELECT MAX(timestamp_utc) as most_recent,
       NOW() - MAX(timestamp_utc) as age
FROM device_telemetry;
-- Expected: <1 minute old

-- User session validation
SELECT connection_status, COUNT(*)
FROM user_sessions
GROUP BY connection_status;
-- Expected: Mix of active/idle/disconnected

-- Log data validation
SELECT status_code, COUNT(*) as count
FROM system_logs
GROUP BY status_code
ORDER BY status_code;
-- Expected: Various HTTP status codes
```

### MongoDB Data Validation

```javascript
// MongoDB Image Data Validation

use tier0_images;

// Count processed images
db.images.countDocuments({processed: true})
// Expected: ~150-200 images

// Verify embeddings exist
db.images.countDocuments({embedding: {$exists: true, $ne: null}})
// Expected: Match processed count

// Check safety compliance distribution
db.images.aggregate([
  {
    $group: {
      _id: "$safety_compliance.has_hard_hat",
      count: {$count: {}}
    }
  }
])

// Average compliance by device type
db.images.aggregate([
  {
    $group: {
      _id: "$device_type",
      avg_score: {$avg: "$safety_compliance.compliance_score"},
      count: {$count: {}}
    }
  }
])
```

---

## 🔐 Security Testing

### Basic Security Checks

```bash
#!/bin/bash
# security-checks.sh - Basic security validation

echo "=== Security Checks ==="

# Check for exposed credentials in logs
echo "1. Checking logs for exposed credentials..."
docker-compose logs 2>&1 | grep -i "password\|secret\|key" | grep -v "REDACTED" && \
  echo "⚠ WARNING: Potential credentials in logs" || \
  echo "✓ No exposed credentials found"

# Verify environment variable injection
echo -e "\n2. Verifying secure environment variable handling..."
docker exec -it tier0-backend printenv | grep -i "COHERE_API_KEY" >/dev/null && \
  echo "✓ Cohere API key loaded" || \
  echo "✗ Cohere API key missing"

# Check for default passwords (should be changed in production)
echo -e "\n3. Checking for default passwords..."
echo "⚠ REMINDER: Change all default passwords before production deployment"

# Port exposure check
echo -e "\n4. Checking exposed ports..."
docker-compose ps

echo "=== Security Checks Complete ==="
```

---

## 🧹 Cleanup After Testing

```bash
#!/bin/bash
# cleanup-test-data.sh - Remove test artifacts

echo "=== Cleaning Up Test Data ==="

# Remove test device telemetry
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "DELETE FROM device_telemetry WHERE device_id LIKE 'TEST-%' OR device_id LIKE 'FAILOVER-%';"

# Clear Redis cache
docker exec -it tier0-redis redis-cli FLUSHDB

echo "=== Cleanup Complete ==="
```

---

## 📋 Testing Checklist

### Pre-Deployment Testing

- [ ] All services start successfully
- [ ] Health checks pass for all services
- [ ] Device telemetry pipeline functional
- [ ] User session pipeline functional
- [ ] RAG queries returning synthesized answers
- [ ] Image processing completed
- [ ] Cohere integration working
- [ ] Database schemas initialized correctly
- [ ] Redis cache operational
- [ ] MQTT broker receiving messages
- [ ] RabbitMQ processing messages

### Failover Testing

- [ ] Failover completes in <5 seconds
- [ ] PostgreSQL replica promotes successfully
- [ ] Redis Sentinel failover works
- [ ] Write validation succeeds
- [ ] No data loss during failover
- [ ] API responsive post-failover
- [ ] Failover can be triggered multiple times

### Performance Testing

- [ ] Backend API latency <500ms
- [ ] RAG query latency <5s
- [ ] MQTT throughput ≥100 msg/s
- [ ] Cache hit rate ≥60%
- [ ] Database write rate ≥500/s

### Data Quality Testing

- [ ] Device telemetry data present
- [ ] User session data present
- [ ] System logs populated
- [ ] Images processed with embeddings
- [ ] No null values in critical fields
- [ ] All sites represented in data

### AI/ML Testing

- [ ] RAG returns synthesized answers
- [ ] Cohere integration confirmed in logs
- [ ] Image safety compliance detected
- [ ] BP document queries return factual data
- [ ] Fallback mode works if Cohere unavailable

---

## 📚 Related Documentation

- [API Reference](api-reference.md) - Detailed API documentation
- [Development Guide](development.md) - Development workflows
- [Troubleshooting](troubleshooting.md) - Common issues
- [Monitoring Guide](monitoring.md) - Metrics and observability

---

**Next**: Explore [Monitoring Guide](monitoring.md) for observability and metrics collection.
