# Tier-0 Enterprise SRE System - Documentation

## 📚 Documentation Hub

Welcome to the comprehensive documentation for the Tier-0 Enterprise Reliability Engineering System.

---

## 🗺️ Documentation Structure

### Getting Started
- **[Quick Start Guide](../README.md#-quick-start)** - Get the system running in 5 minutes
- **[Deployment Guide](deployment.md)** - Detailed installation and configuration
- **[Assignment Overview](assignment.md)** - Academic context and deliverables

### Architecture & Design
- **[System Architecture](architecture.md)** - Complete architectural overview with diagrams
- **[Data Pipelines](data-pipelines.md)** - Detailed flow diagrams for all data pipelines
- **[Multi-Region Failover](failover.md)** - HA/DR architecture and testing

### Development
- **[Development Guide](development.md)** - Common commands, workflows, debugging
- **[API Reference](api-reference.md)** - Complete API documentation
- **[Testing Guide](testing.md)** - Testing strategies and validation procedures

### Operations
- **[Monitoring & Observability](monitoring.md)** - Prometheus, Grafana, metrics
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- **[Security Hardening](security.md)** - Production security checklist

---

## 🎯 Quick Links

### Core Features
- [100K Device Simulation](data-pipelines.md#1-iot-device-telemetry-pipeline)
- [AI-Enhanced RAG Service](architecture.md#ai-services)
- [Multi-Region Failover](failover.md)
- [Safety Compliance Analysis](data-pipelines.md#4-image-processing-pipeline)

### Key Services
- **Backend API**: http://localhost:8000/docs
- **RAG Service**: http://localhost:8001/health
- **Failover Orchestrator**: http://localhost:8003/status
- **Web Dashboard**: http://localhost:3000

### External Resources
- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cohere API Documentation](https://docs.cohere.com/)
- [PostgreSQL Replication](https://www.postgresql.org/docs/current/high-availability.html)

---

## 🏆 System Highlights

### Tier-0 Reliability
- **99.99999% SLA Target** (3 seconds downtime/year)
- **Sub-5-Second Failover** with database promotion
- **Multi-Region Architecture** (PostgreSQL + Redis replication)

### Scale & Performance
- **100,000 IoT Devices** across 10 global sites
- **1,000 Active Users** with session tracking
- **Real-Time Telemetry** via MQTT at scale

### AI Intelligence
- **Cohere-Enhanced RAG** for natural language queries
- **Safety Compliance Detection** with image analysis
- **BP Document Analysis** with semantic search

---

## 📊 Technology Stack

| Category | Technologies |
|----------|-------------|
| **Infrastructure** | Docker, Docker Compose, Nginx |
| **Databases** | PostgreSQL 16 (streaming replication), MongoDB 7, Redis 7 (Sentinel) |
| **Message Brokers** | MQTT (Mosquitto 2.0), RabbitMQ 3.12 |
| **Backend** | FastAPI, Python 3.11+, Uvicorn |
| **AI/ML** | Cohere (command-a-vision-07-2025), PyPDF, scikit-learn |
| **Monitoring** | Prometheus, Grafana |
| **Frontend** | HTML5/CSS3, Vanilla JavaScript |

---

## 🎓 Learning Path

### Beginner
1. Start with [Quick Start Guide](../README.md#-quick-start)
2. Explore [System Architecture](architecture.md)
3. Review [Data Pipelines](data-pipelines.md)

### Intermediate
4. Study [API Reference](api-reference.md)
5. Learn [Development Workflows](development.md)
6. Practice [Testing Procedures](testing.md)

### Advanced
7. Master [Multi-Region Failover](failover.md)
8. Implement [Monitoring Dashboards](monitoring.md)
9. Apply [Security Hardening](security.md)

---

## 🤝 Contributing

This is an academic project demonstrating enterprise SRE principles. See [Assignment Overview](assignment.md) for context.

---

## 📞 Support

- Check [Troubleshooting Guide](troubleshooting.md) for common issues
- Review logs: `docker-compose logs [service-name]`
- Verify health: `docker-compose ps`

---

**Built with ❤️ for Enterprise Reliability Engineering Excellence**

**Target SLA: 99.99999% | Mission: Zero Downtime | Achieved: Sub-5-Second Failover**
