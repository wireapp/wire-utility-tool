# Wire Utility Tool

A comprehensive Docker toolkit providing essential debugging utilities for Wire's backend infrastructure.

## 🚀 Quick Start

```bash
# Wire Utility Tool (debugging & utilities)
docker run -it --rm quay.io/wire/wire-utility-tool:latest
```

## 📦 What's Included

### 🔧 Wire Utility Tool

A debugging container with comprehensive tooling:

**Database Clients**
- **PostgreSQL** (`psql`) - Connect and query PostgreSQL databases
- **Redis** (`redis-cli`) - Interact with Redis instances
- **Cassandra** (`cqlsh`) - Query Cassandra clusters (v3.11 compatible)

**Message Queue & Storage**
- **RabbitMQ** (`rabbitmqadmin`) - Manage RabbitMQ instances
- **MinIO Client** (`mc`) - Interact with S3-compatible storage

**Network & System Tools**
- **Network**: `curl`, `wget`, `nc`, `nmap`, `tcpdump`, `dig`, `ping`, `traceroute`, `netstat`
- **Text Processing**: `jq`, `vim`, `nano`, `less`, `tree`
- **Programming**: Python 2 & 3 with pip
- **System Monitoring**: `ps`, `top`, `free`, `uptime`, `vmstat`

**Search & Analytics**
- **Elasticsearch Debug** (`es`) - Debug Elasticsearch clusters

**Status Monitoring**
- **Status Command** (`status`) - Check connectivity to all services

## 🛠️ Usage

### Development

```bash
# Build and test locally
make build-utility && make test-utility
```

### Production

```bash
# Interactive debugging session
docker run -it --rm quay.io/wire/wire-utility-tool:latest

# Check service connectivity
docker run --rm quay.io/wire/wire-utility-tool:latest status

# Debug Elasticsearch
docker run --rm quay.io/wire/wire-utility-tool:latest es health
```

### Available Commands

```bash
# Status and connectivity
status                    # Show service connectivity status

# Database tools
psql                      # PostgreSQL client
cqlsh                     # Cassandra CQL shell
redis-cli                 # Redis client

# Message queue
rabbitmqadmin list queues # RabbitMQ management

# Storage
mc ls wire-minio          # MinIO/S3 client

# Search
es health                 # Elasticsearch cluster health
es nodes                  # Elasticsearch nodes info
es indices                # List indices
es usages                 # Show all available commands
```

## 🔖 Versioning

### Creating Releases

1. **Make changes and test locally**
2. **Create version tag**:
   ```bash
   git tag -a v1.3.0 -m "Add .."
   ```
3. **Push to trigger automated build**:
   ```bash
   git push origin v1.3.0     # → quay.io/wire/wire-utility-tool:v1.3.0
   ```

### Available Tags

| Component | Latest | Versioned |
|-----------|--------|-----------|
| **Utility Tool** | `latest` | `v1.3.0`, `v1.2.0`, `1.2` |

## 🏗️ Architecture

- **Multi-platform**: AMD64 & ARM64 support
- **Security**: Non-root user (UID 65532), minimal attack surface
- **Base**: Debian Bullseye Slim for stability
- **Python**: Python 2.7 & 3.x with essential libraries

## 🤝 Contributing

1. **Add new tools** to Dockerfile.utility
2. **Update README** with tool documentation
3. **Test changes** locally with `make test-utility`
4. **Submit PR** with version tag

---

**Repository Purpose**: Provides standardized debugging utilities for Wire's infrastructure operations.
