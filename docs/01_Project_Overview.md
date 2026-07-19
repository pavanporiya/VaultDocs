# VaultDocs — Project Overview

> **Document ID:** DOC-001  
> **Version:** 1.0  
> **Status:** Approved  
> **Author:** Pavan — Software Architect / Project Lead  
> **Created:** 2026-07-19  
> **Last Updated:** 2026-07-19  
> **Classification:** Internal — Engineering Team

---

## Table of Contents

1. [Project Introduction](#1-project-introduction)
2. [Project Vision](#2-project-vision)
3. [Project Description](#3-project-description)
4. [Problem Statement](#4-problem-statement)
5. [Objectives](#5-objectives)
6. [Project Scope](#6-project-scope)
7. [Target Users](#7-target-users)
8. [Core Features](#8-core-features)
9. [Functional Requirements](#9-functional-requirements)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Technology Stack](#11-technology-stack)
12. [Architecture Overview](#12-architecture-overview)
13. [Development Methodology](#13-development-methodology)
14. [Repository Strategy](#14-repository-strategy)
15. [Team Responsibilities](#15-team-responsibilities)
16. [Definition of Done](#16-definition-of-done)
17. [Project Success Criteria](#17-project-success-criteria)
18. [Future Enhancements](#18-future-enhancements)
19. [Conclusion](#19-conclusion)

---

## 1. Project Introduction

**VaultDocs** is an enterprise-grade, secure document management system designed from the ground up to address the growing demand for reliable, auditable, and access-controlled document storage within organizations of varying scales. The platform enables teams and individuals to upload, organize, share, and version documents through a structured and permission-aware interface, backed by a robust API layer.

This project is developed under professional software engineering practices—following Clean Architecture principles, a Modular Monolith structure, and an Agile Scrum development methodology. Every aspect of VaultDocs, from repository management to deployment strategy, is built to the same standards expected in production-grade enterprise software.

The system is being built by a team of three engineers, each with clearly defined responsibilities. Development follows a structured sprint cycle with mandatory code reviews, pull request workflows, and protected branch policies. No code reaches production without review and explicit approval from the project lead.

VaultDocs is not a proof-of-concept or a prototype. It is a professional product built to solve real problems in document management—prioritizing security, auditability, and developer experience from day one.

---

## 2. Project Vision

> **To build a secure, self-hosted document management platform that gives teams full ownership and control over their documents—without relying on third-party cloud providers for core functionality.**

Most document management solutions today either lock organizations into proprietary ecosystems or sacrifice security and auditability for convenience. VaultDocs takes a different approach. The platform is designed for teams that need to know exactly where their documents live, who accessed them, when changes were made, and what permissions govern every interaction.

The long-term vision for VaultDocs is to evolve into a comprehensive document operations platform—supporting not just storage and retrieval, but intelligent search, automated summarization, optical character recognition, and seamless integration with the tools teams already use. However, the foundation must be right first: secure authentication, granular access control, reliable versioning, and a clean API surface that can sustain years of development without accumulating technical debt.

VaultDocs is built with the belief that document management infrastructure should be transparent, auditable, and fully under the control of the teams that depend on it.

---

## 3. Project Description

VaultDocs provides a backend-first document management platform that exposes its capabilities through a RESTful API. The system supports the full document lifecycle—from upload and organization to sharing, versioning, and eventual archival. Every operation is governed by a role-based access control model and recorded in a tamper-aware activity log.

At its core, VaultDocs is structured around the following capabilities:

- **Document Storage and Organization:** Users can upload documents and organize them within a hierarchical folder structure. Each folder and document can have its own access permissions independent of parent containers.

- **Access Control:** The system implements a role-based access control (RBAC) model with system-level roles (Admin, Manager, Member) and document-level permissions (Owner, Editor, Viewer). This dual-layer model ensures that organizational roles and per-resource permissions work together without conflict.

- **Document Versioning:** Every document modification creates a new version. Users can view version history, compare changes, and roll back to any previous version. Version metadata includes timestamps, authoring information, and optional change descriptions.

- **Search and Discovery:** Documents are searchable by name, content metadata, tags, and custom attributes. The search subsystem is designed to be replaced by more advanced backends (such as Elasticsearch or AI-powered search) as the platform scales.

- **Activity Logging and Audit Trail:** Every significant action—uploads, downloads, permission changes, deletions, sharing events—is recorded in an immutable activity log. This log supports compliance requirements and operational debugging.

- **Notifications:** Users receive notifications for events relevant to them: documents shared with them, access requests, version updates on documents they follow, and administrative alerts.

The backend is built using Python and FastAPI, with PostgreSQL as the primary data store, SQLAlchemy as the ORM layer, and Alembic for database migrations. The project is containerized using Docker and uses GitHub Actions for continuous integration and delivery.

---

## 4. Problem Statement

Document management remains a surprisingly fragmented and poorly solved problem across the software industry. While large enterprises have access to platforms like SharePoint, Documentum, or Box, these solutions are expensive, opaque, and deeply tied to specific cloud ecosystems. For smaller teams, startups, freelancers, and educational institutions, the situation is often worse—documents end up scattered across email threads, local file systems, shared drives, and chat applications with no centralized governance.

### The specific problems VaultDocs addresses:

**Lack of Centralized Document Storage**

Teams frequently operate without a single source of truth for their documents. Project files live in Google Drive, contracts sit in email attachments, technical specifications exist only on individual laptops. When a team member leaves or a machine fails, critical documents are lost. There is no structured repository where documents are stored, indexed, and protected.

**No Meaningful Access Control**

Most lightweight document sharing solutions—shared folders, email attachments, cloud storage links—operate on an all-or-nothing access model. Either a document is shared with everyone, or it is not shared at all. There is rarely a way to grant view-only access to one user and edit access to another, or to revoke permissions after a project concludes. Sensitive documents are routinely over-shared because the tools do not support granular permissions.

**Absent Version History**

When documents are passed around via email or stored on local file systems, version control is nonexistent. Teams resort to naming conventions like `report_v2_final_FINAL.pdf` because their tools do not track changes automatically. When conflicting edits are made, there is no way to determine which version is authoritative or to recover earlier drafts.

**No Audit Trail**

In many environments, there is no record of who accessed a document, when it was modified, or whether it was downloaded. This creates compliance risks for organizations operating under data governance regulations (GDPR, HIPAA, SOX) and makes it impossible to investigate data breaches or unauthorized access after the fact.

**Vendor Lock-in and Data Sovereignty Concerns**

Organizations that rely on third-party cloud platforms for document management cede control over where their data is stored, how it is processed, and who can access it. For teams operating in regulated industries or geographies with strict data residency requirements, this is unacceptable. A self-hosted solution ensures that data never leaves the organization's infrastructure unless explicitly configured to do so.

**Poor Developer Experience in Existing Solutions**

Many document management platforms are designed exclusively for end-users and offer no API surface for programmatic access. Development teams that need to integrate document workflows into their own applications—automated report generation, CI/CD artifact storage, compliance documentation pipelines—are left building custom solutions from scratch.

VaultDocs exists to solve these problems with a clean, well-documented API, transparent access control, automatic versioning, and complete auditability—all running on infrastructure the team owns and controls.

---

## 5. Objectives

### 5.1 Short-Term Objectives (MVP — Sprint 1 through Sprint 4)

| # | Objective | Target Sprint |
|---|-----------|---------------|
| 1 | Implement secure user registration and authentication using JWT tokens with refresh token rotation | Sprint 1 |
| 2 | Build role-based access control with system-level roles (Admin, Manager, Member) | Sprint 1 |
| 3 | Implement hierarchical folder management with CRUD operations | Sprint 2 |
| 4 | Build document upload, download, and deletion with file validation and size limits | Sprint 2 |
| 5 | Implement document versioning with version history and rollback capability | Sprint 3 |
| 6 | Build document sharing with granular per-document permissions (Owner, Editor, Viewer) | Sprint 3 |
| 7 | Implement full-text search across document metadata and tags | Sprint 4 |
| 8 | Build activity logging for all significant user and system actions | Sprint 4 |
| 9 | Implement user dashboard with document statistics and recent activity | Sprint 4 |
| 10 | Achieve 80% minimum test coverage across all modules | Ongoing |

### 5.2 Long-Term Objectives (Post-MVP — Sprint 5 and Beyond)

| # | Objective | Priority |
|---|-----------|----------|
| 1 | Add notification system for document events (share, update, access request) | High |
| 2 | Implement document tagging and categorization for advanced organization | High |
| 3 | Build administrative panel for user management and system configuration | Medium |
| 4 | Integrate OCR for extracting text from scanned documents and images | Medium |
| 5 | Add support for cloud storage backends (AWS S3, MinIO) | Medium |
| 6 | Implement AI-powered document search and retrieval | Low |
| 7 | Build AI-driven document summarization | Low |
| 8 | Develop a mobile-friendly frontend or native mobile application | Low |
| 9 | Integrate with third-party platforms (Slack, Google Drive, Dropbox) | Low |
| 10 | Build a plugin system for extending platform capabilities | Low |

---

## 6. Project Scope

### 6.1 In Scope

The following capabilities and deliverables are within the scope of VaultDocs for the initial release:

- **User Authentication and Session Management** — Registration, login, logout, JWT-based access tokens, refresh token rotation, and password reset flows.

- **User Management** — User profiles, role assignment, account activation/deactivation, and administrative user operations.

- **Folder Management** — Create, rename, move, and delete folders. Hierarchical nesting. Per-folder access permissions.

- **Document Upload and Storage** — Upload documents up to 100 MB. Support for common document formats (PDF, DOCX, XLSX, PPTX, TXT, CSV, images). Local filesystem storage with abstracted storage interface for future cloud migration.

- **Document Versioning** — Automatic version creation on document updates. Version history retrieval. Rollback to any previous version.

- **Document Sharing** — Share documents and folders with specific users. Assign per-resource permissions (Owner, Editor, Viewer). Revoke sharing at any time.

- **Role-Based Access Control** — System-level roles governing platform-wide permissions. Document-level permissions governing per-resource access. Permission inheritance within folder hierarchies.

- **Search** — Search documents by name, tags, metadata, and content type. Filterable and sortable results.

- **Activity Logs** — Record all significant operations with timestamps, actor identification, resource references, and action types. Query and filter activity logs.

- **User Dashboard** — Aggregate statistics for each user: total documents, storage used, recent uploads, recent activity.

- **Notifications** — In-app notifications for sharing events, access requests, and document updates.

- **API Documentation** — Auto-generated OpenAPI (Swagger) documentation for every endpoint.

- **Containerized Deployment** — Docker and Docker Compose configuration for local development and production deployment.

- **CI/CD Pipeline** — GitHub Actions workflows for automated linting, type checking, testing, and deployment.

### 6.2 Out of Scope

The following items are explicitly excluded from the initial release and will be considered for future development phases:

- Frontend web application (the initial release is API-only; frontend development is planned for a later phase)
- Mobile applications (iOS, Android)
- End-to-end encryption of documents at rest (standard encryption at the storage layer is in scope; client-side E2E encryption is not)
- Real-time collaborative editing (Google Docs-style concurrent editing)
- OCR and text extraction from scanned documents
- AI-powered search, summarization, or classification
- Integration with third-party services (Slack, Google Drive, Dropbox, OneDrive)
- Multi-tenancy (the initial release supports a single organizational context)
- Payment processing or subscription management
- Email-based document sharing (documents are shared within the platform, not via email delivery)
- Support for documents exceeding 100 MB

---

## 7. Target Users

VaultDocs is designed to serve a broad range of users and organizational contexts. The platform's flexibility in deployment (self-hosted) and access control (role-based, granular) makes it suitable for diverse environments.

### 7.1 Students

Students working on academic projects, theses, and research papers need a structured way to organize their documents. Version history is particularly valuable when iterating on drafts—every revision is preserved, and earlier versions can be recovered without manual backup strategies. Shared folders enable collaborative project work where each team member has clear, permission-controlled access to the relevant documents.

### 7.2 Freelancers

Freelancers manage documents across multiple clients—contracts, deliverables, invoices, briefs, and feedback documents. VaultDocs provides isolated folder structures for each client, with sharing permissions that allow clients to view or download specific deliverables without accessing the freelancer's broader document library. Activity logs offer freelancers proof of delivery and access history when disputes arise.

### 7.3 Small Businesses

Small businesses with 10 to 50 employees often outgrow shared drives and email attachments but cannot justify the cost and complexity of enterprise document management platforms. VaultDocs fills this gap—it provides structured document storage, access control, and audit logging without requiring a dedicated IT team to administer. Role-based access ensures that employees only see documents relevant to their function.

### 7.4 Startups

Engineering teams at startups need a place to store technical documentation, architecture decisions, API specifications, compliance documents, and operational runbooks. VaultDocs serves as an internal document repository that integrates with the development workflow—its API can be called from CI/CD pipelines to store build artifacts, test reports, and deployment logs alongside manually authored documents.

### 7.5 Organizations and Enterprises

Larger organizations benefit from VaultDocs as a self-hosted document management layer that satisfies data residency requirements and internal compliance mandates. The audit trail provides the documentation necessary for regulatory reviews. Role-based access control maps cleanly to organizational hierarchies, and the API surface supports integration with internal tools and automation systems.

---

## 8. Core Features

This section describes every planned feature of VaultDocs in detail, covering both the user-facing behavior and the underlying system behavior.

### 8.1 Authentication

VaultDocs implements a stateless, token-based authentication system using JSON Web Tokens (JWT).

- **Registration:** New users register with an email address and a password. Passwords are hashed using bcrypt before storage. Email uniqueness is enforced at the database level. Upon successful registration, the system returns a JWT access token and a refresh token.

- **Login:** Users authenticate with their email and password. On successful credential validation, the system issues a short-lived access token (15 minutes) and a long-lived refresh token (7 days). The access token is included in the `Authorization` header of subsequent API requests.

- **Token Refresh:** When an access token expires, the client presents the refresh token to obtain a new access token without requiring the user to re-enter credentials. Refresh tokens are rotated on each use—the old token is invalidated and a new one is issued—to mitigate token theft.

- **Logout:** Logout invalidates the current refresh token, preventing further token renewal. Access tokens remain valid until their natural expiration (15 minutes maximum), which is an acceptable tradeoff for avoiding the complexity and latency of server-side token blacklists.

- **Password Reset:** Users can request a password reset link sent to their registered email. The reset link contains a time-limited, single-use token. Upon submission of a new password via the reset token, all existing refresh tokens for the user are invalidated.

### 8.2 User Management

The user management module handles user profiles, account states, and administrative operations.

- **User Profiles:** Each user has a profile containing their display name, email address, avatar (optional), registration date, and last login timestamp. Users can update their own profile information.

- **Account States:** User accounts can be in one of three states: Active, Suspended, or Deactivated. Suspended accounts cannot authenticate but retain their data. Deactivated accounts are soft-deleted and are excluded from search results and sharing workflows.

- **Administrative Operations:** Admin users can list all users, search users by name or email, change user roles, suspend or deactivate accounts, and view user activity logs. These operations are restricted to users with the Admin system role.

### 8.3 Folder Management

Folders provide the organizational hierarchy for documents within VaultDocs.

- **Hierarchical Structure:** Folders can be nested to arbitrary depth. Each folder has a reference to its parent folder, enabling tree traversal. Root-level folders have no parent.

- **CRUD Operations:** Users can create, rename, move, and delete folders. Deleting a folder moves it and all its contents (subfolders and documents) to a trash state. Trash items can be restored or permanently purged after a configurable retention period.

- **Permissions Inheritance:** Folder permissions cascade to their children by default. A user with Editor access to a parent folder inherits Editor access to all subfolders and documents within it, unless explicitly overridden at the child level.

- **Folder Metadata:** Each folder stores its name, creation date, last modified date, owner, path (materialized for efficient querying), and size (aggregated from contained documents).

### 8.4 Document Upload

Document upload is the primary entry point for content into VaultDocs.

- **Supported Formats:** PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG, JPEG, GIF, SVG, and other common document and image formats. The allowed format list is configurable at the application level.

- **Size Limits:** Individual files are limited to 100 MB by default. This limit is configurable through environment variables. Uploads exceeding the limit are rejected with a clear error message before any processing occurs.

- **File Validation:** Uploaded files are validated for MIME type consistency (the declared content type must match the actual file content), file extension, and file size. Files with mismatched MIME types are rejected to prevent disguised executable uploads.

- **Storage:** Files are stored on the local filesystem within a structured directory layout organized by user ID and folder path. The storage layer is abstracted behind an interface, allowing future migration to S3-compatible object storage without modifying the domain or application layers.

- **Metadata Extraction:** Upon upload, the system records the filename, file size, MIME type, checksum (SHA-256), upload timestamp, and uploading user.

### 8.5 Document Sharing

Document sharing enables controlled distribution of documents and folders to other users within the platform.

- **Share with Specific Users:** Documents and folders can be shared with individual users by specifying their user ID or email address. Each share includes a permission level: Owner, Editor, or Viewer.

- **Permission Levels:**
  - **Owner:** Full control including deletion, permission management, and sharing with others.
  - **Editor:** Can view, download, and upload new versions. Cannot delete or manage permissions.
  - **Viewer:** Can view and download only. Cannot modify the document or its metadata.

- **Share Revocation:** The document owner or an Admin can revoke any share at any time. Revocation is immediate—subsequent API calls from the revoked user will return 403 Forbidden.

- **Share Links (Future):** Shareable links with optional expiration and password protection are planned for a future release but are out of scope for the initial version.

### 8.6 Role-Based Access Control

VaultDocs implements a dual-layer access control model combining system-level roles with resource-level permissions.

**System-Level Roles:**

| Role | Description |
|------|-------------|
| **Admin** | Full system access. Can manage users, roles, system settings, and all documents regardless of ownership. |
| **Manager** | Can manage users within their scope. Can view activity logs. Cannot modify system settings. |
| **Member** | Standard user role. Can create, upload, share, and manage their own documents and folders. |

**Resource-Level Permissions:**

| Permission | Read | Download | Upload Version | Edit Metadata | Delete | Manage Permissions |
|------------|------|----------|---------------|---------------|--------|--------------------|
| **Owner** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Editor** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| **Viewer** | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |

System roles determine what actions a user can perform at the platform level. Resource permissions determine what a specific user can do with a specific document or folder. Both layers are evaluated on every request—a Member with Owner permission on a document can manage that document fully, but cannot access another user's documents that have not been shared with them.

### 8.7 Version Control

Every document in VaultDocs maintains a complete version history.

- **Automatic Versioning:** When a user uploads a new file to an existing document, the system creates a new version rather than overwriting the previous one. Each version is assigned a sequential version number and a timestamp.

- **Version Metadata:** Each version records the file checksum, file size, upload timestamp, uploading user, and an optional change description provided by the uploader.

- **Version History:** Users can retrieve the complete version history for any document they have access to. The history includes all version metadata and download links for each version.

- **Rollback:** Users with Editor or Owner permissions can roll back a document to any previous version. Rollback creates a new version (with the old content) rather than deleting intermediate versions, preserving the complete audit trail.

- **Storage Efficiency:** Each version is stored as a separate file on disk. Deduplication (storing identical files once regardless of how many versions reference them) is planned for a future release.

### 8.8 Search

VaultDocs provides a search subsystem that allows users to discover documents across their accessible scope.

- **Search Scope:** Search results are filtered by the requesting user's permissions. A user will never see documents in search results that they do not have at least Viewer access to.

- **Searchable Fields:** Document name, file extension, tags, folder name, uploader name, and custom metadata fields.

- **Filters:** Results can be filtered by file type, date range (created, modified), size range, owner, and tags.

- **Sorting:** Results can be sorted by relevance, name, date created, date modified, and file size.

- **Pagination:** Search results are paginated using cursor-based pagination for consistent results across large datasets.

- **Implementation:** The initial implementation uses PostgreSQL full-text search with `tsvector` and `tsquery`. This provides adequate performance for datasets up to approximately 100,000 documents. For larger scales, the search interface is designed to allow transparent replacement with Elasticsearch or Meilisearch.

### 8.9 Activity Logs

The activity log subsystem provides a complete, tamper-aware record of all significant actions within the platform.

- **Recorded Events:** User registration, login, logout, document upload, document download, document deletion, folder creation, folder deletion, permission changes, share creation, share revocation, role changes, and administrative operations.

- **Log Entry Structure:** Each log entry contains the action type, the acting user, the target resource (if applicable), a timestamp, the request IP address, and a human-readable description of the action.

- **Immutability:** Activity log entries are append-only. They cannot be modified or deleted through the API, even by Admin users. Database-level protections (no UPDATE or DELETE permissions on the activity log table for the application database user) reinforce this guarantee.

- **Querying:** Activity logs can be queried by user, action type, resource, and date range. Results are paginated.

- **Retention:** Activity logs are retained indefinitely by default. A configurable retention policy for archiving or purging old entries will be available in a future release.

### 8.10 Dashboard

The user dashboard provides an at-a-glance summary of each user's document management activity.

- **Document Statistics:** Total documents owned, total documents shared with the user, total storage consumed, number of folders.

- **Recent Activity:** The last 20 activities performed by the user or on resources the user owns.

- **Recent Documents:** The 10 most recently uploaded or modified documents accessible to the user.

- **Storage Quota (Future):** Display of storage used versus allocated quota. Quotas are planned for a future release.

- **Admin Dashboard:** Admin users have access to an extended dashboard showing system-wide statistics: total users, total documents, total storage consumed, active sessions, and recent system events.

### 8.11 Notifications

The notification system alerts users to events that require their attention.

- **Notification Events:**
  - A document or folder was shared with the user.
  - A document the user owns was updated (new version uploaded).
  - A user requested access to a document the user owns.
  - An admin performed an action affecting the user's account.

- **Delivery:** Notifications are delivered in-app through a notifications API endpoint. The user can retrieve unread notifications, mark notifications as read, and dismiss notifications.

- **Persistence:** Notifications are stored in the database with a read/unread flag. Dismissed notifications are soft-deleted.

- **Future Delivery Channels:** Email notifications and webhook-based notifications are planned for future releases.

---

## 9. Functional Requirements

This section enumerates the functional requirements of VaultDocs, organized by domain area. Each requirement is identified by a unique code for traceability throughout the project lifecycle.

### 9.1 Authentication and Authorization

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-AUTH-001 | The system shall allow users to register with a unique email address and a password meeting minimum complexity requirements (8+ characters, at least one uppercase, one lowercase, one digit, one special character). | Must Have |
| FR-AUTH-002 | The system shall authenticate users via email and password, returning a JWT access token and a refresh token upon successful authentication. | Must Have |
| FR-AUTH-003 | The system shall support token refresh using a valid refresh token, issuing a new access token and rotating the refresh token. | Must Have |
| FR-AUTH-004 | The system shall invalidate refresh tokens upon user logout. | Must Have |
| FR-AUTH-005 | The system shall support password reset via a time-limited, single-use reset token sent to the user's registered email. | Should Have |
| FR-AUTH-006 | The system shall enforce role-based access control on all API endpoints, rejecting unauthorized requests with appropriate HTTP status codes. | Must Have |

### 9.2 User Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-USER-001 | The system shall maintain a user profile for each registered user, including display name, email, avatar URL, registration date, and last login timestamp. | Must Have |
| FR-USER-002 | The system shall allow users to update their own profile information (display name, avatar). | Must Have |
| FR-USER-003 | The system shall allow Admin users to list, search, suspend, deactivate, and change roles of other users. | Must Have |
| FR-USER-004 | The system shall prevent suspended users from authenticating while retaining their data and document associations. | Must Have |
| FR-USER-005 | The system shall soft-delete deactivated users, removing them from search and sharing workflows while preserving their data for potential restoration. | Should Have |

### 9.3 Folder Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-FOLD-001 | The system shall allow users to create folders at the root level or nested within existing folders. | Must Have |
| FR-FOLD-002 | The system shall allow users to rename and move folders within their accessible scope. | Must Have |
| FR-FOLD-003 | The system shall cascade permissions from parent folders to child folders and documents by default, with optional per-resource overrides. | Must Have |
| FR-FOLD-004 | The system shall soft-delete folders and their contents, supporting restoration within a configurable retention window. | Should Have |

### 9.4 Document Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DOC-001 | The system shall allow users to upload documents up to 100 MB in supported formats. | Must Have |
| FR-DOC-002 | The system shall validate uploaded files for MIME type consistency, file extension, and file size before accepting them. | Must Have |
| FR-DOC-003 | The system shall create a new version each time an existing document is updated, preserving all previous versions. | Must Have |
| FR-DOC-004 | The system shall allow users to view version history and download any previous version of a document. | Must Have |
| FR-DOC-005 | The system shall allow users with Editor or Owner permissions to roll back a document to any previous version. | Must Have |
| FR-DOC-006 | The system shall allow users to download documents they have at least Viewer access to. | Must Have |
| FR-DOC-007 | The system shall soft-delete documents, supporting restoration within a configurable retention window. | Should Have |

### 9.5 Sharing and Permissions

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SHARE-001 | The system shall allow document and folder owners to share resources with specific users, assigning a permission level (Owner, Editor, Viewer). | Must Have |
| FR-SHARE-002 | The system shall allow owners and Admins to revoke sharing permissions at any time, with immediate effect. | Must Have |
| FR-SHARE-003 | The system shall enforce resource-level permissions on every document and folder operation. | Must Have |
| FR-SHARE-004 | The system shall allow users to view a list of all resources shared with them. | Must Have |

### 9.6 Search

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SRCH-001 | The system shall provide full-text search across document names, tags, and metadata fields. | Must Have |
| FR-SRCH-002 | The system shall filter search results to include only resources the requesting user has access to. | Must Have |
| FR-SRCH-003 | The system shall support filtering by file type, date range, size range, owner, and tags. | Should Have |
| FR-SRCH-004 | The system shall support cursor-based pagination for search results. | Must Have |

### 9.7 Activity Logs

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-LOG-001 | The system shall record all significant user and system actions in an append-only activity log. | Must Have |
| FR-LOG-002 | The system shall store the acting user, target resource, action type, timestamp, and IP address for each log entry. | Must Have |
| FR-LOG-003 | The system shall provide an API for querying activity logs with filters for user, action type, resource, and date range. | Must Have |
| FR-LOG-004 | The system shall prevent modification or deletion of activity log entries through the API. | Must Have |

### 9.8 Dashboard and Notifications

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-DASH-001 | The system shall provide a user dashboard showing document count, storage usage, and recent activity. | Should Have |
| FR-DASH-002 | The system shall provide an admin dashboard showing system-wide statistics. | Should Have |
| FR-NOTF-001 | The system shall generate in-app notifications for sharing events, document updates, and administrative actions. | Should Have |
| FR-NOTF-002 | The system shall allow users to retrieve, mark as read, and dismiss notifications. | Should Have |

---

## 10. Non-Functional Requirements

### 10.1 Performance

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| API response time (p50) | < 100 ms | Load testing with Locust / k6 |
| API response time (p95) | < 200 ms | Load testing with Locust / k6 |
| API response time (p99) | < 500 ms | Load testing with Locust / k6 |
| Document upload throughput (100 MB file) | < 10 seconds | Manual benchmark on target hardware |
| Search query response time | < 300 ms for datasets up to 100K documents | PostgreSQL `EXPLAIN ANALYZE` + load testing |
| Concurrent user support | 10,000 simultaneous connections | Load testing with connection pooling validation |

The system shall use asynchronous request handling (via FastAPI's async support and asyncpg) to maximize throughput under concurrent load. Database queries shall be optimized with proper indexing, query planning, and connection pooling (via SQLAlchemy's async pool).

### 10.2 Security

- All API communication shall occur over HTTPS (TLS 1.2 or higher) in production.
- Passwords shall be hashed using bcrypt with a minimum cost factor of 12.
- JWT tokens shall use RS256 or HS256 signing. Token payloads shall not contain sensitive information (passwords, full user records).
- All user input shall be validated and sanitized at the API boundary using Pydantic models. Raw SQL queries are prohibited; all database interactions go through the ORM.
- File uploads shall be validated for MIME type, extension, and size. Executable files shall be rejected.
- The system shall comply with OWASP Top 10 security guidelines, including protection against SQL injection, XSS (at the API level), CSRF (stateless API mitigates this), and broken authentication.
- Rate limiting shall be applied to authentication endpoints to prevent brute-force attacks.
- All secrets (database credentials, JWT signing keys, API keys) shall be managed via environment variables and never committed to source control.

### 10.3 Scalability

- The system shall be designed as a modular monolith with well-defined module boundaries, enabling extraction of individual modules into independent services if scaling demands require it.
- Database queries shall use indexed columns and avoid N+1 query patterns.
- The storage layer shall be abstracted behind an interface, enabling horizontal scaling via object storage (S3, MinIO) without application code changes.
- The system shall support horizontal scaling of the API layer through containerized deployment behind a load balancer.

### 10.4 Maintainability

- All code shall follow the project's coding standards (enforced by Ruff and mypy).
- The codebase shall maintain a minimum of 80% test coverage, measured by `pytest-cov`.
- Every module shall have clear boundaries, its own models, schemas, services, and API routers. Cross-module dependencies shall flow through well-defined interfaces.
- All public functions, classes, and modules shall have docstrings following Google-style conventions.
- Database schema changes shall be managed exclusively through Alembic migrations. Direct schema modifications to production databases are prohibited.

### 10.5 Reliability

- The system shall handle all errors gracefully, returning structured error responses with appropriate HTTP status codes, error codes, and human-readable messages.
- Failed operations shall not leave the system in an inconsistent state. Database transactions shall be used for multi-step operations, with rollback on failure.
- The system shall implement structured logging (via `structlog`) for all operations, enabling effective debugging and incident response.
- Critical failures shall be logged at the ERROR level with sufficient context for root cause analysis.

### 10.6 Availability

| Metric | Target |
|--------|--------|
| Uptime SLA | 99.9% (approximately 8.7 hours downtime per year) |
| Planned maintenance window | Maximum 30 minutes during off-peak hours |
| Recovery Time Objective (RTO) | < 1 hour |
| Recovery Point Objective (RPO) | < 15 minutes (database backup frequency) |

The system shall support zero-downtime deployments through rolling updates in a containerized environment. Health check endpoints shall be exposed for load balancer and orchestrator integration.

### 10.7 Usability

- The API shall follow RESTful conventions consistently: proper HTTP methods, meaningful status codes, and predictable URL structures.
- All API endpoints shall be documented with auto-generated OpenAPI (Swagger UI) documentation, including request/response schemas, example payloads, and error responses.
- Error messages shall be clear, actionable, and free of internal implementation details.
- API responses shall use consistent envelope structures for both success and error cases.
- Pagination, filtering, and sorting shall follow consistent patterns across all list endpoints.

---

## 11. Technology Stack

Every technology in the VaultDocs stack was selected based on specific technical criteria: maturity, community support, performance characteristics, and alignment with the project's architectural goals. This section explains the rationale behind each selection.

| Technology | Role | Version |
|------------|------|---------|
| Python | Primary programming language | 3.13+ |
| FastAPI | Web framework and API layer | 0.115+ |
| PostgreSQL | Primary relational database | 16+ |
| SQLAlchemy | ORM and database abstraction | 2.0+ |
| Alembic | Database schema migration | 1.14+ |
| Pydantic | Data validation and serialization | 2.10+ |
| JWT (python-jose) | Token-based authentication | 3.3+ |
| Docker | Application containerization | 24+ |
| GitHub Actions | CI/CD pipeline automation | N/A |
| pytest | Testing framework | 8.3+ |
| Ruff | Linting and code formatting | 0.9+ |
| mypy | Static type checking | 1.14+ |
| uv | Python package and project manager | Latest |

### 11.1 Python 3.13

Python is selected as the primary language for its readability, extensive ecosystem, and strong support for asynchronous programming. Python 3.13 brings performance improvements through the ongoing work on the faster CPython initiative, improved error messages, and continued enhancements to the type system. The team has deep Python expertise, reducing onboarding friction and enabling rapid development.

Python's ecosystem provides mature, battle-tested libraries for every layer of the stack—from web frameworks to ORMs to testing tools—which eliminates the need to build or maintain custom infrastructure.

### 11.2 FastAPI

FastAPI is chosen over alternatives like Django REST Framework and Flask for several specific reasons:

- **Async-native:** FastAPI is built on Starlette and natively supports async/await, which is essential for high-concurrency workloads like file uploads and database queries.
- **Automatic OpenAPI documentation:** FastAPI generates Swagger UI and ReDoc documentation from endpoint definitions and Pydantic models without any additional configuration.
- **Pydantic integration:** Request validation, response serialization, and settings management all use Pydantic, eliminating an entire class of data validation bugs.
- **Performance:** FastAPI consistently benchmarks among the fastest Python web frameworks, approaching the performance of Node.js and Go for I/O-bound workloads.
- **Type safety:** FastAPI leverages Python type hints throughout, providing IDE auto-completion, early error detection, and self-documenting code.

Django was considered but rejected due to its monolithic nature, synchronous-first design, and the overhead of its ORM and template system—none of which align with the project's modular, API-only architecture.

### 11.3 PostgreSQL

PostgreSQL is the primary database for VaultDocs due to its reliability, feature set, and extensibility:

- **ACID compliance:** Full transactional support with serializable isolation levels ensures data consistency, which is critical for a system managing document permissions and version history.
- **Full-text search:** PostgreSQL's built-in `tsvector` and `tsquery` provide adequate full-text search for the MVP, eliminating the need for a separate search infrastructure.
- **JSON support:** The `jsonb` column type enables storage of semi-structured metadata without requiring schema changes for every new attribute.
- **Extensibility:** PostgreSQL supports custom types, functions, and extensions. If the project requires advanced capabilities (PostGIS for geolocation, pgvector for AI embeddings), they can be added without migrating databases.
- **Maturity:** PostgreSQL is one of the most thoroughly tested and widely deployed relational databases. It powers critical infrastructure at organizations ranging from startups to Fortune 500 companies.

### 11.4 SQLAlchemy 2.0

SQLAlchemy 2.0 serves as the ORM and database abstraction layer:

- **Async support:** SQLAlchemy 2.0's native async engine and session support, paired with the `asyncpg` driver, enables non-blocking database operations throughout the application.
- **Declarative mapping:** Models are defined as Python classes with type-annotated columns, making the schema self-documenting and compatible with mypy.
- **Query flexibility:** SQLAlchemy supports both ORM-level queries (for most operations) and Core-level queries (for performance-critical operations), providing flexibility without sacrificing safety.
- **Mature ecosystem:** SQLAlchemy is the most widely used Python ORM, with extensive documentation, community support, and integration with tools like Alembic.

### 11.5 Alembic

Alembic manages database schema migrations with version control:

- **Automatic migration generation:** Alembic can auto-generate migration scripts by comparing SQLAlchemy model definitions against the current database schema, reducing manual work and the risk of errors.
- **Reversible migrations:** Every migration includes an `upgrade` and a `downgrade` function, enabling safe rollback if a migration introduces issues.
- **CI/CD integration:** Migration scripts are version-controlled alongside application code, ensuring that database schema changes are reviewed, tested, and deployed through the same pipeline as code changes.

### 11.6 Pydantic v2

Pydantic v2 handles data validation and serialization across the entire application:

- **Performance:** Pydantic v2 is rewritten with a Rust-based core, delivering 5–50x faster validation compared to v1.
- **Strict mode:** Pydantic v2 supports strict type coercion, preventing unintended type conversions that could introduce bugs.
- **Settings management:** `pydantic-settings` provides type-safe configuration management, reading from environment variables, `.env` files, and secrets files with validation.

### 11.7 JWT (python-jose)

JWT-based authentication is selected over session-based authentication for the following reasons:

- **Stateless:** JWT tokens are self-contained, meaning the server does not need to maintain session state. This simplifies horizontal scaling since any API instance can validate any token.
- **Standard:** JWT is an open standard (RFC 7519) supported by every major programming language and framework, making future frontend and mobile integrations straightforward.
- **Granular claims:** JWT payloads can carry user identity, roles, and custom claims, reducing the need for additional database lookups on every request.

### 11.8 Docker

Docker is used for both development and production environments:

- **Environment parity:** Docker ensures that the application runs in identical environments across development, CI/CD, staging, and production, eliminating "works on my machine" issues.
- **Dependency isolation:** The application and its dependencies (PostgreSQL, Redis for future use) run in isolated containers, preventing conflicts with host system packages.
- **Reproducible builds:** Docker images are built from explicit `Dockerfile` definitions, ensuring that every build produces the same result.
- **Orchestration readiness:** Docker containers are the deployment unit for orchestration platforms (Docker Compose for development, Kubernetes for production-scale deployment).

### 11.9 GitHub Actions

GitHub Actions is selected for CI/CD due to its native integration with the project's GitHub repository:

- **Zero infrastructure:** Workflows run on GitHub-hosted runners, eliminating the need to provision and maintain CI/CD servers.
- **Native integration:** Workflows trigger on push, pull request, and other GitHub events. Status checks gate pull request merges.
- **Marketplace:** Pre-built actions for Python setup, Docker builds, linting, and deployment are available in the GitHub Actions Marketplace.
- **Secrets management:** GitHub Actions provides encrypted secrets storage for database credentials, API keys, and deployment tokens.

### 11.10 pytest

pytest is the testing framework for all unit, integration, and end-to-end tests:

- **Fixture system:** pytest's fixture mechanism provides dependency injection for test setup and teardown, enabling clean and reusable test infrastructure.
- **Plugin ecosystem:** `pytest-asyncio` for async tests, `pytest-cov` for coverage reporting, `pytest-mock` for mocking, and `factory-boy` for test data generation.
- **Assertion introspection:** pytest rewrites assertions to provide detailed failure messages without requiring custom assertion methods.

### 11.11 Ruff

Ruff replaces multiple linting and formatting tools (flake8, isort, black, pyupgrade) with a single, fast tool:

- **Speed:** Ruff is written in Rust and is 10–100x faster than the Python-based tools it replaces.
- **Unified tooling:** A single configuration in `pyproject.toml` governs linting rules, import sorting, and code formatting.
- **Comprehensive rules:** Ruff supports rules from flake8, isort, pyupgrade, pyflakes, and many other plugins—all in one tool.

### 11.12 mypy

mypy provides static type checking for the entire codebase:

- **Bug prevention:** Type checking catches type errors, missing return values, and incorrect function signatures before the code runs.
- **Documentation:** Type annotations serve as machine-verifiable documentation of function contracts and data structures.
- **Strict mode:** The project uses mypy in strict mode, requiring type annotations on all function parameters and return values. This maximizes the effectiveness of type checking.

### 11.13 uv

uv is selected as the Python package and project manager over pip and Poetry:

- **Speed:** uv is written in Rust and resolves and installs packages 10–100x faster than pip.
- **Lockfile support:** `uv.lock` provides deterministic dependency resolution, ensuring that every team member and CI environment uses the exact same package versions.
- **All-in-one tool:** uv handles Python version management, virtual environment creation, package installation, and script execution—replacing multiple separate tools.
- **pip-compatible:** uv supports the standard `pyproject.toml` format and can read `requirements.txt` files, ensuring compatibility with existing Python tooling.

---

## 12. Architecture Overview

### 12.1 Architectural Pattern: Modular Monolith

VaultDocs follows a **Modular Monolith** architecture rather than a Microservices architecture. This is a deliberate decision based on the team size, project maturity, and operational complexity considerations.

#### What is a Modular Monolith?

A Modular Monolith is a single deployable application organized into well-defined, loosely coupled modules. Each module owns its domain logic, data models, and API surface. Modules communicate through explicit interfaces (function calls, in-process events, or a mediator pattern) rather than through shared database tables or implicit coupling.

The key distinction from a traditional monolith is the enforcement of module boundaries. In VaultDocs, the `auth` module cannot directly import models from the `documents` module. Cross-module communication flows through defined interfaces, making it possible to extract any module into an independent service if scaling requirements demand it.

#### Why Not Microservices?

Microservices introduce operational complexity that is disproportionate to the current scale of VaultDocs:

| Concern | Microservices Impact | Modular Monolith Impact |
|---------|---------------------|------------------------|
| **Deployment complexity** | Each service requires its own deployment pipeline, health checks, and scaling configuration. | Single deployment artifact. One pipeline. |
| **Inter-service communication** | Requires network calls (HTTP, gRPC, message queues) between services, introducing latency, failure modes, and distributed transaction challenges. | In-process function calls. No network overhead. No distributed transactions. |
| **Data consistency** | Each service owns its database, making cross-service queries and transactions difficult. Eventual consistency patterns (sagas, outbox) add significant complexity. | Shared database with clear schema ownership per module. ACID transactions across modules when needed. |
| **Observability** | Distributed tracing (Jaeger, Zipkin) is required to follow a request across services. Correlating logs from multiple services requires centralized logging infrastructure. | Single process. Standard logging. No distributed tracing required. |
| **Team size** | Microservices are designed for large teams (5+ engineers per service) where independent deployment velocity matters. | A team of 3 engineers does not benefit from the isolation that microservices provide. |
| **Infrastructure cost** | Each service requires its own container, memory allocation, and scaling policy. | Single container. Efficient resource usage. |

#### Advantages of the Modular Monolith for VaultDocs

1. **Simplicity of development:** Developers work in a single codebase with a single set of dependencies. There is no need to run multiple services locally or coordinate deployments across repositories.

2. **Refactoring safety:** Since all modules exist in the same codebase, refactoring is supported by the type checker and test suite. Renaming an interface that spans two modules is a single commit, not a coordinated release across two services.

3. **Transaction integrity:** Operations that span multiple domains (e.g., creating a document and recording an activity log entry) can use a single database transaction, guaranteeing atomicity without the complexity of distributed saga patterns.

4. **Migration path:** The modular structure ensures that if VaultDocs grows to a scale where microservices are justified, any module can be extracted into an independent service. The inter-module interfaces already define the contract that would become the service API.

5. **Faster iteration:** In the early stages of a product, requirements change frequently. A modular monolith allows rapid iteration without the overhead of updating API contracts between services, managing schema compatibility, or coordinating deployments.

### 12.2 Clean Architecture Layers

Within each module, VaultDocs follows Clean Architecture principles with four distinct layers:

```
┌────────────────────────────────────────┐
│         Presentation (API)             │  ← FastAPI routers, request/response schemas
├────────────────────────────────────────┤
│         Application (Use Cases)        │  ← Business workflows, orchestration
├────────────────────────────────────────┤
│         Domain (Business Rules)        │  ← Entities, value objects, domain events
├────────────────────────────────────────┤
│   Infrastructure (DB, Storage, Email)  │  ← Repositories, external service adapters
└────────────────────────────────────────┘
```

**Dependency Rule:** Dependencies flow inward. The Domain layer has no external dependencies. The Application layer depends only on the Domain layer. The Infrastructure layer implements interfaces defined in the Application layer. The Presentation layer calls the Application layer.

This structure ensures that business logic is isolated from framework and infrastructure concerns, making the codebase testable, maintainable, and adaptable to changing requirements.

---

## 13. Development Methodology

### 13.1 Agile Scrum

VaultDocs is developed using Agile Scrum methodology. Scrum is selected over alternatives (Kanban, Waterfall, XP) for the following reasons:

- **Predictable delivery cadence:** Two-week sprints provide regular checkpoints for progress assessment, stakeholder demos, and priority adjustment.
- **Clear accountability:** Each sprint has defined goals, a sprint backlog, and a definition of done. Every team member knows what they are responsible for.
- **Iterative refinement:** At the end of each sprint, the team reviews what was built, what went well, and what needs improvement. This feedback loop prevents technical debt from accumulating unchecked.
- **Right-sized for a team of 3:** Scrum ceremonies (planning, daily standups, review, retrospective) are lightweight enough for a small team while providing sufficient structure to prevent ad hoc development.

### 13.2 Sprint Planning

Sprint planning occurs at the beginning of each two-week sprint. The process follows these steps:

1. **Backlog Grooming:** The Project Lead (Pavan) reviews the product backlog and identifies the highest-priority items for the upcoming sprint. Items are described as user stories or technical tasks with acceptance criteria.

2. **Estimation:** The team estimates each item using story points based on complexity, effort, and risk. The team's velocity from previous sprints informs how many points can be committed.

3. **Sprint Backlog Creation:** The team selects items from the prioritized backlog until the sprint capacity is reached. Each item is assigned to a developer (Raj or Tirth) based on expertise and workload balance.

4. **Task Breakdown:** Each sprint backlog item is broken into implementation tasks small enough to be completed in 1–2 days. Tasks are tracked on a GitHub Projects board with columns: Backlog, In Progress, In Review, Done.

5. **Sprint Goal:** A concise statement summarizing what the sprint aims to deliver. For example: "Implement user authentication and role-based access control for all API endpoints."

### 13.3 Daily Development

Daily development follows a structured workflow:

1. **Pull latest changes:** Developers sync their feature branches with the `develop` branch at the start of each working session to avoid merge conflicts.

2. **Work on assigned tasks:** Each developer works on their assigned tasks within their feature branch. Commits follow Conventional Commit conventions.

3. **Write tests:** Every feature is accompanied by unit tests and, where applicable, integration tests. Tests are written alongside the implementation, not as an afterthought.

4. **Run checks locally:** Before pushing, developers run the full check suite locally:
   - `ruff check .` — Linting
   - `ruff format --check .` — Formatting
   - `mypy .` — Type checking
   - `pytest` — Tests

5. **Push and create Pull Request:** Once the task is complete and all checks pass, the developer pushes their branch and opens a Pull Request against `develop`.

### 13.4 Pull Requests

Pull Requests (PRs) are the mechanism through which all code enters the protected branches (`develop`, `main`). The PR process is designed to enforce quality, encourage knowledge sharing, and prevent defects.

**PR Requirements:**

- Every PR must have a descriptive title following Conventional Commit conventions.
- The PR description must include: what was changed, why it was changed, how to test it, and any relevant screenshots or API examples.
- Every PR must pass all CI checks (linting, type checking, tests) before review.
- Every PR must be reviewed and approved by the Project Lead (Pavan) before merging.
- PRs should be small and focused. A single PR should address a single task or user story. Large PRs that combine multiple unrelated changes will be rejected and asked to be split.

**PR Review Criteria:**

- Code follows the project's coding standards.
- All new functionality has corresponding tests.
- No security vulnerabilities are introduced.
- No unnecessary complexity or over-engineering.
- Clear, meaningful commit messages.
- Documentation is updated if the change affects API contracts or architectural decisions.

### 13.5 Code Reviews

Code reviews serve three purposes in VaultDocs:

1. **Quality assurance:** The reviewer verifies that the code is correct, handles edge cases, follows the project's patterns, and does not introduce regressions.

2. **Knowledge sharing:** Reviews ensure that at least two team members understand every piece of code in the system. This eliminates single points of failure in team knowledge.

3. **Mentorship:** Reviews are an opportunity for the reviewer to share best practices, suggest improvements, and help developers grow. Review comments should be constructive and educational, never dismissive.

The Project Lead (Pavan) is the required reviewer for all PRs targeting `develop` and `main`. In addition, Raj and Tirth are encouraged to review each other's PRs to broaden their understanding of the codebase.

---

## 14. Repository Strategy

### 14.1 Git Flow

VaultDocs uses a Git Flow branching model adapted for a small team. The branching strategy provides clear separation between development, release preparation, and production code.

**Branch Types:**

| Branch | Purpose | Created From | Merges Into | Protected |
|--------|---------|-------------|-------------|-----------|
| `main` | Production-ready code. Every commit on `main` is a deployable release. | `release/*` or `hotfix/*` | — | Yes |
| `develop` | Integration branch for completed features. Always contains the latest delivered code. | `main` (initial) | `release/*` | Yes |
| `feature/*` | Development of new features. Named `feature/short-description` (e.g., `feature/user-authentication`). | `develop` | `develop` | No |
| `bugfix/*` | Fixing bugs discovered during development. Named `bugfix/short-description`. | `develop` | `develop` | No |
| `hotfix/*` | Urgent fixes for production issues. Named `hotfix/short-description`. | `main` | `main` and `develop` | No |
| `release/*` | Release preparation. Final testing, version bumps, changelog updates. Named `release/v1.0.0`. | `develop` | `main` and `develop` | No |

### 14.2 Branch Lifecycle

**Feature Development:**
```
develop → feature/user-authentication → Pull Request → develop
```
1. Developer creates `feature/user-authentication` from `develop`.
2. Developer implements the feature, commits, and pushes.
3. Developer opens a Pull Request targeting `develop`.
4. CI runs all checks. Project Lead reviews the code.
5. On approval, the Project Lead merges the PR into `develop` (squash merge preferred for clean history).
6. The feature branch is deleted after merge.

**Release:**
```
develop → release/v1.0.0 → Pull Request → main (and back-merge to develop)
```
1. When `develop` contains all features planned for the release, a `release/v1.0.0` branch is created.
2. On the release branch, only bug fixes, version bumps, and changelog updates are allowed. No new features.
3. Once ready, a Pull Request is opened targeting `main`. After approval, the release is merged.
4. The `main` branch is tagged with the version number (e.g., `v1.0.0`).
5. The release branch is merged back into `develop` to incorporate any fixes made during release preparation.
6. The release branch is deleted.

**Hotfix:**
```
main → hotfix/fix-token-validation → Pull Request → main (and back-merge to develop)
```
1. A critical bug is discovered in production.
2. A `hotfix/fix-token-validation` branch is created from `main`.
3. The fix is implemented, tested, and submitted as a Pull Request targeting `main`.
4. After approval, the hotfix is merged into `main` and tagged.
5. The hotfix is also merged into `develop` to prevent regression.
6. The hotfix branch is deleted.

### 14.3 Pull Request Workflow

```
┌──────────────┐     ┌───────────┐     ┌───────────┐     ┌──────────┐     ┌───────────┐
│  Developer   │────▶│ Push to   │────▶│ CI Checks │────▶│  Code    │────▶│  Merge    │
│  completes   │     │ feature   │     │ (lint,    │     │  Review  │     │  by Lead  │
│  task        │     │ branch    │     │  type,    │     │  (Pavan) │     │           │
│              │     │           │     │  test)    │     │          │     │           │
└──────────────┘     └───────────┘     └───────────┘     └──────────┘     └───────────┘
```

**Merge Rules:**

- Only the Project Lead (Pavan) can merge into `develop` and `main`.
- All CI checks must pass before merge is allowed.
- At least one approval is required.
- Force pushes to protected branches are disabled.
- Branch deletion after merge is mandatory.

---

## 15. Team Responsibilities

### 15.1 Pavan — Project Lead / Software Architect / DevOps Lead

Pavan holds overall responsibility for the technical direction, quality, and delivery of VaultDocs.

| Area | Responsibilities |
|------|-----------------|
| **Architecture** | Design system architecture, define module boundaries, establish coding patterns, make technology selection decisions. |
| **Project Planning** | Maintain the product backlog, prioritize features, plan sprints, set sprint goals, and track team velocity. |
| **Repository Management** | Manage GitHub repository settings, branch protection rules, access permissions, and repository secrets. |
| **Code Reviews** | Review all Pull Requests before merge. Ensure code quality, security, and architectural consistency. |
| **CI/CD** | Design and maintain GitHub Actions workflows for linting, testing, building, and deployment. |
| **Docker and Deployment** | Create and maintain Dockerfiles, Docker Compose configurations, and deployment scripts. |
| **Documentation** | Author and maintain project documentation (architecture, API design, coding standards, deployment guides). |
| **Final Approval** | No code reaches `develop` or `main` without Pavan's explicit approval. |

### 15.2 Raj — Backend Developer

Raj is responsible for implementing backend features as assigned during sprint planning.

| Area | Responsibilities |
|------|-----------------|
| **Feature Development** | Implement assigned features according to sprint backlog items, acceptance criteria, and architectural patterns. |
| **API Endpoints** | Build FastAPI routers, request/response schemas, and endpoint handlers for assigned modules. |
| **Business Logic** | Implement application layer services and domain logic for assigned features. |
| **Database** | Write SQLAlchemy models and Alembic migrations for assigned modules. |
| **Testing** | Write unit and integration tests for all implemented code. Maintain minimum 80% coverage on assigned modules. |
| **Code Quality** | Follow coding standards. Run linting, type checking, and tests before every push. |
| **Pull Requests** | Submit focused, well-documented Pull Requests. Address review feedback promptly. |
| **Peer Review** | Review Tirth's Pull Requests to share knowledge and catch issues early. |

### 15.3 Tirth — Backend Developer

Tirth is responsible for implementing backend features as assigned during sprint planning.

| Area | Responsibilities |
|------|-----------------|
| **Feature Development** | Implement assigned features according to sprint backlog items, acceptance criteria, and architectural patterns. |
| **API Endpoints** | Build FastAPI routers, request/response schemas, and endpoint handlers for assigned modules. |
| **Business Logic** | Implement application layer services and domain logic for assigned features. |
| **Database** | Write SQLAlchemy models and Alembic migrations for assigned modules. |
| **Testing** | Write unit and integration tests for all implemented code. Maintain minimum 80% coverage on assigned modules. |
| **Code Quality** | Follow coding standards. Run linting, type checking, and tests before every push. |
| **Pull Requests** | Submit focused, well-documented Pull Requests. Address review feedback promptly. |
| **Peer Review** | Review Raj's Pull Requests to share knowledge and catch issues early. |

---

## 16. Definition of Done

A task, user story, or sprint backlog item is considered **Done** only when all of the following criteria are met:

### Code Completion
- [ ] All acceptance criteria defined in the task/user story are satisfied.
- [ ] The implementation follows the project's architectural patterns (Clean Architecture layers, module boundaries).
- [ ] No placeholder code, TODO comments, or incomplete implementations remain in the submitted code.

### Testing
- [ ] Unit tests are written for all new business logic.
- [ ] Integration tests are written for database operations and API endpoints where applicable.
- [ ] All existing tests continue to pass (no regressions).
- [ ] Test coverage for the affected module meets or exceeds 80%.

### Code Quality
- [ ] Code passes Ruff linting with zero errors or warnings.
- [ ] Code passes Ruff formatting check (no formatting changes needed).
- [ ] Code passes mypy type checking in strict mode with zero errors.
- [ ] All public functions, classes, and modules have docstrings.

### Pull Request
- [ ] A Pull Request is submitted targeting the correct base branch.
- [ ] The PR title follows Conventional Commit conventions.
- [ ] The PR description includes what was changed, why, and how to test it.
- [ ] All CI pipeline checks pass (linting, type checking, tests, coverage).
- [ ] The PR has been reviewed and approved by the Project Lead (Pavan).

### Documentation
- [ ] API documentation is auto-generated and accurate (OpenAPI/Swagger reflects the implemented endpoints).
- [ ] Any changes to architecture, configuration, or deployment are reflected in the relevant documentation files.

### Merge
- [ ] The PR is merged by the Project Lead into the target branch.
- [ ] The feature branch is deleted after merge.

If any single criterion is not met, the task is **not Done**, regardless of whether the code "works."

---

## 17. Project Success Criteria

The success of VaultDocs is measured against specific, quantifiable criteria across multiple dimensions.

### 17.1 Functional Completeness

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Core features implemented | 100% of MVP features (Auth, User Mgmt, Folders, Documents, Sharing, RBAC, Versioning, Search, Activity Logs, Dashboard) | Feature checklist sign-off |
| API endpoint coverage | All endpoints defined in the API Design document are implemented and functional | Automated API test suite |
| Error handling coverage | All endpoints return structured error responses for invalid inputs, unauthorized access, and server errors | Manual review + automated tests |

### 17.2 Code Quality

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Test coverage | ≥ 80% across all modules | `pytest-cov` report |
| Linting | Zero errors/warnings from Ruff | CI pipeline |
| Type checking | Zero errors from mypy in strict mode | CI pipeline |
| Code review | 100% of code merged through reviewed Pull Requests | GitHub PR audit |

### 17.3 Performance

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| API response time (p95) | < 200 ms | Load testing |
| Document upload (100 MB) | < 10 seconds | Benchmark |
| Search response time | < 300 ms | Load testing |
| Concurrent users | 10,000 simultaneous connections | Load testing |

### 17.4 Security

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| OWASP Top 10 compliance | All applicable items addressed | Security review checklist |
| No secrets in source control | Zero secrets committed to the repository | GitHub secret scanning + manual review |
| Authentication bypass vulnerabilities | Zero | Penetration testing / security audit |
| Authorization bypass vulnerabilities | Zero | Automated permission tests |

### 17.5 Delivery

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Sprint completion rate | ≥ 85% of committed story points delivered per sprint | Sprint review |
| CI pipeline reliability | ≥ 99% of pipeline runs complete without infrastructure failures | GitHub Actions logs |
| Deployment success rate | 100% of deployments complete without rollback | Deployment logs |
| Documentation coverage | All modules, endpoints, and architectural decisions documented | Documentation review |

---

## 18. Future Enhancements

The following features are planned for post-MVP development phases. They are listed here to ensure that architectural decisions made during the MVP phase do not preclude their implementation.

### 18.1 OCR (Optical Character Recognition)

Integrate an OCR engine (such as Tesseract or a cloud-based OCR API) to extract text from scanned documents, images, and non-searchable PDFs. Extracted text will be indexed alongside document metadata, enabling full-text search across document content—not just filenames and tags. This feature requires the search subsystem to support content-level indexing, which is why the search interface is designed to be replaceable.

### 18.2 Cloud Storage Integration

Replace or augment the local filesystem storage with cloud object storage (AWS S3, Google Cloud Storage, or MinIO for self-hosted environments). The storage layer is already abstracted behind an interface in the MVP architecture, so this integration will not require changes to the domain or application layers. Cloud storage enables virtually unlimited scaling and removes the dependency on local disk capacity.

### 18.3 AI-Powered Search

Integrate a vector database (such as pgvector, Pinecone, or Weaviate) and an embedding model to enable semantic search. Users will be able to search for documents by describing what they are looking for in natural language, rather than relying on exact keyword matches. For example, searching for "Q3 revenue analysis" would surface relevant financial reports even if they do not contain those exact words.

### 18.4 AI Document Summaries

Use a large language model (LLM) API to generate automatic summaries of uploaded documents. Summaries will be stored as metadata and displayed in the document detail view and search results, helping users quickly assess document relevance without opening each file. Summarization can be triggered on upload or on demand, with results cached for performance.

### 18.5 Mobile Application

Develop a mobile-friendly frontend (progressive web app or native mobile application) that allows users to view, search, upload, and manage documents from mobile devices. The existing API surface is designed to support mobile clients without modification—authentication (JWT), pagination (cursor-based), and file upload (multipart) are all mobile-compatible patterns.

### 18.6 Slack Integration

Build a Slack application that notifies users of document events (shares, updates, access requests) directly in Slack channels or direct messages. Users will also be able to search for and share VaultDocs documents directly from Slack using slash commands. This integration requires a webhook endpoint on the VaultDocs side and a Slack App registration on the Slack side.

### 18.7 Google Drive Integration

Enable two-way synchronization between VaultDocs and Google Drive. Users will be able to import documents from their Google Drive into VaultDocs (gaining versioning, access control, and audit logging) and optionally mirror VaultDocs documents back to Google Drive for users who prefer Google's interface. This integration will use the Google Drive API and require OAuth consent from each user.

---

## 19. Conclusion

VaultDocs is a purposefully designed, production-grade document management system built to address real shortcomings in how teams and organizations handle their documents. The project prioritizes security, auditability, and clean architecture from the outset—not as afterthoughts bolted onto a prototype.

The technology stack is selected for performance, maintainability, and long-term viability. Python and FastAPI provide the development speed and async performance the project requires. PostgreSQL delivers the transactional guarantees and query capabilities the domain demands. Docker and GitHub Actions ensure that the build, test, and deployment pipeline is reproducible and automated.

The Modular Monolith architecture is a pragmatic choice for a team of three engineers building a product from scratch. It provides the structural discipline of microservices—clear module boundaries, dependency inversion, and replaceable infrastructure—without the operational complexity that microservices would impose at this scale. When the product grows beyond what a monolith can serve, the module boundaries are already defined, and extraction is a measured migration rather than a crisis-driven rewrite.

The development methodology—Agile Scrum with two-week sprints, mandatory code reviews, and protected branch policies—ensures that the team delivers incrementally, maintains quality, and adapts to feedback. No code enters production without being tested, reviewed, and approved through a structured process.

This document establishes the foundation for all subsequent project documentation. The team will proceed to detailed specifications for system architecture, database design, API design, and sprint planning only after this overview is reviewed and approved.

---

> **Document Control**
>
> | Field | Value |
> |-------|-------|
> | Document ID | DOC-001 |
> | Version | 1.0 |
> | Status | Approved |
> | Author | Pavan |
> | Reviewers | Raj, Tirth |
> | Next Review | End of Sprint 1 |
