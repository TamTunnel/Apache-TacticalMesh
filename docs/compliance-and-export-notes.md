# Compliance and Export Control Notes

## TacticalMesh — Dual-Use Networking Platform

**Document Version:** 1.0  
**Last Updated:** December 2025  
**Classification:** UNCLASSIFIED / OPEN SOURCE

---

## Executive Summary

TacticalMesh is an **open-source, general-purpose tactical edge networking platform** released under the Apache License 2.0. This document provides important legal and compliance information for organizations considering the deployment or modification of this software.

---

## Nature of the Software

### What TacticalMesh IS:

- A **general-purpose networking orchestration platform** for managing distributed edge nodes
- **Dual-use software** applicable to defense, disaster response, commercial IoT, and civil resilience applications
- **Open-source software** with fully transparent source code available for security review
- Built on **widely-used, standard technologies** (Python, PostgreSQL, React) with no proprietary components

### What TacticalMesh IS NOT:

- Does not include any **classified information** or classified algorithms
- Does not include any **cryptographic implementations** beyond standard TLS/HTTPS for transport security
- Does not include any **radio frequency** or **waveform** implementations
- Does not include any **targeting**, **weapons**, or **kill chain** capabilities
- Does not include any **signals intelligence** or **electronic warfare** capabilities

---

## U.S. Export Control Considerations

### General Information

The TacticalMesh project has been designed with the following export control considerations in mind:

1. **ITAR (International Traffic in Arms Regulations):**  
   To the best of our knowledge, TacticalMesh does not contain defense articles or technical data as defined under the U.S. Munitions List (USML). The software is a general-purpose networking tool with no inherent military-specific functionality.

2. **EAR (Export Administration Regulations):**  
   TacticalMesh is believed to be classified under EAR99 as publicly available, open-source software without controlled encryption beyond standard authentication protocols. However, this assessment is informal and not a legal determination.

3. **Open Source Exception:**  
   Under 15 CFR § 734.3(b)(3), published open-source software is generally not subject to the EAR. TacticalMesh is publicly available without access restrictions.

### Disclaimers

> **⚠️ IMPORTANT: Not Legal Advice**
>
> The information in this document is provided for general informational purposes only and does not constitute legal advice. Export control regulations are complex and subject to change. The TacticalMesh project and its contributors make no representations regarding the export classification of this software.
>
> **End-users and integrators are solely responsible for:**
> - Obtaining their own export control classification and legal review
> - Ensuring compliance with all applicable U.S. and international export control laws
> - Obtaining any necessary export licenses before transferring this software internationally
> - Compliance with all applicable national laws in their jurisdiction

---

## NATO and Allied Nations Considerations

For organizations in NATO member states and allied nations:

1. **National Regulations:** Many NATO countries have their own export control regimes that may impose additional requirements. Users must ensure compliance with their national regulations.

2. **Technology Transfer:** Transfer of this software, including to contractors or partner nations, may require approval under national technology transfer regulations.

3. **Classification Handling:** If this software is integrated into classified systems, users are responsible for handling the resulting system according to applicable security classifications.

4. **Interoperability:** While designed with interoperability in mind, actual integration with military systems will require appropriate security reviews and certifications.

---

## Open Source Benefits for Defense Applications

### Transparency and Auditability

- All source code is publicly available for security review
- No hidden backdoors or undisclosed functionality
- Independent verification by multiple parties is possible

### Security Through Openness

- Vulnerabilities can be identified and reported by the security community
- Rapid patching and updates are possible
- No reliance on "security through obscurity"

### Audit Trail and Accountability

TacticalMesh includes built-in features to support compliance and oversight:

- **Comprehensive Audit Logging:** All operator actions are logged with timestamps, user identity, and action details
- **Role-Based Access Control:** Clear delineation of permissions (Admin, Operator, Observer)
- **API-First Design:** All actions occur through documented API endpoints, enabling external monitoring

---

## Modification and Integration Guidelines

When modifying or integrating TacticalMesh:

1. **Export Control Review:** Any modifications that add encryption, military-specific functionality, or integration with controlled systems should undergo export control review.

2. **Security Classification:** Integration with classified systems may result in classification requirements for the integrated system.

3. **Contribution Guidelines:** Contributions to the open-source project must not include export-controlled, classified, or proprietary information.

4. **License Compliance:** Modifications must comply with the Apache License 2.0 terms.

> [!CAUTION]
> **Radio and Cryptographic Integration Warning**
> 
> Integration of TacticalMesh with specific radio systems, waveforms, or cryptographic modules (beyond standard TLS) may **change the export control classification** of the resulting integrated system and is **explicitly out of scope** for the core TacticalMesh project.
> 
> Examples that may trigger export control review:
> - Integration with military radios (e.g., SINCGARS, MUOS, Link 16)
> - Custom cryptographic implementations or algorithms
> - Hardware security module (HSM) integration
> - FIPS-validated cryptography implementations
> - Classified or proprietary waveform implementations
> 
> Users integrating such systems should consult export control counsel **before** development.

---

## Contact and Further Information

For questions regarding this software:

- **Project Repository:** https://github.com/TamTunnel/TacticalMesh
- **Issue Tracker:** https://github.com/TamTunnel/TacticalMesh/issues

For export control questions, consult with:
- Your organization's legal counsel
- Your organization's export control office
- For U.S. entities: Bureau of Industry and Security (BIS)
- For U.S. defense-related: Directorate of Defense Trade Controls (DDTC)

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | December 2025 | Initial release |

---

*This document is provided as part of the TacticalMesh open-source project and is licensed under Apache License 2.0.*
