# Apache TacticalMesh

**Open-Source Tactical Edge Networking Platform**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-green.svg)](https://swagger.io/specification/)

---

## One-Line Summary

Apache TacticalMesh is an open-source, decentralized mesh networking platform that enables resilient command-and-control communications between edge nodes in contested or infrastructure-denied environments.

---

## Problem Statement

### The Operational Reality

Modern defense operations, disaster response scenarios, and civil resilience efforts face a common challenge: **communications in contested environments**.

Consider these operational realities:

- **Contested Spectrum:** Adversary jamming and interference degrade traditional radio links
- **Destroyed Infrastructure:** After natural disasters or in conflict zones, cell towers and network infrastructure may be non-functional
- **Mobility Requirements:** Vehicles, dismounted units, sensors, and UAS must maintain connectivity while moving
- **Coalition Operations:** Allied forces must interoperate, often with incompatible proprietary systems
- **Disconnected Operations:** Forward units may be cut off from headquarters for extended periods

### Why Current Systems Fall Short

Existing tactical networking solutions suffer from critical limitations:

| Challenge | Impact |
|-----------|--------|
| **Vendor Lock-in** | Proprietary systems create single-vendor dependencies with long procurement cycles and limited flexibility |
| **Cost** | Military-grade mesh radios cost $10,000–$50,000+ per unit, limiting widespread deployment |
| **Interoperability** | Different systems cannot communicate, hindering coalition operations |
| **Adaptability** | Closed systems cannot be rapidly modified to address emerging threats |
| **Supply Chain Risk** | Proprietary hardware creates supply chain vulnerabilities |

---

## Competitor and Landscape Analysis

### Categories of Existing Solutions

#### 1. Proprietary Military Mesh Systems

Traditional defense contractors offer specialized tactical radio systems with integrated mesh networking:

- **Strengths:** Proven in military environments, designed for specific frequency bands
- **Weaknesses:** Extremely high cost, vendor lock-in, slow innovation cycles, limited customization

#### 2. Commercial Mesh Networking

Commercial mesh solutions designed for IoT and enterprise applications:

- **Strengths:** Lower cost, widely available
- **Weaknesses:** Not designed for contested environments, lack tactical features, no disconnected operation support

#### 3. Open RAN Initiatives

Telecom-focused efforts to open radio access network interfaces:

- **Strengths:** Open standards, multi-vendor support
- **Weaknesses:** Infrastructure-centric, not designed for tactical edge, assumes reliable backhaul

### The Gaps Apache TacticalMesh Addresses

| Gap | Apache TacticalMesh Approach |
|-----|------------------------------|
| Vendor Lock-in | Fully open-source with Apache 2.0 license |
| High Cost | Runs on commodity hardware (Raspberry Pi, x86 boxes) |
| Closed Code | Transparent, auditable source code |
| Slow Innovation | Community-driven development with rapid iteration |
| Interoperability | OpenAPI-first design for easy integration |
| Single Points of Failure | Decentralized architecture with graceful degradation |

---

## What Apache TacticalMesh Provides

### Core Benefits

✅ **Resilient Edge Networking** — Nodes continue operating when disconnected from the central controller, with automatic reconnection and state synchronization

✅ **Open-Source Transparency** — Full source code visibility enables security audits, customization, and elimination of supply chain black boxes

✅ **Commodity Hardware** — Deploy on Raspberry Pi, NVIDIA Jetson, commercial edge servers, or any Linux platform

✅ **OpenAPI Integration** — Standard REST APIs enable integration with existing C2 systems, sensor networks, and enterprise applications

✅ **Role-Based Access Control** — Granular permissions for administrators, operators, and observers with complete audit logging

✅ **Dual-Use Design** — Applicable to defense, disaster response, remote industrial operations, and civil resilience

### Target Deployment Scenarios

- **Military Edge Networks:** Connecting vehicles, dismounted units, sensors, and small UAS in tactical environments
- **Disaster Response:** Rapidly deployable communications for first responders when infrastructure is destroyed
- **Remote Operations:** Industrial sites, research stations, and maritime vessels with intermittent connectivity
- **Coalition Operations:** Interoperable command and control for allied forces with different native systems

---

## Key Features (v0.1)

### Node Management

- **Registration & Discovery:** Automatic node registration with the central controller
- **Heartbeat Monitoring:** Real-time health status with configurable intervals
- **Telemetry Collection:** CPU, memory, disk usage, and GPS location (when available)
- **Graceful Degradation:** Nodes operate independently when disconnected

### Command & Control

- **Command Dispatch:** Send commands to individual nodes or groups
- **Command Types:** Ping, configuration updates, role changes, and custom actions
- **Status Tracking:** Full lifecycle tracking from pending to completion
- **Audit Trail:** Complete logging of all operator actions

### Security & Access Control

- **JWT Authentication:** Standard token-based authentication
- **Role-Based Permissions:**
  - **Admin:** Full system access including user management
  - **Operator:** Node and command management
  - **Observer:** Read-only access to status and history
- **Audit Logging:** Timestamped log of all actions for compliance

### Integration

- **OpenAPI 3.0:** Complete API specification for code generation
- **REST/JSON:** Standard interfaces for easy integration
- **Webhook Support:** (Roadmap) Event notifications to external systems

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THEATER OPERATIONS CENTER                        │
│  ┌───────────────┐  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ Mesh          │  │ PostgreSQL  │  │ Web Console              │  │
│  │ Controller    │──│ Database    │  │ (React/TypeScript)       │  │
│  │ (FastAPI)     │  └─────────────┘  └──────────────────────────┘  │
│  └───────┬───────┘                              ▲                   │
│          │                                      │                   │
└──────────┼──────────────────────────────────────┼───────────────────┘
           │ HTTPS/REST                           │
           │ (Heartbeat, Commands)                │
           ▼                                      │
┌──────────────────────────────────────────────────────────────────────┐
│                         TACTICAL EDGE NETWORK                        │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ Vehicle  │◄──►│Dismounted│◄──►│  Sensor  │◄──►│   UAS    │       │
│  │  Node    │    │   Node   │    │   Node   │    │   Node   │       │
│  │ (Agent)  │    │ (Agent)  │    │ (Agent)  │    │ (Agent)  │       │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘       │
│                                                                      │
│                    ◄──► Mesh Links (Future)                         │
└──────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Backend Controller | Python / FastAPI | Widely known, easy to audit, async-native |
| Database | PostgreSQL | Enterprise-grade, strong government track record |
| Web Console | React / TypeScript | Industry standard, large talent pool |
| Node Agent | Python | Portable across ARM and x86, easy to modify |
| Deployment | Docker / Kubernetes | Standard container orchestration |
| API Specification | OpenAPI 3.0 | Enables code generation and tooling |

---

## Security and Compliance Posture

### Security Features

- **Transport Security:** All communications over HTTPS/TLS
- **Authentication:** JWT tokens with configurable expiration
- **Authorization:** Role-based access control at every endpoint
- **Audit Trail:** Complete logging of all operator actions with timestamps

### Compliance Considerations

Apache TacticalMesh is designed as a **general-purpose, dual-use platform**:

- ✅ Does not include classified information or algorithms
- ✅ Does not include cryptographic implementations beyond standard TLS
- ✅ Open-source code enables security review and audit
- ✅ Built-in audit logging supports compliance requirements

> **Important:** End-users are responsible for export control compliance. See `docs/compliance-and-export-notes.md` for details.

---

## Deployment Quick Start

### Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/TamTunnel/Apache-TacticalMesh.git
cd Apache-TacticalMesh

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

Access points:
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Console:** http://localhost:3000

Default credentials: `admin` / `admin123`

### Minimal Local Demo

1. **Start the Controller:**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn backend.main:app --reload
   ```

2. **Start a Node Agent:**
   ```bash
   cd agent
   pip install -r requirements.txt
   python -m agent.main --init-config --node-id demo-node-001 --controller http://localhost:8000
   python -m agent.main --config config.yaml
   ```

3. **Start the Console:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## Roadmap

### Near-Term (v0.2–0.3)

- [ ] Multi-hop mesh routing between agents
- [ ] Offline command buffering with sync-on-reconnect
- [ ] WebSocket real-time updates in console
- [ ] Prometheus metrics export

### Medium-Term (v0.4–1.0)

- [ ] Geographic visualization (map-based node display)
- [ ] Group-based command targeting
- [ ] Plugin architecture for custom command handlers
- [ ] Integration with common radio APIs (SDR, commercial mesh radios)

### Long-Term (Post-1.0)

- [ ] Distributed controller federation
- [ ] Advanced mesh topology optimization
- [ ] Bandwidth-constrained transport modes
- [ ] Hardware abstraction layer for tactical radios

> **Note:** This roadmap represents potential directions. Actual development priorities will be driven by community needs and contributions.

---

## Contributing

We welcome contributions from the community! Please review our guidelines:

### What We Accept

✅ Bug fixes and improvements  
✅ Documentation enhancements  
✅ New features aligned with project goals  
✅ Test coverage improvements  
✅ Security vulnerability reports (via responsible disclosure)

### What We Cannot Accept

❌ Proprietary or licensed code  
❌ Export-controlled implementations  
❌ Classified information  
❌ Code without appropriate tests or documentation

### Getting Started

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a Pull Request

See `CONTRIBUTING.md` for full guidelines.

---

## License

Apache TacticalMesh is licensed under the **Apache License 2.0**.

```
Copyright 2024 Apache TacticalMesh Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

See [LICENSE](LICENSE) for the complete license text.

---

## Contact

- **Repository:** https://github.com/TamTunnel/Apache-TacticalMesh
- **Issues:** https://github.com/TamTunnel/Apache-TacticalMesh/issues
- **Discussions:** https://github.com/TamTunnel/Apache-TacticalMesh/discussions

---

*Apache TacticalMesh — Resilient networking for the tactical edge.*
