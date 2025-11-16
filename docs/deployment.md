# Deployment Guide

This guide covers installation, configuration, and deployment of the Tier-0 Enterprise SRE System.

---

## 📋 Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Docker Desktop** | 20.10+ | 24.0+ |
| **Docker Compose** | 1.29+ | 2.20+ |
| **RAM** | 8 GB | 16 GB |
| **CPU Cores** | 4 | 8 |
| **Disk Space** | 20 GB | 50 GB |
| **OS** | macOS 11+, Windows 10+, Linux | macOS 13+, Windows 11, Ubuntu 22.04 |

### Required Ports

Ensure the following ports are available on your system:

| Port | Service | Required |
|------|---------|----------|
| 3000 | Frontend Dashboard | ✅ Yes |
| 8000 | Backend API | ✅ Yes |
| 8001 | RAG Service | ✅ Yes |
| 8002 | Failover Test Service | Optional |
| 8003 | Failover Orchestrator | ✅ Yes |
| 5432 | PostgreSQL Primary | ✅ Yes |
| 5433 | PostgreSQL Replica | ✅ Yes |
| 6379 | Redis Master | ✅ Yes |
| 6380 | Redis Replica | ✅ Yes |
| 26379 | Redis Sentinel | ✅ Yes |
| 27017 | MongoDB | ✅ Yes |
| 1883 | MQTT Broker | ✅ Yes |
| 5672 | RabbitMQ | ✅ Yes |
| 15672 | RabbitMQ Management | Optional |
| 9090 | Prometheus | Optional |
| 3001 | Grafana | Optional |

**Check ports**:
```bash
# macOS/Linux
lsof -i :3000,8000,5432,6379,27017

# Windows
netstat -an | findstr "3000 8000 5432"
```

---

## 🚀 Quick Installation

### 1. Clone Repository

```bash
git clone https://github.com/your-org/EntSystemsHackaton.git
cd EntSystemsHackaton
```

### 2. Configure Environment

```bash
# Create .env file from template
cp .env.example .env

# Edit .env and add your Cohere API key (optional but recommended)
nano .env  # or use your preferred editor
```

**`.env` Contents**:
```bash
# Cohere API (optional - system works without it)
COHERE_API_KEY=your_cohere_api_key_here

# Leave other variables as default for local deployment
```

**Get Cohere API Key**: https://cohere.com/ (free tier available)

### 3. Start All Services

```bash
# Build and start all 18+ containers
docker-compose up --build

# Or run in detached mode (background)
docker-compose up -d --build
```

**Expected output**:
```
✓ Network tier0-network created
✓ Volume tier0-postgres-data created
✓ Container tier0-redis started
✓ Container tier0-postgres started
✓ Container tier0-mongodb started
...
tier0-rag-service  | INFO: ✓ RAG service ready
tier0-backend      | INFO: Application startup complete
```

### 4. Wait for Initialization

Services need 3-5 minutes to fully initialize:
- PostgreSQL replica performs base backup (~60s)
- Redis Sentinel waits for master/replica (~30s)
- Image processor scans images (~5-10 minutes)
- RAG service loads BP documents (~30s)

**Monitor logs**:
```bash
docker-compose logs -f | grep "✓"
```

**Look for**:
- `✓ PostgreSQL connected`
- `✓ Redis connected`
- `✓ MongoDB connected`
- `✓ RAG service ready`

### 5. Verify Deployment

```bash
# Check all services are running
docker-compose ps

# All services should show "Up" status
# If any show "Restarting" or "Exit", check logs:
docker-compose logs [service-name]
```

### 6. Access the System

Open your browser to:
- **Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## 🔧 Detailed Configuration

### Environment Variables

**Backend API** (`backend/.env`):
```bash
# Cache
REDIS_HOST=redis
REDIS_PORT=6379

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=tier0_db
POSTGRES_USER=tier0user
POSTGRES_PASSWORD=tier0pass

# MongoDB
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_USER=tier0admin
MONGODB_PASSWORD=tier0mongo

# Message Brokers
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=tier0admin
RABBITMQ_PASS=tier0secure

MQTT_HOST=mqtt-broker
MQTT_PORT=1883

# AI
COHERE_API_KEY=${COHERE_API_KEY}
```

**Device Simulator**:
```bash
NUM_DEVICES=100000      # Total devices in registry
NUM_SITES=10            # Number of global sites
PUBLISH_INTERVAL=5      # Seconds between publish cycles
```

**User Simulator**:
```bash
NUM_USERS=1000          # Total active users
PUBLISH_INTERVAL=10     # Seconds between activity updates
```

