# VaultDocs — API Design Specification

> **Document ID:** DOC-005
> **Version:** 1.0.0
> **Status:** Approved
> **Author:** Pavan (Software Architect / Project Lead)
> **Contributors:** Raj (Backend Developer), Tirth (Backend Developer)
> **Created Date:** 2026-07-20
> **Last Updated:** 2026-07-20
> **Classification:** Internal Engineering Documentation

---

## Executive Summary

This API Design Specification defines the RESTful interface standards, request/response contracts, authorization mechanics, error formatting rules, pagination schemas, rate-limiting policies, and versioning rules for VaultDocs. The VaultDocs API is designed using **FastAPI** and **Pydantic v2**, adhering to OpenAPI 3.1 standards and strict RFC 7807 error detail conventions.

---

## Table of Contents

1. [REST Architecture & URI Standards](#1-rest-architecture--uri-standards)
2. [HTTP Methods & Status Code Conventions](#2-http-methods--status-code-conventions)
3. [Authentication & Authorization Headers](#3-authentication--authorization-headers)
4. [Pagination, Sorting & Filtering](#4-pagination-sorting--filtering)
5. [Error Handling & RFC 7807 Schema](#5-error-handling--rfc-7807-schema)
6. [Rate Limiting & Throttling](#6-rate-limiting--throttling)
7. [API Route Specifications](#7-api-route-specifications)
8. [API Versioning & Deprecation Policy](#8-api-versioning--deprecation-policy)

---

## 1. REST Architecture & URI Standards

VaultDocs strictly follows REST design principles:

* **Base Endpoint URI:** `https://api.vaultdocs.io/api/v1`
* **Resource Naming:** Nouns in lowercase plural format (e.g., `/documents`, `/users`, `/audit-logs`).
* **Kebab-Case Pathing:** Multi-word URI path segments use kebab-case (`/document-versions`, `/storage-quotas`).
* **JSON Default Format:** All request payloads and response bodies enforce `Content-Type: application/json` (except binary upload/download streams).

---

## 2. HTTP Methods & Status Code Conventions

| Method | Usage Description | Success Status | Idempotent |
| :--- | :--- | :---: | :---: |
| `GET` | Retrieve resource representation or catalog listing | `200 OK` | Yes |
| `POST` | Create new resource (user, document version, login token) | `201 Created` | No |
| `PUT` | Complete resource replacement | `200 OK` | Yes |
| `PATCH` | Partial resource metadata mutation | `200 OK` | No |
| `DELETE` | Remove or soft-delete resource | `200 OK` / `204 No Content` | Yes |

### Standard HTTP Status Codes

* **`200 OK`**: Request succeeded with response body.
* **`201 Created`**: Resource successfully created.
* **`400 Bad Request`**: Malformed payload or validation failure.
* **`401 Unauthorized`**: Missing or invalid Bearer JWT.
* **`403 Forbidden`**: Insufficient RBAC permission.
* **`404 Not Found`**: Resource ID does not exist or soft-deleted.
* **`409 Conflict`**: Conflict with existing state (e.g., email duplicate).
* **`422 Unprocessable Entity`**: Pydantic schema validation error.
* **`429 Too Many Requests`**: Rate limit exceeded.
* **`500 Internal Server Error`**: Unexpected system error.

---

## 3. Authentication & Authorization Headers

All secured routes require an OAuth2 Bearer token passed in the `Authorization` header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### JWT Payload Structure

```json
{
  "sub": "usr_01H123456789",
  "tenant_id": "tnt_01H987654321",
  "role": "Editor",
  "email": "alex@enterprise.com",
  "iat": 1753013000,
  "exp": 1753013900,
  "jti": "tok_01H555555555"
}
```

---

## 4. Pagination, Sorting & Filtering

### 4.1 Query Parameter Standards

* **Pagination:** `page` (default `1`) and `page_size` (default `20`, max `100`).
* **Sorting:** `sort_by` (e.g., `created_at`, `title`) and `sort_order` (`asc` / `desc`).
* **Filtering:** Field-specific parameters (e.g., `mime_type=application/pdf&is_deleted=false`).

### 4.2 Paginated Response Envelope Schema

```json
{
  "items": [
    {
      "id": "doc_01H123456789",
      "title": "Q3 Financial Report",
      "mime_type": "application/pdf",
      "file_size_bytes": 10485760,
      "version_number": 2,
      "created_at": "2026-07-20T12:00:00Z"
    }
  ],
  "pagination": {
    "total_items": 142,
    "page": 1,
    "page_size": 20,
    "total_pages": 8,
    "has_next": true,
    "has_previous": false
  }
}
```

---

## 5. Error Handling & RFC 7807 Schema

All error responses strictly return RFC 7807 Problem Detail structures:

```json
{
  "type": "https://api.vaultdocs.io/errors/permission-denied",
  "title": "Permission Denied",
  "status": 403,
  "detail": "User with role 'Viewer' cannot perform action 'DOCUMENT_DELETE' on resource 'doc_01H123456789'.",
  "instance": "/api/v1/documents/doc_01H123456789",
  "code": "ERR_PERM_DENIED",
  "timestamp": "2026-07-20T12:25:00Z"
}
```

---

## 6. Rate Limiting & Throttling

Rate limiting is enforced per authenticated user / client IP using Redis sliding window counters:

| User Role | Standard Endpoint Limit | File Search Limit | Binary Upload Limit |
| :--- | :---: | :---: | :---: |
| **Admin** | 1,000 req / min | 300 req / min | 100 req / min |
| **Manager / Editor** | 500 req / min | 150 req / min | 50 req / min |
| **Viewer** | 200 req / min | 60 req / min | 0 req / min |

Exceeding limits returns HTTP `429 Too Many Requests` with header `Retry-After: 60`.

---

## 7. API Route Specifications

### 7.1 Module 1: Authentication (`/api/v1/auth`)

* `POST /api/v1/auth/login` — Authenticate credentials, return JWT access & refresh tokens.
* `POST /api/v1/auth/refresh` — Rotate refresh token and issue new JWT token pair.
* `POST /api/v1/auth/logout` — Revoke active refresh token in Redis.

### 7.2 Module 2: Document Management (`/api/v1/documents`)

* `POST /api/v1/documents/upload` — Ingest binary stream via multipart form and commit metadata.
* `GET /api/v1/documents` — Query paginated catalog of tenant documents.
* `GET /api/v1/documents/{id}` — Fetch detailed document metadata and head version info.
* `PATCH /api/v1/documents/{id}` — Update document title, description, or tags.
* `DELETE /api/v1/documents/{id}` — Soft-delete document.
* `POST /api/v1/documents/{id}/purge` — Hard-purge document (Admin only).

### 7.3 Module 3: Document Versions (`/api/v1/documents/{id}/versions`)

* `GET /api/v1/documents/{id}/versions` — List historical version records for a document.
* `POST /api/v1/documents/{id}/versions` — Upload revised binary stream to create new version.
* `GET /api/v1/documents/{id}/versions/{version_id}/download` — Stream version binary content.

### 7.4 Module 4: Search & Audit (`/api/v1/search`, `/api/v1/audit-logs`)

* `GET /api/v1/search` — Full-text keyword search and filter query.
* `GET /api/v1/audit-logs` — Query system compliance audit trail (Admin/Manager only).

---

## 8. API Versioning & Deprecation Policy

1. **URI Path Versioning:** All API endpoints prefix major version numbers in the URL path (`/api/v1/`).
2. **Backward Compatibility Guarantee:** Breaking schema updates require a new major version path (e.g., `/api/v2/`).
3. **Deprecation Header Notice:** Deprecated endpoints return `Sunset: Wed, 11 Nov 2026 00:00:00 GMT` and `Deprecation: @1762819200` headers.
