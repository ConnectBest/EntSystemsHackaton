# Security Hardening Guide

Production security recommendations for the Tier-0 Enterprise SRE System.

---

## ⚠️ Current Security Posture

### Development Mode (Current)

**Status**: ⚠️ **NOT PRODUCTION-READY**

The system is currently configured for **demonstration and development only**:

❌ No authentication on APIs
❌ Default passwords in use
❌ No TLS/SSL encryption
❌ Open network exposure
❌ Secrets in environment variables
❌ No rate limiting
❌ Debug logging enabled

**⚠️ WARNING**: Do NOT deploy the current configuration to production without implementing security hardening.

---

## 🔒 Production Security Checklist

### Critical (Must-Have)

- [ ] Change all default passwords
- [ ] Enable TLS/SSL for all services
- [ ] Implement API authentication (JWT/OAuth)
- [ ] Use secrets management system
- [ ] Enable network segmentation
- [ ] Implement rate limiting
- [ ] Set up Web Application Firewall (WAF)
- [ ] Enable audit logging

### Important (Recommended)

- [ ] Implement RBAC (Role-Based Access Control)
- [ ] Set up intrusion detection (IDS/IPS)
- [ ] Enable database encryption at rest
- [ ] Implement API key rotation
- [ ] Set up vulnerability scanning
- [ ] Enable container security scanning
- [ ] Implement DDoS protection
- [ ] Set up SIEM integration

### Additional (Best Practice)

- [ ] Implement zero-trust architecture
- [ ] Set up honeypots
- [ ] Enable runtime application protection
- [ ] Implement security chaos engineering
- [ ] Set up bug bounty program

---

## 🔐 Authentication & Authorization

### JWT Authentication for Backend API

**Implementation**:

```python
# backend/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Load from secrets manager
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

# Protect endpoints
@app.get("/api/devices")
async def get_devices(username: str = Depends(verify_token)):
    # Only authenticated users can access
    return devices
```

**Login Endpoint**:
```python
@app.post("/auth/login")
async def login(username: str, password: str):
    # Verify credentials (use bcrypt for password hashing)
    if verify_credentials(username, password):
        access_token = create_access_token(data={"sub": username})
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

**Usage**:
```bash
# Get token
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -d "username=admin&password=secure_password" | jq -r '.access_token')

# Use token
curl http://localhost:8000/api/devices \
  -H "Authorization: Bearer $TOKEN"
```

### RBAC Implementation

**Roles**:
- **Admin**: Full access to all endpoints including failover
- **Operator**: Read/write device data, no failover access
- **Viewer**: Read-only access to dashboards and APIs

**Role Middleware**:
```python
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

def require_role(required_role: Role):
    def role_checker(username: str = Depends(verify_token)):
        user_role = get_user_role(username)  # Query from database
        if user_role not in [required_role, Role.ADMIN]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return username
    return role_checker

# Protect failover endpoint (admin only)
@app.post("/failover/{target_region}")
async def trigger_failover(
    target_region: str,
    username: str = Depends(require_role(Role.ADMIN))
):
    # Only admins can trigger failover
    return await perform_failover(target_region)
```

---

## 🔑 Secrets Management

### Using Docker Secrets

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  backend:
    image: tier0-backend
    secrets:
      - postgres_password
      - cohere_api_key
      - jwt_secret_key
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      COHERE_API_KEY_FILE: /run/secrets/cohere_api_key
      JWT_SECRET_KEY_FILE: /run/secrets/jwt_secret_key

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  cohere_api_key:
    file: ./secrets/cohere_api_key.txt
  jwt_secret_key:
    file: ./secrets/jwt_secret_key.txt
```

**Load Secrets in Application**:
```python
import os

def load_secret(secret_name):
    secret_file = os.getenv(f"{secret_name.upper()}_FILE")
    if secret_file and os.path.exists(secret_file):
        with open(secret_file, 'r') as f:
            return f.read().strip()
    return os.getenv(secret_name.upper())

POSTGRES_PASSWORD = load_secret("postgres_password")
COHERE_API_KEY = load_secret("cohere_api_key")
JWT_SECRET_KEY = load_secret("jwt_secret_key")
```

### Using HashiCorp Vault

