#\!/bin/sh

echo "Waiting for Redis master to be available..."

# Wait for Redis master to be responsive
until redis-cli -h redis -p 6379 ping > /dev/null 2>&1; do
  echo "Redis master not ready yet, waiting..."
  sleep 2
done

echo "Redis master is available, getting IP address..."

# Get the actual IP address of redis master
REDIS_IP=$(getent hosts redis | awk '{ print $1 }')
echo "Redis master IP: $REDIS_IP"

# Create sentinel config with IP address instead of hostname
cat > /tmp/sentinel.conf <<EEOF
# Redis Sentinel Configuration for Tier-0 Failover

# Monitor the master using IP address
sentinel monitor tier0master $REDIS_IP 6379 1

# Master down after 5 seconds of no response
sentinel down-after-milliseconds tier0master 5000

# Failover timeout
sentinel failover-timeout tier0master 10000

# Allow 1 replica to sync during failover
sentinel parallel-syncs tier0master 1

# Bind to all interfaces
bind 0.0.0.0

# Protected mode off for Docker networking
protected-mode no

# Sentinel runs on port 26379
port 26379
EEOF

echo "Starting Sentinel with config:"
cat /tmp/sentinel.conf

# Start Sentinel
exec redis-sentinel /tmp/sentinel.conf
