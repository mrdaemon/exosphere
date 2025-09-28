# System Updates Report

Full Report, filtered, generated on 2025-09-29 22:59:04 -0400

- **Selected hosts:** 5
- **Hosts with updates:** 2
- **Total updates:** 8
- **Security updates:** 4

## web-prod-01 (10.0.1.10)

**System Information:**

- **Description**: Web Server
- **OS**: linux ubuntu 22.04
- **Package Manager**: apt
- **Last Refresh**: 2025-09-29 20:59:03 -0400

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
- **Last Refresh**: 2025-09-29 21:59:03 -0400

**Available Updates (4):**

| Package | Current Version | New Version | Sec | Source |
|---------|-----------------|-------------|-----|--------|
| **postgresql-14** | 14.9-0+deb12u1 | 14.10-0+deb12u1 | **Yes** | security |
| **openssl** | 3.0.9-1+deb12u3 | 3.0.11-1+deb12u2 | **Yes** | security |
| **rsync** | 3.2.7-1 | 3.2.7-1+deb12u1 | No | main |
| **libextra3** | (NEW) | 3.2.2-2 | No | main |

---

*Generated with [Exosphere](https://github.com/mrdaemon/exosphere) version 1.5.0.dev0*
