# Troubleshooting Guide

Common issues, solutions, and debugging procedures for the Tier-0 Enterprise SRE System.

---

## 🔍 Quick Diagnostics

### System Health Check

```bash
#!/bin/bash
# quick-diagnostic.sh - Run comprehensive system diagnostics

echo "=== Tier-0 System Diagnostics ==="

# 1. Check all containers are running
echo "1. Container Status:"
docker-compose ps

# 2. Check service health
echo -e "\n2. Service Health:"
curl -s http://localhost:8000/health | jq '.status' 2>/dev/null || echo "Backend: FAIL"
curl -s http://localhost:8001/health | jq '.status' 2>/dev/null || echo "RAG: FAIL"
curl -s http://localhost:8003/health | jq '.status' 2>/dev/null || echo "Failover: FAIL"

# 3. Check database connections
echo -e "\n3. Database Connectivity:"
docker exec -it tier0-postgres pg_isready -U tier0user >/dev/null 2>&1 && \
  echo "PostgreSQL: ✓" || echo "PostgreSQL: ✗"
docker exec -it tier0-redis redis-cli ping 2>&1 | grep -q PONG && \
  echo "Redis: ✓" || echo "Redis: ✗"
docker exec -it tier0-mongodb mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1 && \
  echo "MongoDB: ✓" || echo "MongoDB: ✗"

# 4. Check data flow
echo -e "\n4. Data Flow Validation:"
DEVICE_COUNT=$(docker exec -it tier0-postgres psql -U tier0user -d tier0_db -t -c \
  "SELECT COUNT(*) FROM device_telemetry;" 2>/dev/null | tr -d ' ')
echo "Device telemetry records: $DEVICE_COUNT"

USER_COUNT=$(docker exec -it tier0-postgres psql -U tier0user -d tier0_db -t -c \
  "SELECT COUNT(*) FROM user_sessions WHERE connection_status='active';" 2>/dev/null | tr -d ' ')
echo "Active users: $USER_COUNT"

# 5. Check simulators
echo -e "\n5. Simulator Status:"
docker-compose ps | grep "simulator"

echo -e "\n=== Diagnostics Complete ==="
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Services Not Starting

#### Symptom
```
dependency failed to start: container tier0-postgres is unhealthy
```

#### Root Causes
1. **Insufficient Docker memory**
2. **Port conflicts**
3. **Slow health checks**
4. **Volume corruption**

#### Solutions

**1. Increase Docker Memory**:
```bash
# Docker Desktop → Settings → Resources
# Set Memory to 8GB minimum (16GB recommended)
```

**2. Check for Port Conflicts**:
```bash
# macOS/Linux
lsof -i :8000,5432,6379,27017

# Windows
netstat -ano | findstr "8000 5432 6379 27017"

# Kill conflicting process or change port in docker-compose.yml
```

**3. Check Service Logs**:
```bash
# View logs for failing service
docker-compose logs postgres
docker-compose logs redis
docker-compose logs mongodb

# Look for specific errors
docker-compose logs | grep -i error
```

**4. Remove Corrupted Volumes**:
```bash
# Stop all services
docker-compose down

# Remove volumes
docker-compose down -v

# Rebuild
docker-compose up --build
```

---

### Issue 2: PostgreSQL Replication Not Working

#### Symptom
```
no pg_hba.conf entry for replication connection
ERROR: could not connect to primary
```

#### Diagnosis
```bash
# Check replication status
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT client_addr, state, sync_state FROM pg_stat_replication;"

# Expected: 1 row showing replica connection

# Check replica status
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "SELECT pg_is_in_recovery();"

# Expected: t (true)

# Check replication slot
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT * FROM pg_replication_slots;"

# Expected: replication_slot exists
```

#### Solutions

**1. Verify pg_hba.conf is Mounted**:
```bash
docker exec -it tier0-postgres cat /etc/postgresql/pg_hba.conf

# Should contain:
# host replication replication_user all md5
```

**2. Recreate Replication**:
```bash
# Stop services
docker-compose stop postgres postgres-replica

# Remove replica volume
docker volume rm entystemshackaton_postgres-replica-data

# Start primary
docker-compose up -d postgres

# Wait for primary to be healthy (30 seconds)
sleep 30

# Start replica
docker-compose up -d postgres-replica
```

**3. Check Network Connectivity**:
```bash
# From replica container
docker exec -it tier0-postgres-replica ping postgres

# Should respond with ICMP replies
```

---

### Issue 3: Redis Sentinel Not Starting

#### Symptom
```
Can't resolve instance hostname 'redis'
Sentinel configuration error
```

#### Diagnosis
```bash
# Check Redis master and replica
docker exec -it tier0-redis redis-cli INFO replication

