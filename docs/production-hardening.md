# Production Hardening Guide

This guide provides security hardening recommendations for deploying TacticalMesh in operational defense, disaster response, or production environments.

> [!WARNING]
> **IMPORTANT**: This guide provides general security recommendations. Organizations are responsible for their own security assessments, ATOs, and compliance with applicable regulations.

---

## Pre-Deployment Checklist

### 1. Credentials and Authentication

- [ ] **Change all default credentials immediately**
  - Default `admin/admin123` is for development only
  - Generate strong passwords (minimum 16 characters, mixed case, numbers, symbols)
  - Store credentials securely (password manager, secrets vault)

- [ ] **Configure JWT secret**
  - Set a strong random `TM_JWT_SECRET_KEY` in backend environment variables
  - Use at least 32 bytes of cryptographically secure random data
  - Generate with: `openssl rand -hex 32`
  - Rotate JWT secrets periodically (recommend quarterly)

- [ ] **Configure token expiration**
  - Set appropriate `TM_ACCESS_TOKEN_EXPIRE_MINUTES` (recommend 60-240 minutes)
  - Shorter duration = more secure, but more frequent re-authentication
  - Require re-authentication for sensitive operations

### 2. TLS/HTTPS Configuration

- [ ] **Enable HTTPS for all communications**
  - Obtain valid TLS certificates from your organization's CA or Let's Encrypt
  - Configure nginx reverse proxy with TLS termination
  - Disable HTTP (port 80), enforce HTTPS only (port 443)

- [ ] **Use strong TLS configuration**
  - TLS 1.2 minimum (TLS 1.3 recommended)
  - Disable weak ciphers (no RC4, DES, 3DES)
  - Enable Forward Secrecy (ECDHE key exchange)

- [ ] **Example nginx TLS configuration**:
  ```nginx
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
  ssl_prefer_server_ciphers off;
  ssl_session_cache shared:SSL:10m;
  ssl_session_timeout 1d;
  ssl_stapling on;
  ssl_stapling_verify on;
  ```

### 3. Network Security

- [ ] **Restrict controller access**
  - Deploy controller behind firewall
  - Allow inbound connections only from authorized node subnets
  - Use VPN or private networks for inter-site communications

- [ ] **Example firewall rules** (iptables):
  ```bash
  # Allow HTTPS from authorized node subnet only
  iptables -A INPUT -p tcp --dport 443 -s 10.0.0.0/8 -j ACCEPT
  iptables -A INPUT -p tcp --dport 443 -j DROP
  
  # Allow SSH from management subnet only
  iptables -A INPUT -p tcp --dport 22 -s 192.168.1.0/24 -j ACCEPT
  iptables -A INPUT -p tcp --dport 22 -j DROP
  ```

- [ ] **PostgreSQL security**
  - Do not expose PostgreSQL port (5432) to public internet
  - Use password authentication (no trust mode)
  - Restrict `pg_hba.conf` to localhost or controller subnet only
  - Consider using SSL for database connections

### 4. Container Security

- [ ] **Run containers as non-root**
  - The provided Dockerfiles should be modified to use a non-root user
  - Example:
    ```dockerfile
    RUN adduser --disabled-password --gecos '' --uid 1000 appuser
    USER appuser
    ```

- [ ] **Use read-only root filesystems where possible**
  - Add `--read-only` flag to docker run commands
  - Mount writable volumes only for logs and data

- [ ] **Scan images for vulnerabilities**
  - Use `docker scan` or Trivy before deployment
  - Update base images regularly (monthly)
  - Example: `trivy image tacticalmesh-controller:latest`

- [ ] **Limit container capabilities**
  ```bash
  docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE ...
  ```

---

## Post-Deployment Checklist

### 1. Logging and Monitoring

- [ ] **Centralize logs to SIEM/SOC**
  - Forward controller logs to syslog, Splunk, or ELK stack
  - Ensure audit logs are tamper-evident (append-only)
  - Configure log retention per organizational policy