```python
import hvac

# Initialize Vault client
vault_client = hvac.Client(url='https://vault.example.com')
vault_client.token = os.getenv('VAULT_TOKEN')

# Read secrets
postgres_creds = vault_client.secrets.kv.v2.read_secret_version(
    path='tier0/postgres'
)
POSTGRES_PASSWORD = postgres_creds['data']['data']['password']

cohere_key = vault_client.secrets.kv.v2.read_secret_version(
    path='tier0/cohere'
)
COHERE_API_KEY = cohere_key['data']['data']['api_key']
```

### AWS Secrets Manager

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-west-2')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Load secrets
postgres_secret = get_secret('tier0/postgres')
POSTGRES_PASSWORD = postgres_secret['password']

cohere_secret = get_secret('tier0/cohere')
COHERE_API_KEY = cohere_secret['api_key']
```

---

## 🔐 TLS/SSL Encryption

### Nginx SSL Termination

**docker-compose.yml**:
```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./certs/fullchain.pem:/etc/nginx/ssl/fullchain.pem
      - ./certs/privkey.pem:/etc/nginx/ssl/privkey.pem
```

**nginx.conf**:
```nginx
server {
    listen 443 ssl http2;
    server_name tier0.example.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Backend API
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name tier0.example.com;
    return 301 https://$server_name$request_uri;
}
```

### PostgreSQL SSL

**postgresql.conf**:
```
ssl = on
ssl_cert_file = '/var/lib/postgresql/server.crt'
ssl_key_file = '/var/lib/postgresql/server.key'
ssl_ca_file = '/var/lib/postgresql/root.crt'
```

**Connection String**:
```python
DATABASE_URL = f"postgresql://user:pass@host:5432/db?sslmode=require"
```

### Redis TLS

**redis.conf**:
```
tls-port 6380
port 0  # Disable non-TLS
tls-cert-file /etc/redis/redis.crt
tls-key-file /etc/redis/redis.key
tls-ca-cert-file /etc/redis/ca.crt
```

**Connection**:
```python
import redis
r = redis.Redis(
    host='redis',
    port=6380,
    ssl=True,
    ssl_certfile='/path/to/client.crt',
    ssl_keyfile='/path/to/client.key',
    ssl_ca_certs='/path/to/ca.crt'
)
```

---

## 🛡️ Network Security

### Network Segmentation

```yaml
# docker-compose.yml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
  database:
    driver: bridge
    internal: true  # No external access

services:
  frontend:
    networks:
      - frontend

  backend:
    networks:
      - frontend
      - backend

  postgres:
    networks:
      - database
    # Not exposed to frontend network
```

### Firewall Rules (iptables)

```bash
#!/bin/bash
# firewall-rules.sh - Configure host firewall

# Allow SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Allow Prometheus/Grafana (internal only)
iptables -A INPUT -p tcp --dport 9090 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 3001 -s 10.0.0.0/8 -j ACCEPT

# Deny all other incoming
iptables -A INPUT -j DROP

# Save rules
iptables-save > /etc/iptables/rules.v4
```

### VPC Configuration (AWS Example)

```
VPC: 10.0.0.0/16

Subnets:
├─ Public Subnet (10.0.1.0/24)
│  ├─ Load Balancer
│  └─ NAT Gateway
│
├─ Private Subnet - App (10.0.2.0/24)
│  ├─ Backend API
│  ├─ RAG Service
│  └─ Failover Orchestrator
│
└─ Private Subnet - Data (10.0.3.0/24)
   ├─ PostgreSQL
   ├─ Redis
   └─ MongoDB

Security Groups:
├─ Load Balancer SG: 0.0.0.0/0:443 → LB
├─ App SG: LB → App:8000, App → Data:5432/6379/27017
└─ Data SG: App → Data:5432/6379/27017 (no inbound from internet)
```

---

## 🔒 Database Security

### PostgreSQL Hardening

**Change Default Passwords**:
```sql
-- Create strong password
ALTER USER tier0user WITH PASSWORD 'StrongP@ssw0rd!2025';

-- Remove default postgres user remote access
ALTER USER postgres WITH PASSWORD NULL;
```

**Restrict Access** (`pg_hba.conf`):
```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
host    tier0_db        tier0user       10.0.0.0/8             scram-sha-256
host    replication     replication_user 10.0.0.0/8            scram-sha-256
# Deny all others
host    all             all             0.0.0.0/0              reject
```

**Enable Audit Logging**:
```sql
-- Install pgaudit extension
CREATE EXTENSION pgaudit;

-- Audit all DDL and writes
ALTER SYSTEM SET pgaudit.log = 'ddl, write';