# Check Sentinel logs
docker-compose logs redis-sentinel

# Check Sentinel status
docker exec -it tier0-redis-sentinel redis-cli -p 26379 \
  SENTINEL masters
```

#### Solutions

**1. Ensure Redis Services are Healthy First**:
```bash
# Verify Redis master
docker exec -it tier0-redis redis-cli ping
# Expected: PONG

# Verify Redis replica
docker exec -it tier0-redis-replica redis-cli ping
# Expected: PONG

# Check replication
docker exec -it tier0-redis redis-cli INFO replication
# Expected: connected_slaves:1
```

**2. Restart Sentinel**:
```bash
docker-compose restart redis-sentinel

# Check startup script
docker exec -it tier0-redis-sentinel cat /etc/redis/start-sentinel.sh
```

**3. Manual Sentinel Configuration**:
```bash
# Get Redis master IP
REDIS_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' tier0-redis)

# Update Sentinel config
docker exec -it tier0-redis-sentinel redis-cli -p 26379 \
  SENTINEL monitor tier0master $REDIS_IP 6379 1
```

---

### Issue 4: No Data in Dashboard

#### Symptom
Dashboard shows 0 users, 0 devices, empty graphs

#### Diagnosis
```bash
# 1. Check simulators are running
docker-compose ps | grep simulator

# 2. Check MQTT messages
mosquitto_sub -h localhost -p 1883 -t "og/field/#" -v
# Should see messages every 5 seconds

# 3. Check PostgreSQL data
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT COUNT(*) FROM device_telemetry;"

# 4. Check consumer logs
docker-compose logs mqtt-consumer
docker-compose logs rabbitmq-consumer
```

#### Solutions

**1. Restart Simulators**:
```bash
docker-compose restart device-simulator user-simulator

# Wait 30 seconds for data to flow
sleep 30

# Verify data
curl http://localhost:8000/api/devices | jq length
```

**2. Check MQTT Broker**:
```bash
# Verify broker is running
docker-compose ps mqtt-broker

# Test publish
mosquitto_pub -h localhost -p 1883 \
  -t "test/topic" -m "test message"

# Test subscribe
mosquitto_sub -h localhost -p 1883 -t "test/topic" -v
```

**3. Check Consumer Processing**:
```bash
# MQTT consumer logs
docker-compose logs mqtt-consumer | tail -50

# Look for:
# "Inserted device telemetry"
# "Connected to PostgreSQL"
# "Subscribed to MQTT"

# Restart consumer if stuck
docker-compose restart mqtt-consumer
```

**4. Manual Data Insertion Test**:
```bash
# Insert test record
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "INSERT INTO device_telemetry (device_id, device_type, site_id, timestamp_utc, metrics, status)
   VALUES ('TEST-001', 'turbine', 'TEST', NOW(), '{\"rpm\": 3500}', '{\"state\": \"OK\"}');"

# Verify via API
curl "http://localhost:8000/api/devices?device_id=TEST-001"
```

---

### Issue 5: RAG/Cohere Errors

#### Symptom
```
WARNING: Cohere synthesis failed, falling back to keyword-based response
```

#### Diagnosis
```bash
# Check RAG service logs
docker-compose logs rag-service | tail -50

# Check Cohere API key
docker exec -it tier0-rag-service printenv COHERE_API_KEY

# Test Cohere connection
docker exec -it tier0-rag-service python3 -c "
import cohere
import os
client = cohere.Client(os.getenv('COHERE_API_KEY'))
print('Cohere connected successfully')
"
```

#### Solutions

**1. Verify API Key is Set**:
```bash
# Check .env file
cat .env | grep COHERE_API_KEY

# Should show: COHERE_API_KEY=your_key_here

# If missing, add it
echo "COHERE_API_KEY=your_key_here" >> .env

# Rebuild RAG service
docker-compose up -d --build rag-service
```

**2. Check Token Limits**:
```bash
# View recent RAG errors
docker-compose logs rag-service | grep "token"

# If "too many tokens" error, snippet truncation is working
# Verify MAX_CHARS_PER_SNIPPET in rag_server.py
docker exec -it tier0-rag-service grep "MAX_CHARS_PER_SNIPPET" /app/rag_server.py
```

**3. Rebuild Without Cache**:
```bash
docker-compose build --no-cache rag-service
docker-compose up -d rag-service

# Monitor logs
docker-compose logs -f rag-service
```

**4. Test RAG Query**:
```bash
# Simple query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test query"}' | jq

# Check if synthesized is true
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many incidents occurred?"}' | jq '.synthesized'
```

---

### Issue 6: Failover Not Working

#### Symptom
```
Failover failed: replica not healthy
Failover took >5 seconds
```

#### Diagnosis
```bash
# Check failover status
curl http://localhost:8003/status | jq

