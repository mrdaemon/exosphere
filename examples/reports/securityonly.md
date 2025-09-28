# System Updates Report

Security Only Report, complete, generated on 2025-09-29 22:59:04 -0400

- **Total hosts:** 5
- **Hosts with security updates:** 2
- **Total security updates:** 4

## web-prod-01 (10.0.1.10)

**System Information:**

- **Description**: Web Server
- **OS**: linux ubuntu 22.04
- **Package Manager**: apt
- **Last Refresh**: 2025-09-29 20:59:03 -0400

**Available Updates (2):**

| Package | Current Version | New Version | Sec | Source |
|---------|-----------------|-------------|-----|--------|
| **apache2** | 2.4.52-1ubuntu4.6 | 2.4.52-1ubuntu4.7 | **Yes** | security |
| **php8.1** | 8.1.2-1ubuntu2.13 | 8.1.2-1ubuntu2.14 | **Yes** | security |

## db-01 (10.0.2.20)

**System Information:**

- **Description**: PostgreSQL database server
- **OS**: linux debian 12
- **Package Manager**: apt
- **Last Refresh**: 2025-09-29 21:59:03 -0400

**Available Updates (2):**

| Package | Current Version | New Version | Sec | Source |
|---------|-----------------|-------------|-----|--------|
| **postgresql-14** | 14.9-0+deb12u1 | 14.10-0+deb12u1 | **Yes** | security |
| **openssl** | 3.0.9-1+deb12u3 | 3.0.11-1+deb12u2 | **Yes** | security |

## admin-01 (10.0.2.30)

**System Information:**

- **Description**: Admin Server
- **OS**: freebsd 14.3-RELEASE-p3
- **Package Manager**: pkg
- **Last Refresh**: 2025-09-29 19:59:03 -0400

**No updates available.**

## lb-01 (10.0.1.5)

**System Information:**

- **Description**: HAProxy load balancer
- **OS**: linux rhel 9
- **Package Manager**: dnf
- **Last Refresh**: 2025-09-29 22:29:03 -0400

**No updates available.**

## dev-staging (10.0.3.100)

**System Information:**

- **Description**: Development and staging environment
- **OS**: linux ubuntu 20.04
- **Package Manager**: apt
- **Last Refresh**: 2025-09-26 22:59:03 -0400 *(Stale, needs refresh)*

**No updates available.**

---

*Generated with [Exosphere](https://github.com/mrdaemon/exosphere) version 1.5.0.dev0*
