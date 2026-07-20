# VaultDocs — Software Requirements Specification (SRS)

> **Document ID:** DOC-002
> **Version:** 1.0.0
> **Status:** Approved
> **Author:** Pavan (Software Architect / Project Lead)
> **Contributors:** Raj (Backend Developer), Tirth (Backend Developer)
> **Created Date:** 2026-07-20
> **Last Updated:** 2026-07-20
> **Classification:** Internal Engineering Documentation

---

## Executive Summary

This Software Requirements Specification (SRS) defines the formal functional, non-functional, security, operational, and structural requirements for the VaultDocs enterprise Secure Document Management System. It establishes unambiguous boundaries, acceptance criteria, and traceability matrices required for implementation by the backend engineering team.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Product Overview & Boundary](#2-product-overview--boundary)
3. [User Roles & Permissions Matrix](#3-user-roles--permissions-matrix)
4. [Functional Requirements (FR)](#4-functional-requirements-fr)
5. [Non-Functional Requirements (NFR)](#5-non-functional-requirements-nfr)
6. [Business Rules & Policy Constraints](#6-business-rules--policy-constraints)
7. [Technical Risks & Mitigation Strategies](#7-technical-risks--mitigation-strategies)
8. [System Assumptions & Dependencies](#8-system-assumptions--dependencies)
9. [Acceptance Criteria Framework](#9-acceptance-criteria-framework)
10. [Requirements Traceability Matrix (RTM)](#10-requirements-traceability-matrix-rtm)

---

## 1. Introduction

### 1.1 Purpose
The purpose of this document is to specify all software requirements for VaultDocs Release 1.0.0. It serves as the single source of truth for backend developers, test engineers, enterprise system architects, and technical lead review.

### 1.2 Scope
This specification covers the backend REST API core, data persistence layers, security context evaluation engines, transaction management, background session invalidation, document lifecycle management, and audit logging services.

---

## 2. Product Overview & Boundary

VaultDocs operates as a multi-tenant ready, API-first software application providing cryptographic session authentication, streaming binary object ingestion, database indexing, and granular privilege verification.

```
+-----------------------------------------------------------------------------------+
|                              VAULTDOCS SYSTEM BOUNDARY                            |
|                                                                                   |
|  +-------------------+      HTTPS / REST      +--------------------------------+  |
|  | Enterprise API    | <====================> | VaultDocs FastAPI Engine       |  |
|  | Clients & Web Apps|                        | - Auth & Session Guard         |  |
|  +-------------------+                        | - Document Service Layer       |  |
|                                               | - Version Control Engine       |  |
|                                               | - Audit Logger                 |  |
|                                               +---------------+----------------+  |
|                                                               |                   |
|                                                SQL / Storage  |                   |
|                                                               v                   |
|                                               +--------------------------------+  |
|                                               | Infrastructure Layer           |  |
|                                               | - PostgreSQL (Relational Data) |  |
|                                               | - Redis (Tokens & Cache)       |  |
|                                               | - POSIX / Local File Vault     |  |
|                                               +--------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 3. User Roles & Permissions Matrix

VaultDocs enforces a hierarchical Role-Based Access Control (RBAC) model. Permissions are evaluated dynamically against the target document or tenant context.

| Permission / Action | Admin | Manager | Editor | Viewer | Guest |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **System Health & Config Read** | Yes | No | No | No | No |
| **Tenant User Management** | Yes | Yes | No | No | No |
| **View Audit Trail Logs** | Yes | Yes | No | No | No |
| **Upload New Document** | Yes | Yes | Yes | No | No |
| **Create New Version** | Yes | Yes | Yes | No | No |
| **Modify Document Metadata** | Yes | Yes | Yes | No | No |
| **Read / Download Document** | Yes | Yes | Yes | Yes | No |
| **Search Document Catalog** | Yes | Yes | Yes | Yes | No |
| **Soft Delete Document** | Yes | Yes | No | No | No |
| **Purge / Hard Delete Doc** | Yes | No | No | No | No |

---

## 4. Functional Requirements (FR)

### 4.1 Module 1: Authentication & Session Management

#### `FR-AUTH-001`: OAuth2 Bearer JWT Issuance
* **Priority:** Critical (Must Have)
* **Description:** The system shall authenticate registered users using email and password, issuing a signed HS256 JWT access token and opaque refresh token upon successful verification.
* **Acceptance Criteria:** Access tokens expire in 15 minutes; refresh tokens expire in 7 days; passwords must be verified against Argon2id salted hashes.

#### `FR-AUTH-002`: Refresh Token Rotation & Blacklisting
* **Priority:** High (Must Have)
* **Description:** Re-issuing an access token using a refresh token shall automatically invalidate the used refresh token and issue a new refresh token pair stored in Redis.
* **Acceptance Criteria:** Attempting to reuse an invalidated refresh token revokes all active tokens associated with that user session immediately.

#### `FR-AUTH-003`: User Registration & Role Assignment
* **Priority:** High (Must Have)
* **Description:** Admins shall be capable of inviting and creating user accounts with specific assigned roles (`Admin`, `Manager`, `Editor`, `Viewer`).

---

### 4.2 Module 2: Document Lifecycle Engine

#### `FR-DOC-001`: Streamed Multipart Document Upload
* **Priority:** Critical (Must Have)
* **Description:** The system shall ingest document files via HTTP `multipart/form-data` requests in stream mode up to a maximum single file size of 100 MB.
* **Acceptance Criteria:** Memory consumption per upload request must not exceed 20 MB regardless of file size; content SHA-256 hash calculated during stream.

#### `FR-DOC-002`: Document Metadata Management
* **Priority:** High (Must Have)
* **Description:** Each uploaded document shall capture mandatory metadata: title, description, mime type, size in bytes, SHA-256 hash, owner ID, tenant ID, and custom key-value tags.

#### `FR-DOC-003`: Soft Deletion & Recovery Lifecycle
* **Priority:** Medium (Should Have)
* **Description:** Deleting a document shall mark it as `is_deleted = True` and populate `deleted_at`. Deleted documents are excluded from search results but remain recoverable by Admins.

#### `FR-DOC-004`: Hard Purge Authorization
* **Priority:** Medium (Should Have)
* **Description:** System Admins can permanently purge soft-deleted documents, physically deleting binary files from the storage engine and cascade-deleting DB metadata.

---

### 4.3 Module 3: Immutable Document Versioning

#### `FR-VER-001`: Automatic Head Version Incrementing
* **Priority:** Critical (Must Have)
* **Description:** Uploading a revised binary or metadata updates designated as a new version shall create a distinct immutable record with incremented version number (`v1`, `v2`, ...).
* **Acceptance Criteria:** Historical versions are read-only and cannot be altered or overwritten once created.

#### `FR-VER-002`: Point-in-Time Version Download
* **Priority:** High (Must Have)
* **Description:** Authorized users can request and stream any historical version binary payload by explicitly passing `version_id` or `version_number`.

---

### 4.4 Module 4: Search & Indexing Engine

#### `FR-SRCH-001`: Multi-Field Parameterized Search
* **Priority:** High (Must Have)
* **Description:** The system shall filter documents by exact match on owner ID, mime type, tag keys, date ranges, and version status.

#### `FR-SRCH-002`: PostgreSQL Full-Text Keyword Search
* **Priority:** High (Must Have)
* **Description:** The system shall execute weighted keyword searches against document titles, descriptions, and tag values using PostgreSQL `tsvector` and GIN index structures.

---

### 4.5 Module 5: Governance & Audit Trail

#### `FR-AUD-001`: Immutable Audit Log Emission
* **Priority:** Critical (Must Have)
* **Description:** All create, update, read, delete, and access denied events shall automatically emit an audit record containing actor ID, tenant ID, action name, resource target, client IP, timestamp, and status.

---

## 5. Non-Functional Requirements (NFR)

### 5.1 Performance & Scalability (NFR-PERF)

| Req ID | Parameter | Target Benchmark | Verification Method |
| :--- | :--- | :--- | :--- |
| **NFR-PERF-01** | Metadata Read API Latency | p95 < 150ms under 500 RPS | Locust Load Testing |
| **NFR-PERF-02** | Full-Text Search Execution | p95 < 250ms over 1,000,000 document records | Benchmark DB Queries |
| **NFR-PERF-03** | Max Concurrent Connections | 1,000 active WebSocket/HTTP connections per node | Async ASGI benchmarking |
| **NFR-PERF-04** | DB Connection Pooling | Max pool size 20, max overflow 10 per worker process | SQLAlchemy pool metrics |

### 5.2 Security & Compliance (NFR-SEC)

* **`NFR-SEC-01` TLS Encryption in Transit:** All external communication must enforce HTTPS TLS 1.3 encryption.
* **`NFR-SEC-02` Password Hashing Standard:** Passwords stored using Argon2id with memory cost 65536 KB and time cost 3 iterations.
* **`NFR-SEC-03` Storage Encryption at Rest:** Storage layer POSIX files written with file system-level AES-256 encryption.
* **`NFR-SEC-04` OWASP Top 10 Mitigation:** Pydantic strict parsing prevents SQL Injection (via SQLAlchemy parameterized queries), XSS, and broken object-level authorization (BOLA).

### 5.3 Reliability & Availability (NFR-REL)

* **`NFR-REL-01` Service Availability SLA:** System backend API target uptime of 99.9% excluding scheduled maintenance windows.
* **`NFR-REL-02` Database Resilience:** Automated Alembic migration checks verify schema integrity on startup before receiving traffic.

---

## 6. Business Rules & Policy Constraints

* **`BR-001` Document Storage Quotas:** A tenant organization cannot exceed its pre-configured total storage quota (e.g., 50 GB default).
* **`BR-002` Immutability Guarantee:** No API route or direct service method shall permit editing the binary stream of an existing version record.
* **`BR-003` Audit Log Retention:** Audit log entries are strictly append-only and cannot be modified or deleted by any user persona including system Admins.

---

## 7. Technical Risks & Mitigation Strategies

| Risk ID | Identified Risk Description | Impact | Probability | Mitigation Strategy |
| :--- | :--- | :---: | :---: | :--- |
| **TR-01** | High memory consumption during simultaneous large file uploads. | High | Medium | Implement chunked streaming via FastAPI `UploadFile` directly to disk streams without loading entire payload into RAM. |
| **TR-02** | Slow full-text search performance as document table scales past millions of rows. | High | Medium | Utilize PostgreSQL GIN indexes on computed `tsvector` columns; implement Redis query caching for common search parameters. |
| **TR-03** | Redis cache failure or connectivity drop causing authentication outage. | Critical | Low | Fallback to stateless JWT signature validation if Redis session revocation lookup fails or times out. |

---

## 8. System Assumptions & Dependencies

1. **Host Environment:** Operating system supports POSIX file locking and Linux kernel 5.15+ for container runtime execution.
2. **Database System:** PostgreSQL version 17+ is deployed with `pg_trgm` and `unaccent` extensions enabled.
3. **Time Synchronization:** Host servers and container instances execute Network Time Protocol (NTP) synchronization to prevent JWT timestamp skew errors.

---

## 9. Acceptance Criteria Framework

Feature implementation MUST satisfy automated testing criteria before merging:
1. **Unit Test Coverage:** All domain logic and service layer methods must maintain minimum 85% branch coverage.
2. **Integration Test Suite:** All API endpoints verified against test PostgreSQL/Redis test containers using `httpx` async client.
3. **Static Typing & Formatting Compliance:** `mypy --strict` produces zero type error alerts, and `ruff check .` passes without warnings.

---

## 10. Requirements Traceability Matrix (RTM)

| Requirement ID | Module Target | Implementation Layer | Primary Class / Component | Verification Test Case |
| :--- | :--- | :--- | :--- | :--- |
| **FR-AUTH-001** | Auth Module | Presentation / App | `AuthService.login()` | `test_jwt_issuance_success` |
| **FR-AUTH-002** | Auth Module | Application / Infra | `RedisTokenRepository` | `test_refresh_token_rotation` |
| **FR-DOC-001** | Document Module| Infrastructure / App | `POSIXStorageEngine` | `test_stream_file_upload_100mb` |
| **FR-VER-001** | Version Module | Domain / Application | `VersionControlService` | `test_immutable_version_increment` |
| **FR-SRCH-001**| Search Module  | Infrastructure | `PostgresDocumentRepository`| `test_fulltext_search_gin_index` |
| **FR-AUD-001** | Audit Module   | Application / Infra | `AuditLoggingMiddleware` | `test_audit_event_emitted` |