**Data Cleanup**:
```bash
CLEANUP_INTERVAL_SECONDS=300   # Run cleanup every 5 minutes
RETENTION_HOURS=24             # Keep last 24 hours
MAX_RECORDS_PER_TABLE=100000   # Max 100K records per table
```

---

## 🗄️ Database Initialization

### PostgreSQL Schema

The schema is automatically initialized from `config/postgres/init.sql` on first startup.

**Tables created**:
- `sites` - 10 global site definitions
- `device_registry` - 100K device catalog
- `device_telemetry` - Real-time device metrics
- `user_sessions` - Active user tracking
- `system_logs` - Apache-style access logs
- `image_metadata` - Image processing metadata

**Replication setup**:
- Replication slot: `replication_slot`
- WAL level: `replica`
- Max WAL senders: 10

**Verify schema**:
```bash
docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c "\dt"
```

### MongoDB Collections

Collections are created automatically on first write.

**Databases**:
- `tier0_images` - Image metadata and embeddings

**Collections**:
- `images` - Image metadata, keywords, compliance scores, embeddings

**Verify collections**:
```bash
docker exec -it tier0-mongodb mongosh -u tier0admin -p tier0mongo --eval "use tier0_images; db.images.countDocuments()"
```

### Redis Configuration

- **Max Memory**: 2GB
- **Eviction Policy**: allkeys-lru
- **Persistence**: AOF (append-only file)
- **Replication**: Master → Replica streaming

**Verify Redis**:
```bash
docker exec -it tier0-redis redis-cli INFO replication
```

---

## 🌐 Network Configuration

### Docker Network

All services run on a single bridge network: `tier0-network`

**Service Discovery**: Services communicate via DNS names (e.g., `postgres`, `redis`)

**Verify network**:
```bash
docker network inspect tier0-network
```

### Port Mapping

Ports are mapped from container to host in `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - "8000:8000"  # host:container
```

**Change ports if conflicts exist**:
```yaml
ports:
  - "8080:8000"  # Use port 8080 instead of 8000
```

---

## 📦 Volume Management

### Persistent Volumes

Data is persisted in Docker volumes:

```yaml
volumes:
  postgres-data:         # PostgreSQL primary data
  postgres-replica-data: # PostgreSQL replica data
  mongodb-data:          # MongoDB data
  redis-data:            # Redis master data
  redis-replica-data:    # Redis replica data
  redis-sentinel-data:   # Sentinel config
  rabbitmq-data:         # RabbitMQ data
  prometheus-data:       # Metrics history
  grafana-data:          # Dashboards
  mqtt-data:             # MQTT persistence
  mqtt-logs:             # MQTT logs
```

**List volumes**:
```bash
docker volume ls | grep tier0
```

**Inspect volume**:
```bash
docker volume inspect entystemshackaton_postgres-data
```

**Backup volume**:
```bash
docker run --rm -v entystemshackaton_postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz /data
```

**Restore volume**:
```bash
docker run --rm -v entystemshackaton_postgres-data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-backup.tar.gz -C /
```

---

## 🧹 Cleanup & Reset

### Stop All Services

```bash
# Stop containers (keeps data)
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

### Remove Specific Service Data

```bash
# Remove PostgreSQL data only
docker volume rm entystemshackaton_postgres-data entystemshackaton_postgres-replica-data

# Remove MongoDB data only
docker volume rm entystemshackaton_mongodb-data

# Remove Redis data only
docker volume rm entystemshackaton_redis-data entystemshackaton_redis-replica-data
```

### Complete System Reset

```bash
# Remove everything
docker-compose down -v --remove-orphans

# Remove all images
docker-compose down --rmi all -v

# Rebuild from scratch
docker-compose up --build
```

---

## 🔄 Updates & Rebuilds

### Update Specific Service

```bash
# Rebuild and restart single service
docker-compose up -d --build backend

# Force rebuild without cache
docker-compose build --no-cache backend
docker-compose up -d backend
```

### Update All Services

```bash
# Pull latest code
git pull origin main

# Rebuild all services
docker-compose down
docker-compose up --build
```

---

## 🐛 Troubleshooting Deployment

### Services Won't Start

**Symptom**: `dependency failed to start: container X is unhealthy`

**Solutions**:
1. **Increase Docker memory**: Docker Desktop → Settings → Resources → Memory (increase to 8GB+)
2. **Wait longer**: Health checks have `start_period` - some services need 30-60s
3. **Check logs**: `docker-compose logs [service-name]`
4. **Restart Docker Desktop**

### Port Conflicts

**Symptom**: `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solutions**:
1. **Find conflicting process**:
   ```bash
   # macOS/Linux
   lsof -i :8000

   # Windows
   netstat -ano | findstr :8000
   ```

