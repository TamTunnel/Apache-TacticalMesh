# Lab Deployment Guide

This guide walks you through building a **3-5 node demonstration lab** for evaluating TacticalMesh in a controlled environment.

**Target Audience**: Program managers, technical evaluators, innovation units, contractors

**Time to Deploy**: 2-4 hours (depending on hardware prep)

---

## Lab Objectives

This lab demonstrates:

1. **Node registration and heartbeat monitoring**
2. **Command dispatch and execution** (ping, config updates)
3. **Resilience to controller disconnection** (buffering, reconnection)
4. **Audit logging and role-based access control**
5. **Basic mesh peer discovery** (experimental feature)

---

## Bill of Materials

### Minimum Lab (3 Nodes + 1 Controller)

| Item | Quantity | Purpose | Est. Cost |
|------|----------|---------|-----------|
| Raspberry Pi 4 (4GB RAM) | 3 | Edge nodes | 3 × $55 = $165 |
| microSD cards (32GB+) | 3 | Node OS storage | 3 × $10 = $30 |
| USB-C power supplies | 3 | Node power | 3 × $10 = $30 |
| Laptop or small server | 1 | Controller host | (existing) |
| Ethernet switch + cables | 1 | Lab network | $30 |
| **TOTAL** | — | — | **~$255** |

### Recommended Lab (5 Nodes + 1 Controller)

Add 2 more Raspberry Pi units for more complex scenarios (~$420 total).

### Alternative: Virtual Lab

For quick evaluation without hardware:
- Run controller + 3-5 agent containers on a single Linux VM or laptop
- Use Docker Compose with multiple agent instances
- Simulate network partitions with `iptables` or `docker network disconnect`

---

## Step-by-Step Setup

### Phase 1: Controller Setup (30 minutes)

#### 1.1 Install Controller on Laptop/Server

**Prerequisites**:
- Ubuntu 22.04 or similar Linux (macOS/Windows with Docker also work)
- Docker and Docker Compose installed
- Internet connection (for initial setup)

**Steps**:

```bash
# Clone repository
git clone https://github.com/TamTunnel/TacticalMesh.git
cd TacticalMesh

# Start controller and database
docker-compose up -d

# Verify services are running
docker-compose ps
# Expected: controller, postgres, frontend all "Up"

# Check logs
docker-compose logs -f controller
# Wait for "Uvicorn running on http://0.0.0.0:8000"
```

#### 1.2 Access Web Console

Open browser to `http://<controller-ip>:3000`

- Default login: `admin` / `admin123`
- Verify dashboard loads successfully
- Note the controller IP address for agent configuration

#### 1.3 Verify API Endpoint

```bash
curl http://<controller-ip>:8000/health
# Expected: {"status": "healthy", ...}
```

---

### Phase 2: Node Setup (20 minutes per node)

#### 2.1 Prepare Raspberry Pi OS

1. Flash **Raspberry Pi OS Lite (64-bit)** to microSD cards using Raspberry Pi Imager
2. Enable SSH:
   - Create empty file named `ssh` in boot partition, OR
   - Use Imager's advanced options (⚙️) to enable SSH
3. Configure network:
   - Ethernet: Connect to same network as controller
   - WiFi: Use Imager's advanced options to pre-configure
4. Boot each Pi and SSH in: `ssh pi@<node-ip>` (password: `raspberry`)

#### 2.2 Install Python and Dependencies

On each Pi:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and Git
sudo apt install -y python3 python3-pip git

# Clone repository
git clone https://github.com/TamTunnel/TacticalMesh.git
cd TacticalMesh/agent

# Install dependencies
pip3 install -r requirements.txt
```

#### 2.3 Configure Agent

Create config file for each node:

```bash
# Generate initial config
python3 -m agent.main --init-config \
  --node-id "edge-node-001" \
  --controller "http://<controller-ip>:8000"

# Edit config for customization (optional)
nano config.yaml
```

Example `config.yaml`:
```yaml
node_id: edge-node-001
controllers:
  - url: "http://192.168.1.100:8000"
    priority: 1
heartbeat_interval_seconds: 30
registration:
  name: "Vehicle Alpha"
  node_type: "vehicle"
  metadata:
    location: "Building A"
    operator: "Team 1"
```

#### 2.4 Start Agent

```bash
# Run agent (foreground for testing)
python3 -m agent.main --config config.yaml

# Or run as background service
nohup python3 -m agent.main --config config.yaml > agent.log 2>&1 &
```

#### 2.5 Verify Registration

1. Check agent logs for "Successfully registered"
2. Refresh web console - node should appear in dashboard
3. Verify heartbeat updates every 30 seconds

---

### Phase 3: Run Lab Exercises (30-60 minutes)

#### Exercise 1: Node Monitoring

**Objective**: Verify all nodes are online and reporting telemetry.

1. Open web console at `http://<controller-ip>:3000`
2. Navigate to Nodes view
3. Verify all nodes show "online" status (green)
4. Check CPU/Memory telemetry is updating
5. Disconnect one Pi's network cable → status changes to "offline"
6. Reconnect → status returns to "online"