-- Reload config
SELECT pg_reload_conf();
```

**Encryption at Rest**:
```bash
# Initialize PostgreSQL with encryption
initdb --pgdata=/var/lib/postgresql/data \
       --auth=scram-sha-256 \
       --pwfile=/run/secrets/postgres_password \
       --waldir=/var/lib/postgresql/wal \
       --data-checksums
```

### MongoDB Hardening

**Enable Authentication**:
```javascript
// Create admin user
use admin
db.createUser({
  user: "admin",
  pwd: "StrongP@ssw0rd!2025",
  roles: [ { role: "userAdminAnyDatabase", db: "admin" } ]
})

// Create application user
use tier0_images
db.createUser({
  user: "tier0app",
  pwd: "AppP@ssw0rd!2025",
  roles: [ { role: "readWrite", db: "tier0_images" } ]
})
```

**mongod.conf**:
```yaml
security:
  authorization: enabled

net:
  bindIp: 10.0.0.5  # Internal IP only
  tls:
    mode: requireTLS
    certificateKeyFile: /etc/mongodb/mongodb.pem
    CAFile: /etc/mongodb/ca.pem
```

### Redis Hardening

**redis.conf**:
```
# Require password
requirepass StrongP@ssw0rd!2025

# Bind to internal IP only
bind 10.0.0.4

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""
rename-command CONFIG "CONFIG_SECRET_NAME"

# Enable AOF for persistence
appendonly yes
appendfilename "appendonly.aof"
```

---

## 🚦 Rate Limiting

### API Rate Limiting

**Using FastAPI Limiter**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply rate limit
@app.get("/api/devices")
@limiter.limit("100/minute")
async def get_devices(request: Request):
    return devices

# Stricter limit for critical endpoints
@app.post("/failover/{target_region}")
@limiter.limit("10/hour")
async def trigger_failover(request: Request, target_region: str):
    return await perform_failover(target_region)
```

### Nginx Rate Limiting

```nginx
http {
    # Define rate limit zone
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;
    limit_req_zone $binary_remote_addr zone=query_limit:10m rate=20r/m;

    server {
        # Apply to API endpoints
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://backend:8000;
        }

        # Stricter limit for RAG queries
        location /api/query {
            limit_req zone=query_limit burst=5 nodelay;
            proxy_pass http://backend:8000;
        }
    }
}
```

---

## 🔍 Security Monitoring

### Audit Logging

**Application Audit Log**:
```python
import logging
import json
from datetime import datetime

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
handler = logging.FileHandler("/var/log/tier0/audit.log")
handler.setFormatter(logging.Formatter('%(message)s'))
audit_logger.addHandler(handler)

def log_audit_event(event_type: str, user: str, resource: str, action: str, result: str):
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "user": user,
        "resource": resource,
        "action": action,
        "result": result,
        "ip_address": request.client.host
    }
    audit_logger.info(json.dumps(audit_entry))

# Usage
@app.post("/failover/{target_region}")
async def trigger_failover(target_region: str, username: str = Depends(verify_token)):
    result = await perform_failover(target_region)
    log_audit_event(
        event_type="failover",
        user=username,
        resource=f"region/{target_region}",
        action="trigger_failover",
        result="success" if result['success'] else "failure"
    )
    return result
```

### Intrusion Detection

**OSSEC Integration**:
```xml
<!-- /var/ossec/etc/ossec.conf -->
<ossec_config>
  <localfile>
    <log_format>json</log_format>
    <location>/var/log/tier0/audit.log</location>
  </localfile>

  <rule id="100001" level="10">
    <if_sid>100000</if_sid>
    <match>failover</match>
    <description>Failover triggered</description>
  </rule>

  <rule id="100002" level="12">
    <if_sid>100000</if_sid>
    <match>result.*failure</match>
    <description>Failover failed</description>
  </rule>
</ossec_config>
```

### Security Scanning

**Trivy Container Scanning**:
```bash
#!/bin/bash
# scan-containers.sh - Scan all containers for vulnerabilities

for service in backend rag-service failover-orchestrator; do
  echo "Scanning $service..."
  trivy image --severity HIGH,CRITICAL tier0-$service:latest
done
```

**OWASP ZAP API Scanning**:
```bash
# Scan Backend API
docker run -t owasp/zap2docker-stable zap-api-scan.py \
  -t http://backend:8000/docs \
  -f openapi \
  -r zap-report.html
```