# Check PostgreSQL replication lag
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT client_addr, state, sync_state, replay_lag
   FROM pg_stat_replication;"

# Check replica health
docker exec -it tier0-postgres-replica pg_isready -U tier0user
```

#### Solutions

**1. Verify Replication is Healthy**:
```bash
# Check replication lag
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) AS lag_seconds;"

# Should be <1 second
```

**2. Test Failover Step by Step**:
```bash
# Step 1: Health check
curl http://localhost:8003/status | jq '.postgres_replica_healthy'

# Step 2: Manual promotion test
docker exec -it tier0-postgres-replica pg_ctl promote

# Step 3: Verify promotion
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "SELECT pg_is_in_recovery();"
# Should return 'f' (false) if promoted

# Step 4: Write test
docker exec -it tier0-postgres-replica psql -U tier0user -d tier0_db -c \
  "INSERT INTO device_telemetry (device_id, device_type, site_id, timestamp_utc, metrics, status)
   VALUES ('FAILOVER-TEST', 'turbine', 'TEST', NOW(), '{}', '{}');"
```

**3. Check Failover Orchestrator Logs**:
```bash
docker-compose logs failover-orchestrator | grep -i error

# Restart if needed
docker-compose restart failover-orchestrator
```

---

### Issue 7: High Memory Usage

#### Symptom
```
Docker Desktop running slow
Services being OOM killed
```

#### Diagnosis
```bash
# Check container memory usage
docker stats --no-stream

# Check Docker Desktop memory allocation
# Docker Desktop → Settings → Resources → Memory

# Check PostgreSQL memory
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "SELECT pg_size_pretty(pg_database_size('tier0_db'));"
```

#### Solutions

**1. Increase Docker Memory**:
```
Docker Desktop → Settings → Resources → Memory → 16GB
```

**2. Enable Data Cleanup Service**:
```bash
# Verify data-cleanup service is running
docker-compose ps data-cleanup

# Check cleanup logs
docker-compose logs data-cleanup

# Manual cleanup
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c \
  "DELETE FROM device_telemetry WHERE timestamp_utc < NOW() - INTERVAL '24 hours';"
```

**3. Clear Redis Cache**:
```bash
docker exec -it tier0-redis redis-cli FLUSHDB
```

**4. Prune Docker System**:
```bash
# Remove unused containers, networks, images
docker system prune -a

# Remove unused volumes (WARNING: deletes data)
docker volume prune
```

---

### Issue 8: Image Processing Not Running

#### Symptom
```
No images in MongoDB
avg_compliance is null
```

#### Diagnosis
```bash
# Check image processor status
docker-compose ps image-processor

# Check logs
docker-compose logs image-processor

# Check MongoDB data
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo --eval "
use tier0_images;
db.images.countDocuments({processed: true})
"
```

#### Solutions

**1. Verify Images Directory is Mounted**:
```bash
# Check volume mount
docker exec -it tier0-image-processor ls -la /app/images

# Should show:
# TurbineImages/
# ThermalEngines/
# ElectricalRotors/
# OilAndGas/
```

**2. Restart Image Processor**:
```bash
docker-compose restart image-processor

# Monitor processing
docker-compose logs -f image-processor

# Look for: "Processing image: ..."
```

**3. Check Cohere Embeddings**:
```bash
# Verify Cohere API key
docker exec -it tier0-image-processor printenv COHERE_API_KEY

# Check for embedding errors
docker-compose logs image-processor | grep -i cohere
```

---

### Issue 9: Frontend Not Loading

#### Symptom
```
localhost:3000 not accessible
Dashboard shows blank page
```

#### Diagnosis
```bash
# Check frontend container
docker-compose ps frontend

# Check Nginx logs
docker-compose logs frontend

# Test direct access
curl http://localhost:3000
```

#### Solutions

**1. Verify Port Mapping**:
```bash
# Check docker-compose.yml
grep -A 5 "frontend:" docker-compose.yml | grep ports

# Should show: "3000:80"
```

**2. Restart Frontend**:
```bash
docker-compose restart frontend

# Wait for startup
sleep 5

# Test
curl http://localhost:3000
```

**3. Check Browser Console**:
```
Open browser console (F12)
Look for JavaScript errors or network errors
```

**4. Rebuild Frontend**:
```bash
docker-compose up -d --build frontend
```

---

### Issue 10: MQTT Messages Not Being Received

#### Symptom
```
No device telemetry in database
mosquitto_sub shows no messages
```

#### Diagnosis
```bash
# Check MQTT broker status
docker-compose ps mqtt-broker

# Check broker logs
docker-compose logs mqtt-broker

# Test subscription
mosquitto_sub -h localhost -p 1883 -t "#" -v

