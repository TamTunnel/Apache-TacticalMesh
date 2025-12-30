# Production Deployment Runbook

## TacticalMesh Deployment Guide

This runbook provides step-by-step instructions for deploying TacticalMesh in production environments.

---

## Pre-flight Checklist

### Infrastructure Requirements

| Requirement | Details |
|-------------|---------|
| Controller Host | 2+ CPU cores, 4GB+ RAM, 50GB storage |
| Database | PostgreSQL 15+ (can be same host or separate) |
| Nodes | Raspberry Pi 4 (4GB) or equivalent ARM/x86 |
| Network | Stable connectivity between controller and at least one node |

### Network Configuration

- [ ] **DNS**: Configure DNS record for controller (e.g., `mesh.example.com`)
- [ ] **TLS Certificates**: Obtain valid certificates (Let's Encrypt or enterprise CA)
- [ ] **Firewall Ports**:
  - `443/tcp` - HTTPS (Controller API)
  - `8000/tcp` - Backend API (internal)
  - `3000/tcp` - Web Console (if separate)
  - `7777/udp` - Mesh peering between agents
  - `5432/tcp` - PostgreSQL (internal only)

### Security Checklist

- [ ] Generate strong `TM_JWT_SECRET_KEY` (32+ random bytes)
- [ ] Set `TM_DEBUG=false` in production
- [ ] Configure rate limiting thresholds
- [ ] Plan password rotation policy

---

## Step 1: Deploy Controller

### 1.1 Clone Repository

```bash
git clone https://github.com/TamTunnel/TacticalMesh.git
cd TacticalMesh
```

### 1.2 Configure Environment

```bash
cp .env.example .env
# Edit .env with production values
```

**Required Environment Variables:**

```bash
TM_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tacticalmesh
TM_JWT_SECRET_KEY=your-32-byte-random-secret-key-here
TM_DEBUG=false
TM_LOG_LEVEL=INFO
```

### 1.3 Start Services

```bash
# Production deployment with Docker Compose
docker-compose -f docker-compose.yaml up -d

# Verify services
docker-compose ps
docker-compose logs -f controller
```

### 1.4 Verify Controller Health

```bash
curl -k https://your-controller:443/health
# Expected: {"status": "healthy", ...}
```

### 1.5 Change Default Admin Password

> [!CAUTION]
> The default admin user (`admin`/`admin123`) must change their password on first login.

1. Login to Web Console at `https://your-controller:443`
2. Complete forced password change
3. Use new credentials for subsequent access

---

## Step 2: Configure Agents

### 2.1 Install Agent on Each Node

```bash
# On each edge node
git clone https://github.com/TamTunnel/TacticalMesh.git
cd TacticalMesh/agent
pip3 install -r requirements.txt
```

### 2.2 Generate Configuration

```bash
python3 -m agent.main --init-config \
  --node-id "edge-node-$(hostname)" \
  --controller "https://your-controller:443"
```

### 2.3 Configure Mesh Networking (Optional)

Edit `config.yaml` to enable mesh routing:

```yaml
mesh:
  enabled: true
  listen_port: 7777
  max_hops: 5
  peers:
    - node_id: edge-node-002
      address: 192.168.1.102
      port: 7777
```

### 2.4 Start Agent

```bash
# Foreground (testing)
python3 -m agent.main --config config.yaml

# Background (production)
nohup python3 -m agent.main --config config.yaml > agent.log 2>&1 &

# Or use systemd (recommended)
sudo systemctl enable tacticalmesh-agent
sudo systemctl start tacticalmesh-agent
```

---

## Step 3: Verify Mesh

### 3.1 Check Node Registration

1. Open Web Console
2. Navigate to Nodes view
3. Verify all nodes show "online" status

### 3.2 Test Command Dispatch

```bash
# From controller, send ping command
curl -X POST https://your-controller:443/api/v1/commands \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"target_node_id": "edge-node-001", "command_type": "ping"}'
```

### 3.3 Verify Mesh Routing (if enabled)

Check agent logs for mesh peer discovery:

```
INFO: MeshPeering: Peer edge-node-002 status: REACHABLE
INFO: MeshRouter: Route discovered: controller via edge-node-002
```

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Connection refused` | Controller not running | Check `docker-compose ps` |
| `401 Unauthorized` | Invalid/expired token | Re-login, check JWT secret |
| `Node not appearing` | Agent can't reach controller | Check firewall, network |
| `Mesh peer unreachable` | UDP blocked | Open port 7777/udp |
| `Database connection failed` | Pool exhausted | Restart controller, check connections |

### Log Locations

| Component | Location |
|-----------|----------|
| Controller | `docker-compose logs controller` |
| Agent | `./agent.log` or journalctl if using systemd |
| PostgreSQL | `docker-compose logs postgres` |
| Frontend | Browser console (F12) |

### Health Check Endpoints

```bash
# Controller health
curl https://your-controller/health

# API docs (development only)
curl https://your-controller/docs
```

---

## Monitoring Setup

### Health Checks

Configure your monitoring system to poll:

- `GET /health` - Returns `{"status": "healthy"}` when operational
- Database connectivity is checked via `pool_pre_ping`

### Log Aggregation

For production, forward logs to a centralized system:

```yaml
# docker-compose.override.yaml
services:
  controller:
    logging:
      driver: "syslog"
      options:
        syslog-address: "tcp://your-siem:514"
```

### Metrics (Roadmap)

Prometheus metrics export is planned for v0.2.

---

## Disaster Recovery

### Database Backup

```bash
# Daily backup (add to cron)
docker exec tacticalmesh-postgres pg_dump -U postgres tacticalmesh > backup-$(date +%Y%m%d).sql

# Or use pg_basebackup for point-in-time recovery
```

### Restore Procedure

```bash
# Stop services
docker-compose down

# Restore database
docker exec -i tacticalmesh-postgres psql -U postgres tacticalmesh < backup-20251224.sql

# Restart services
docker-compose up -d
```

### Agent Recovery

Agents automatically reconnect after controller restart. No special recovery needed.

If agent config is lost:

1. Re-run `--init-config`
2. Node will re-register with new credentials
3. Old node record can be deleted from controller

---

## Rollback Procedure

If deployment fails:

1. `docker-compose down`
2. `git checkout <previous-tag>`
3. `docker-compose up -d --build`

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Applies To**: TacticalMesh v0.1.0+
