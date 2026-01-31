# System Updates Report

Updates Only Report, complete, generated on 2026-01-31 03:01:51 -0500

- **Total hosts:** 5
- **Hosts with updates:** 4
- **Total updates:** 11
- **Security updates:** 4

## web-prod-01 (10.0.1.10)

**System Information:**

- **Description**: Web Server
- **OS**: linux ubuntu 22.04
- **Package Manager**: apt
- **Last Refresh**: 2026-01-31 01:01:51 -0500

**Available Updates (4):**

| Package | Current Version | New Version | Sec | Source |
|---------|-----------------|-------------|-----|--------|
| **apache2** | 2.4.52-1ubuntu4.6 | 2.4.52-1ubuntu4.7 | **Yes** | security |
| **php8.1** | 8.1.2-1ubuntu2.13 | 8.1.2-1ubuntu2.14 | **Yes** | security |
| **curl** | 7.81.0-1ubuntu1.10 | 7.81.0-1ubuntu1.13 | No | updates |
| **vim** | 2:8.2.3458-2ubuntu2.2 | 2:8.2.3458-2ubuntu2.4 | No | updates |

## db-01 (10.0.2.20)

**System Information:**

- **Description**: PostgreSQL database server
- **OS**: linux debian 12
- **Package Manager**: apt
- **Last Refresh**: 2026-01-31 02:01:51 -0500

**Available Updates (4):**

| Package | Current Version | New Version | Sec | Source |
|---------|-----------------|-------------|-----|--------|
| **postgresql-14** | 14.9-0+deb12u1 | 14.10-0+deb12u1 | **Yes** | security |
| **openssl** | 3.0.9-1+deb12u3 | 3.0.11-1+deb12u2 | **Yes** | security |
| **rsync** | 3.2.7-1 | 3.2.7-1+deb12u1 | No | main |
| **libextra3** | (NEW) | 3.2.2-2 | No | main |

## admin-01 (10.0.2.30)

**System Information:**

- **Description**: Admin Server
- **OS**: freebsd 14.3-RELEASE-p3
- **Package Manager**: pkg
- **Last Refresh**: 2026-01-31 00:01:51 -0500

**Available Updates (2):**

| Package | Current Version | New Version | Sec | Source |
|---------|-----------------|-------------|-----|--------|
| **en-freebsd-doc** | 20250814,1 | 20250920,1 | No | FreeBSD |
| **expat** | 2.7.1 | 2.7.2 | No | FreeBSD |

## dev-staging (10.0.3.100)

**System Information:**

- **Description**: Development and staging environment
- **OS**: linux ubuntu 20.04
- **Package Manager**: apt
- **Last Refresh**: 2026-01-28 03:01:51 -0500 *(Stale, needs refresh)*

**Available Updates (1):**

| Package | Current Version | New Version | Sec | Source |
|---------|-----------------|-------------|-----|--------|
| **git** | 1:2.34.1-1ubuntu1.9 | 1:2.34.1-1ubuntu1.10 | No | updates |

---

*Generated with [Exosphere](https://github.com/mrdaemon/exosphere) version 2.2.1.dev0*