#### Exercise 2: Command Dispatch

**Objective**: Send a command to a specific node and verify execution.

1. In web console, click "Send Command" on any node
2. Select command type: "ping"
3. Submit command
4. Verify command appears in Commands panel
5. Verify status changes: Pending → Sent → Completed
6. Check agent logs for command execution

#### Exercise 3: Network Partition

**Objective**: Demonstrate agent resilience during controller disconnection.

1. Stop the controller: `docker-compose stop controller`
2. Observe agent logs: state changes to DEGRADED
3. Agent continues running, buffers telemetry locally
4. Start controller: `docker-compose start controller`
5. Agent reconnects, flushes buffered data
6. Verify buffered heartbeats appear in controller

#### Exercise 4: Role-Based Access Control

**Objective**: Demonstrate RBAC restricts sensitive operations.

1. Login as admin → can see all features
2. Create a new user with "observer" role via API:
   ```bash
   curl -X POST http://<controller-ip>:8000/api/v1/auth/register \
     -H "Authorization: Bearer <admin-token>" \
     -H "Content-Type: application/json" \
     -d '{"username":"observer1","password":"obs123!@#","email":"obs@example.com","role":"observer"}'
   ```
3. Login as observer1 → verify read-only access
4. Attempt to create command → should be denied (403)

#### Exercise 5: Audit Log Review

**Objective**: Review audit trail for compliance demonstration.

1. Perform several actions (login, command, etc.)
2. Check audit logs in database:
   ```bash
   docker exec -it tacticalmesh-postgres-1 psql -U postgres -d tacticalmesh
   SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 20;
   ```
3. Verify user, action, timestamp are recorded

---

### Phase 4: Mesh Multi-Hop Routing Demo (20 minutes)

> [!NOTE]
> Level 2 Multi-Hop Routing enables nodes to relay heartbeats through peers when the controller is unreachable.

#### 4.1 Configure Mesh Networking

Edit agent config on each node to include mesh settings:

```yaml
mesh:
  enabled: true
  listen_port: 7777
  heartbeat_interval_seconds: 10
  peer_timeout_seconds: 30
  route_cache_ttl_seconds: 60
  max_hops: 5
  peers:
    - node_id: edge-node-002
      address: 192.168.1.102
      port: 7777
    - node_id: edge-node-003
      address: 192.168.1.103
      port: 7777
```

#### 4.2 Restart Agents

```bash
# On each node
pkill -f agent.main
python3 -m agent.main --config config.yaml
```

#### 4.3 Verify Peer Discovery

Check agent logs for:
```
INFO: MeshPeering: Added static peer edge-node-002
INFO: MeshPeering: Peer edge-node-002 status: REACHABLE
INFO: MeshRouter initialized: node_id=edge-node-001, max_hops=5
```

#### 4.4 Test Multi-Hop Relay

1. Block direct controller access on Node 1: `iptables -A OUTPUT -d <controller-ip> -j DROP`
2. Observe agent logs: 
   ```
   WARNING: Direct heartbeat failed - controller unreachable
   INFO: Discovering mesh routes to controller...
   INFO: Route discovered: controller via edge-node-002 (1 hops, 25.0ms)
   INFO: Heartbeat relayed via edge-node-002 (1 hops, 25ms RTT)
   ```
3. Node 2 forwards heartbeat to controller via HTTP
4. Restore access: `iptables -D OUTPUT -d <controller-ip> -j DROP`


---

## Cleanup

When finished with the lab:

```bash
# On controller
docker-compose down -v  # -v removes database volume

# On each Pi (optional)
rm -rf ~/TacticalMesh
```

---

## Troubleshooting

### Node Not Appearing in Console

1. Check agent logs for errors
2. Verify controller URL is correct
3. Check firewall allows port 8000
4. Verify Pi has network connectivity: `ping <controller-ip>`

### Command Stuck in "Pending"

1. Check agent is running and connected
2. Review agent logs for command receipt
3. Verify node heartbeat is recent (< 60 seconds)

### Database Connection Errors

1. Verify PostgreSQL container is running: `docker-compose ps`
2. Check database logs: `docker-compose logs postgres`
3. Ensure `TM_DATABASE_URL` is correct in environment

---

## Next Steps After Lab

1. **Review SECURITY.md** for vulnerability reporting
2. **Review production-hardening.md** for deployment security
3. **Open GitHub issues** for feature requests or bugs
4. **Consider contributing** - see CONTRIBUTING.md

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Applies To**: TacticalMesh v0.1.0+