# Check simulator logs
docker-compose logs device-simulator
```

#### Solutions

**1. Restart MQTT Broker**:
```bash
docker-compose restart mqtt-broker

# Wait for startup
sleep 5

# Test publish/subscribe
mosquitto_pub -h localhost -p 1883 -t "test/topic" -m "test"
mosquitto_sub -h localhost -p 1883 -t "test/topic" -v
```

**2. Verify Device Simulator is Publishing**:
```bash
# Check simulator logs for "Published message"
docker-compose logs device-simulator | grep "Published"

# Restart simulator
docker-compose restart device-simulator
```

**3. Check MQTT Consumer**:
```bash
# Verify consumer is subscribed
docker-compose logs mqtt-consumer | grep "Subscribed"

# Restart consumer
docker-compose restart mqtt-consumer
```

---

## 🛠️ Debugging Tools

### Container Shell Access

```bash
# Backend
docker exec -it tier0-backend /bin/bash

# RAG Service
docker exec -it tier0-rag-service /bin/bash

# Inside container, useful commands:
ls -la
cat main.py
printenv
ps aux
netstat -tulpn
```

### Database Queries

**PostgreSQL**:
```sql
-- Connection info
SELECT * FROM pg_stat_activity;

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- Recent errors
SELECT * FROM pg_stat_database WHERE datname = 'tier0_db';
```

**MongoDB**:
```javascript
// Connection info
db.serverStatus()

// Collection stats
db.images.stats()

// Recent operations
db.currentOp()
```

**Redis**:
```bash
# Memory info
docker exec -it tier0-redis redis-cli INFO memory

# Key count
docker exec -it tier0-redis redis-cli DBSIZE

# Slow log
docker exec -it tier0-redis redis-cli SLOWLOG GET 10
```

### Network Debugging

```bash
# Check DNS resolution
docker exec -it tier0-backend nslookup postgres

# Check network connectivity
docker exec -it tier0-backend ping postgres

# Check open ports
docker exec -it tier0-backend netstat -tulpn
```

---

## 📊 Performance Debugging

### High CPU Usage

```bash
# Check which container is using CPU
docker stats --no-stream

# Check processes inside container
docker exec -it tier0-backend top

# Profile Python code
docker exec -it tier0-backend python -m cProfile -o profile.stats main.py
```

### Slow Database Queries

```sql
-- Enable query logging
ALTER DATABASE tier0_db SET log_min_duration_statement = 100;

-- View slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Explain query
EXPLAIN ANALYZE SELECT * FROM device_telemetry WHERE site_id='WY-ALPHA';
```

### High Latency

```bash
# Measure API latency
time curl http://localhost:8000/api/devices

# Check Redis latency
docker exec -it tier0-redis redis-cli --latency

# Check PostgreSQL latency
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c "\timing on" -c "SELECT COUNT(*) FROM device_telemetry;"
```

---

## 🧹 Recovery Procedures

### Complete System Reset

```bash
#!/bin/bash
# reset-system.sh - Complete clean slate

echo "WARNING: This will delete all data!"
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Aborted"
  exit 1
fi

# Stop all services
docker-compose down

# Remove all volumes
docker-compose down -v

# Remove all images
docker-compose down --rmi all -v

# Remove Docker system artifacts
docker system prune -a -f

# Rebuild from scratch
docker-compose up --build

echo "System reset complete"
```

### Restore from Backup

```bash
# Restore PostgreSQL
docker run --rm -v entystemshackaton_postgres-data:/data \
  -v $(pwd):/backup alpine \
  tar xzf /backup/postgres-backup.tar.gz -C /

# Restart PostgreSQL
docker-compose restart postgres
```

---

## 📚 Related Documentation

- [Deployment Guide](deployment.md) - Installation procedures
- [Development Guide](development.md) - Development workflows
- [Monitoring Guide](monitoring.md) - Metrics and alerts
- [API Reference](api-reference.md) - API documentation

---

## 🆘 Getting Help

### Logs to Collect

```bash
# Collect all logs
docker-compose logs > system-logs.txt

# Service status
docker-compose ps > service-status.txt

# Container stats
docker stats --no-stream > container-stats.txt

# System info
docker info > docker-info.txt
```

### Useful Commands Summary

```bash
# Service health
docker-compose ps
curl http://localhost:8000/health

# View logs
docker-compose logs -f [service]

# Restart service
docker-compose restart [service]

# Rebuild service
docker-compose up -d --build [service]

# Complete restart
docker-compose down && docker-compose up --build

# Database access
docker exec -it tier0-postgres psql -U tier0user -d tier0_db
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo
docker exec -it tier0-redis redis-cli
```

---

**Still Having Issues?** Check the [Development Guide](development.md) for additional debugging techniques.