- [ ] **Monitor authentication failures**
  - Alert on 5+ failed login attempts from same IP in 5 minutes
  - Alert on role escalation attempts (Observer → Admin)
  - Alert on access from unexpected geolocations

- [ ] **Set up health monitoring**
  - Monitor controller `/health` endpoint (HTTP 200 = healthy)
  - Alert on node heartbeat failures (node offline > 5 minutes)
  - Monitor database connection pool exhaustion
  - Track system resource usage (CPU > 80%, disk > 90%)

### 2. Access Control Review

- [ ] **Implement least privilege**
  - Assign Observer role by default
  - Grant Operator role only to personnel who need to issue commands
  - Limit Admin role to 2-3 personnel maximum
  - Document role assignments and justifications

- [ ] **Regular access audits**
  - Review user accounts monthly
  - Disable accounts for departing personnel immediately
  - Review audit logs weekly for unauthorized access patterns
  - Re-certify access quarterly

### 3. Backup and Recovery

- [ ] **Database backups**
  - Automated daily PostgreSQL backups
  - Test restore procedures monthly
  - Store backups off-site or in separate availability zone
  - Encrypt backups at rest
  - Example pg_dump command:
    ```bash
    pg_dump -h localhost -U postgres tacticalmesh | gzip > backup-$(date +%Y%m%d).sql.gz
    ```

- [ ] **Configuration backups**
  - Version control all configuration files (encrypted in repo)
  - Document node configurations
  - Maintain runbooks for common failure scenarios
  - Test disaster recovery annually

---

## Integration with Existing Infrastructure

### SIEM Integration

TacticalMesh logs are JSON-structured for easy parsing. Key log events to monitor:

| Event | Description | Priority |
|-------|-------------|----------|
| `login_success` | Successful authentication | Low |
| `login_failed` | Failed authentication attempt | Medium |
| `command_created` | Command dispatched to node(s) | Medium |
| `config_updated` | Configuration changes | High |
| `role_changed` | User role modification | High |
| `node_deleted` | Node removed from mesh | High |

Example syslog forwarding configuration:
```python
import logging
from logging.handlers import SysLogHandler

syslog_handler = SysLogHandler(address=('siem.example.mil', 514))
syslog_handler.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger().addHandler(syslog_handler)
```

### Identity Provider Integration (Future)

v0.1.0 uses built-in JWT authentication. Future versions will support:
- LDAP/Active Directory
- SAML 2.0 (CAC/PIV support)
- OAuth 2.0 / OpenID Connect

For current integration, consider:
- Using a reverse proxy (nginx, Keycloak) for SSO
- Mapping external identities to TacticalMesh roles via proxy headers

---

## Defense-Specific Considerations

### Enclave Deployment

- Deploy controller in TOC or command post with reliable power/connectivity
- Use tactical edge nodes (Raspberry Pi, ruggedized compute) at forward positions
- Plan for intermittent connectivity and offline operation (built-in buffering)
- Consider generator/UPS power for controller reliability

### Classification Handling

> [!CAUTION]
> TacticalMesh is designed for **UNCLASSIFIED** use only.

If integrated into classified systems:
- Conduct security assessment for your classification level
- Follow accreditation requirements for your domain (IL2-6, TS/SCI, etc.)
- Ensure physical security of nodes and controllers
- Consider air-gapped deployments for higher classification levels

### Coalition Operations

For multinational exercises, consider:
- Per-nation role-based access (use separate accounts per coalition partner)
- Separate audit logs per nation for accountability
- Clear data-sharing agreements (defined in exercise orders)
- Network segmentation between partners where required

---

## Security Contact

For security issues, see [SECURITY.md](../SECURITY.md) for vulnerability reporting.

For deployment questions, open a discussion on GitHub or consult your organization's cybersecurity team.

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Applies To**: TacticalMesh v0.1.0+
