# Changelog

All notable changes to TacticalMesh will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-22

### Summary

Initial public release of TacticalMesh — an open-source tactical edge networking platform designed for defense, disaster response, and dual-use applications.

### Added

#### Mesh Controller (Backend)
- FastAPI-based REST API with OpenAPI 3.0 specification
- Node registration and discovery with heartbeat monitoring
- Telemetry collection: CPU, memory, disk usage, GPS coordinates
- Command dispatch with full lifecycle tracking (pending → completed/failed)
- PostgreSQL database with async SQLAlchemy
- JWT authentication with configurable expiration
- Role-based access control (RBAC): Admin, Operator, Observer
- Comprehensive audit logging for all significant operations
- Structured logging for production deployments
- Docker and docker-compose deployment support

#### Node Agent
- Python-based lightweight agent for edge deployment
- YAML configuration with environment variable substitution
- Resilient controller communication with retry and exponential backoff
- Multiple controller URL failover
- Command execution with extensible action handlers:
  - PING: Connectivity test
  - RELOAD_CONFIG: Dynamic configuration refresh
  - UPDATE_CONFIG: Remote configuration updates
  - CHANGE_ROLE: Node role modifications
  - CUSTOM: Extensible command framework
- Local buffering of telemetry during disconnection
- Graceful shutdown handling
- State machine: DISCONNECTED → REGISTERED → DEGRADED
- **Multi-hop mesh routing** with automatic failover:
  - Route discovery via peer broadcast
  - Smart path selection (hop count, RTT, reliability)
  - TTL-based loop prevention (configurable max_hops)
  - Full relay path tracing for debugging/audit
- Mesh peering with UDP-based peer discovery

#### Web Console (Frontend)
- React + TypeScript single-page application
- Material UI dark theme optimized for operations centers
- Node status dashboard with real-time filtering and pagination
- Command management: creation, tracking, and cancellation
- Role-aware UI with appropriate access controls
- Responsive design for various screen sizes
- Nginx-based production deployment

#### Documentation
- Executive-grade README with problem statement and competitor analysis
- Developer onboarding guide with local setup instructions
- Compliance and export control notes (ITAR/EAR considerations)
- Contributing guidelines with code standards
- Security policy (SECURITY.md) with vulnerability reporting
- OpenAPI specification with complete schema definitions

#### DevOps & CI/CD
- Docker Compose for local development and staging
- Dockerfiles for all components (controller, agent, console)
- GitHub Actions CI workflow with backend tests, frontend build
- Security scanning with CodeQL and Trivy
- Dependabot configuration for automated dependency updates

### Security

- All communications secured via HTTPS/TLS
- Password hashing with bcrypt
- JWT tokens with configurable expiration
- Input validation via Pydantic schemas
- Audit trail for compliance requirements

### Known Limitations

- WebSocket real-time updates not yet implemented
- No FIPS-validated cryptography (standard TLS only)
- No HSM integration
- No government security accreditation (ATO)

### License

Apache License 2.0 — See [LICENSE](LICENSE) for details.

---

## [Unreleased]

### Planned for v0.2

- Offline command buffering with sync-on-reconnect
- WebSocket real-time updates in console
- Prometheus metrics export
- Geographic visualization (map-based node display)

[0.1.0]: https://github.com/TamTunnel/TacticalMesh/releases/tag/v0.1.0
[Unreleased]: https://github.com/TamTunnel/TacticalMesh/compare/v0.1.0...HEAD