2. **Kill process or change port** in `docker-compose.yml`:
   ```yaml
   ports:
     - "8080:8000"  # Use different host port
   ```

### PostgreSQL Replica Not Syncing

**Symptom**: `no pg_hba.conf entry for replication connection`

**Solutions**:
1. **Verify pg_hba.conf mounted**:
   ```bash
   docker exec -it tier0-postgres cat /etc/postgresql/pg_hba.conf
   ```

2. **Check replication slot**:
   ```bash
   docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c "SELECT * FROM pg_replication_slots;"
   ```

3. **Rebuild primary**:
   ```bash
   docker-compose down -v
   docker volume rm entystemshackaton_postgres-data entystemshackaton_postgres-replica-data
   docker-compose up --build postgres postgres-replica
   ```

### Redis Sentinel Not Starting

**Symptom**: `Can't resolve instance hostname 'redis'`

**Solutions**:
1. **Ensure Redis master and replica are healthy first**:
   ```bash
   docker-compose ps | grep redis
   ```

2. **Check start script**:
   ```bash
   docker exec -it tier0-redis-sentinel cat /etc/redis/start-sentinel.sh
   ```

3. **Restart Sentinel**:
   ```bash
   docker-compose restart redis-sentinel
   ```

### No Data in Dashboard

**Symptom**: Dashboard shows 0 users, 0 devices

**Solutions**:
1. **Verify simulators running**:
   ```bash
   docker-compose ps | grep simulator
   ```

2. **Check MQTT messages**:
   ```bash
   mosquitto_sub -h localhost -p 1883 -t "og/field/#" -v
   ```

3. **Verify database has data**:
   ```bash
   docker exec -it tier0-postgres psql -U tier0user -d tier0_db -c "SELECT COUNT(*) FROM device_telemetry;"
   ```

4. **Check consumer logs**:
   ```bash
   docker-compose logs mqtt-consumer
   docker-compose logs rabbitmq-consumer
   ```

---

## 🔒 Production Deployment Considerations

### Security Hardening

See [Security Guide](security.md) for detailed production recommendations:
- Change all default passwords
- Enable TLS/SSL on all services
- Implement authentication on MQTT/APIs
- Use Docker secrets
- Network segmentation
- Regular security audits

### Scaling

**Horizontal Scaling**:
```yaml
# Scale simulators
docker-compose up -d --scale device-simulator=3

# Scale consumers
docker-compose up -d --scale mqtt-consumer=2
```

**Resource Limits**:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          memory: 1G
```

### High Availability

For production HA deployment:
1. Deploy PostgreSQL primary and replica in separate regions
2. Configure Redis Sentinel with 3+ sentinel nodes
3. Load balance backend APIs with Nginx/HAProxy
4. Use managed services (RDS, ElastiCache, DocumentDB)
5. Implement backup and disaster recovery

---

## 📊 Post-Deployment Verification

### Health Check Checklist

- [ ] All services show "Up" status: `docker-compose ps`
- [ ] Backend API responds: `curl http://localhost:8000/health`
- [ ] RAG service responds: `curl http://localhost:8001/health`
- [ ] Failover orchestrator responds: `curl http://localhost:8003/health`
- [ ] Dashboard loads: http://localhost:3000
- [ ] PostgreSQL replication active: Check replica lag
- [ ] Redis replication active: Check sentinel status
- [ ] MQTT messages flowing: Subscribe to topics
- [ ] RabbitMQ queue processing: Check queue depth
- [ ] Device telemetry appearing in database
- [ ] User sessions appearing in database
- [ ] Images processed in MongoDB
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards loading

### Smoke Tests

```bash
# Test device API
curl http://localhost:8000/api/devices | jq '.[:3]'

# Test user API
curl http://localhost:8000/api/users | jq '.active_users'

# Test RAG query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many safety incidents occurred?"}' | jq '.result.answer'

# Test failover
curl -X POST http://localhost:8003/failover/region2 | jq '.total_failover_time'
```

---

## 📚 Related Documentation

- [System Architecture](architecture.md) - Understand components
- [Development Guide](development.md) - Local development workflow
- [Testing Guide](testing.md) - Testing procedures
- [Troubleshooting](troubleshooting.md) - Common issues

---

**Next**: Explore [Development Guide](development.md) for local development workflows.
