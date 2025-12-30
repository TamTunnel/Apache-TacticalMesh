# Security Policy

## Reporting Security Vulnerabilities

The TacticalMesh team takes security vulnerabilities seriously. We appreciate your efforts to responsibly disclose your findings.

### How to Report

**Preferred Method:** Use [GitHub Security Advisories](https://github.com/TamTunnel/Apache-TacticalMesh/security/advisories/new) to report vulnerabilities privately.

**Alternative:** Email security concerns to the repository maintainers via the contact information in the repository.

### What to Include

When reporting a vulnerability, please include:

1. **Description** of the vulnerability
2. **Steps to reproduce** the issue
3. **Affected versions** if known
4. **Potential impact** of the vulnerability
5. **Suggested remediation** if you have one

### Response Timeline

- **Acknowledgment:** Within 72 hours
- **Initial assessment:** Within 7 days
- **Status updates:** Every 14 days until resolved

---

## Security Model

### Scope and Limitations

TacticalMesh is **open-source, unclassified software** designed as general-purpose networking infrastructure:

> [!IMPORTANT]
> **No Warranty.** This software is provided "AS IS" without warranty of any kind. See the [Apache 2.0 License](LICENSE) for details.

> [!CAUTION]
> **No Accreditation.** TacticalMesh has NOT received any government security accreditation, Authority to Operate (ATO), or certification. Organizations deploying this software in government or defense environments are solely responsible for obtaining necessary authorizations.

### Security Features (v0.1.0)

| Feature | Implementation Status |
|---------|----------------------|
| Transport Encryption | ✅ HTTPS/TLS (standard libraries) |
| Authentication | ✅ JWT tokens with configurable expiration |
| Authorization | ✅ Role-based access control (Admin, Operator, Observer) |
| Audit Logging | ✅ Timestamped logs of all significant actions |
| Password Storage | ✅ bcrypt hashing |
| Input Validation | ✅ Pydantic schema validation |
| Rate Limiting | ✅ 5/min login, 10/min registration |
| Account Lockout | ✅ 15-minute lockout after 5 failed attempts |
| Password Complexity | ✅ Requires uppercase, lowercase, digit, special char |
| Forced Password Change | ✅ Default admin must change password on first login |
| Mesh Routing TTL | ✅ Hop limits prevent routing loops (default 5 hops) |
| Mesh Path Tracing | ✅ Full relay path logged for audit |


### What This Project Does NOT Provide

This project explicitly does **NOT** include:

- ❌ Cryptographic implementations beyond standard TLS
- ❌ Classified algorithms or data handling
- ❌ Hardware security module (HSM) integration
- ❌ FIPS-validated cryptography
- ❌ Export-controlled technology

### Compliance Responsibility

Organizations deploying TacticalMesh are responsible for:

1. Obtaining any required security authorizations (ATO, IL certifications, etc.)
2. Conducting their own security assessments
3. Ensuring compliance with applicable laws and regulations
4. Export control due diligence (see `docs/compliance-and-export-notes.md`)

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Active development |
| < 0.1   | ❌ Not supported |

---

## Security Best Practices for Deployment

When deploying TacticalMesh:

1. **Change default credentials immediately** after initial setup
2. **Use HTTPS** for all controller communications
3. **Restrict network access** to the controller using firewalls
4. **Review audit logs** regularly for suspicious activity
5. **Keep dependencies updated** via Dependabot or manual review
6. **Run in isolated environments** with minimal privileges

---

## Acknowledgments

We thank the security research community for helping improve this project. Responsible disclosure of vulnerabilities is greatly appreciated.