---

## 🛡️ DDoS Protection

### CloudFlare Integration

```
DNS Configuration:
tier0.example.com → CloudFlare Proxy (Orange Cloud) → Load Balancer

CloudFlare Settings:
├─ Security Level: High
├─ Challenge Passage: 30 minutes
├─ Browser Integrity Check: ON
├─ Rate Limiting: 100 req/min per IP
└─ WAF: OWASP Core Ruleset
```

### Fail2Ban

```ini
# /etc/fail2ban/jail.local
[tier0-api]
enabled = true
port = 8000
filter = tier0-api
logpath = /var/log/tier0/backend.log
maxretry = 10
findtime = 60
bantime = 3600
action = iptables-multiport[name=tier0, port="8000,8001,8003"]

# /etc/fail2ban/filter.d/tier0-api.conf
[Definition]
failregex = ^.*"status_code": 40[13].*"ip_address": "<HOST>"
ignoreregex =
```

---

## 🔐 Container Security

### Docker Security Best Practices

**Run as Non-Root User**:
```dockerfile
# Dockerfile
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 tier0user

# Switch to non-root user
USER tier0user

# Copy and run application
COPY --chown=tier0user:tier0user . /app
WORKDIR /app
CMD ["python", "main.py"]
```

**Read-Only Root Filesystem**:
```yaml
# docker-compose.yml
services:
  backend:
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
```

**Drop Capabilities**:
```yaml
services:
  backend:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if needed
```

**Security Scanning in CI/CD**:
```yaml
# .github/workflows/security-scan.yml
name: Security Scan

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'tier0-backend:latest'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

---

## 📋 Security Compliance

### GDPR Compliance

- [ ] Data encryption at rest and in transit
- [ ] Right to be forgotten (data deletion API)
- [ ] Data portability (export API)
- [ ] Consent management
- [ ] Audit logging
- [ ] Data breach notification procedures

### SOC 2 Compliance

- [ ] Access controls (RBAC)
- [ ] Audit logging
- [ ] Change management
- [ ] Backup and recovery
- [ ] Incident response plan
- [ ] Vendor management

### HIPAA Compliance (if handling health data)

- [ ] PHI encryption
- [ ] Access controls
- [ ] Audit trails
- [ ] Business associate agreements
- [ ] Breach notification
- [ ] Security risk assessments

---

## 🧪 Security Testing

### Penetration Testing Checklist

- [ ] SQL Injection testing
- [ ] XSS (Cross-Site Scripting) testing
- [ ] CSRF (Cross-Site Request Forgery) testing
- [ ] Authentication bypass attempts
- [ ] Authorization escalation attempts
- [ ] API fuzzing
- [ ] Container escape attempts
- [ ] Network segmentation validation

### Security Audit Script

```bash
#!/bin/bash
# security-audit.sh - Automated security audit

echo "=== Tier-0 Security Audit ==="

# Check for default passwords
echo "1. Checking for default passwords..."
docker-compose config | grep -i "tier0" && \
  echo "⚠ WARNING: Default passwords detected"

# Check TLS configuration
echo "2. Checking TLS/SSL..."
openssl s_client -connect localhost:443 < /dev/null 2>/dev/null | \
  grep "Cipher" && echo "✓ TLS enabled" || echo "✗ TLS not configured"

# Check for exposed secrets
echo "3. Checking for exposed secrets..."
docker-compose config | grep -iE "password|secret|key" | grep -v "FILE" && \
  echo "⚠ WARNING: Secrets in environment variables"

# Check container security
echo "4. Checking container security..."
docker inspect tier0-backend | jq '.[0].HostConfig.ReadonlyRootfs' && \
  echo "✓ Read-only root filesystem" || echo "⚠ Root filesystem is writable"

# Check network exposure
echo "5. Checking network exposure..."
docker-compose ps | grep "0.0.0.0" && \
  echo "⚠ WARNING: Services exposed to 0.0.0.0"

echo "=== Audit Complete ==="
```

---

## 📚 Related Documentation

- [Deployment Guide](deployment.md) - Secure deployment procedures
- [Monitoring Guide](monitoring.md) - Security monitoring
- [Troubleshooting](troubleshooting.md) - Security issue resolution

---

## 🔗 Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

---

**⚠️ IMPORTANT**: Security is an ongoing process. Regularly update dependencies, scan for vulnerabilities, and stay informed about emerging threats.
