# VaultDocs — Product Roadmap

> **Document ID:** DOC-008
> **Version:** 1.0.0
> **Status:** Approved
> **Author:** Pavan (Software Architect / Project Lead)
> **Contributors:** Raj (Backend Developer), Tirth (Backend Developer)
> **Created Date:** 2026-07-20
> **Last Updated:** 2026-07-20
> **Classification:** Internal Engineering Documentation

---

## Executive Summary

This Product Roadmap outlines the multi-phase evolution of VaultDocs. Starting from the Phase 1 core backend MVP (Modular Monolith, JWT Auth, Streamed Ingestion, Version Control, PostgreSQL Full-Text Search, Audit Logging), this document details upcoming near-term capabilities (OCR, Vector Search, AI Summaries) and long-term enterprise extensions (Cloud Object Storage, Third-Party Integrations, Native Mobile Apps, and Enterprise Compliance).

---

## Table of Contents

1. [Product Vision & Release Strategy](#1-product-vision--release-strategy)
2. [Phase 1: MVP Baseline (Current Release - v1.0)](#2-phase-1-mvp-baseline-current-release---v10)
3. [Phase 2: Intelligent Document Engine (v1.5 - v2.0)](#3-phase-2-intelligent-document-engine-v15---v20)
4. [Phase 3: Cloud & Ecosystem Integrations (v2.5)](#4-phase-3-cloud--ecosystem-integrations-v25)
5. [Phase 4: Enterprise Scale & Governance (v3.0)](#5-phase-4-enterprise-scale--governance-v30)
6. [Feature Matrix & Release Timeline](#6-feature-matrix--release-timeline)

---

## 1. Product Vision & Release Strategy

VaultDocs is evolving from an API-driven core document vault into an intelligent, enterprise-wide knowledge platform. Development proceeds in structured quarterly releases:

```
+-----------------------------------------------------------------------------------+
|                            VAULTDOCS EVOLUTION TIMELINE                           |
|                                                                                   |
|  [ Phase 1: MVP Core ]  ===>  [ Phase 2: AI & OCR ]  ===>  [ Phase 3: Integrations]  |
|  - Modular Monolith           - Tesseract OCR Pipeline       - AWS S3 / Azure Storage |
|  - Stream Ingestion           - pgvector Semantic Search     - Slack & Drive Sync     |
|  - Version Control            - LLM Document Summaries       - Cloud Connectors       |
|  - RBAC & Audit Logs          - Auto-Categorization          - Webhooks System        |
|  (Q3 2026 - Delivered)        (Q4 2026 - Q1 2027)            (Q2 2027 - Q3 2027)      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Phase 1: MVP Baseline (Current Release - v1.0)

*Status: Implemented / Baseline Delivery*

* **Architecture:** Modular Monolith in Python 3.13, FastAPI, Clean Architecture.
* **Authentication:** OAuth2 JWT Bearer tokens, Argon2id hashing, Redis session revocation.
* **Document Engine:** Streamed multipart upload, SHA-256 integrity verification, POSIX vault storage.
* **Versioning:** Immutable version tracking, historical version retrieval.
* **Search:** PostgreSQL GIN index full-text search across titles, descriptions, and tags.
* **Governance:** Granular RBAC, immutable structured JSON audit logging.

---

## 3. Phase 2: Intelligent Document Engine (v1.5 - v2.0)

*Target Timeline: Q4 2026 – Q1 2027*

```
+-----------------------------------------------------------------------------------+
|                       PHASE 2: INTELLIGENT PROCESSING PIPELINE                    |
|                                                                                   |
|  Document Upload --> OCR Extraction --> Embedding Generation --> Vector Indexing |
|  (PDF / Raster)     (Tesseract / PDF)   (SentenceTransformers) (pgvector / HNSW)  |
+-----------------------------------------------------------------------------------+
```

### Key Deliverables

1. **Optical Character Recognition (OCR) Engine:**
   - Background worker task queue (Celery / Redis Work Queue) ingesting scanned image PDFs.
   - Text extraction using `Tesseract OCR` and PDF stream parsing into database `search_content`.

2. **Vector-Based Semantic Search (`pgvector`):**
   - Generation of 768-dimensional text embeddings for document content chunking.
   - Storage of embeddings inside PostgreSQL using the `pgvector` extension with HNSW indexing.
   - Hybrid search capability blending PostgreSQL keyword GIN search with semantic vector similarity queries.

3. **LLM Document Summarization & Metadata Auto-Tagging:**
   - Asynchronous LLM processing pipeline generating automated executive summaries.
   - Automated extraction of key entity metadata tags (dates, entities, contracts, financial amounts).

---

## 4. Phase 3: Cloud & Ecosystem Integrations (v2.5)

*Target Timeline: Q2 2027 – Q3 2027*

### Key Deliverables

1. **Cloud Blob Storage Provider Plugins:**
   - Implement `S3StorageEngine` supporting AWS S3, MinIO, and Cloudflare R2 object storage.
   - Implement `AzureBlobStorageEngine` for Microsoft Azure enterprise storage integration.

2. **Third-Party Synchronization & Connectors:**
   - **Google Drive / OneDrive Integration:** Direct import/export document synchronization.
   - **Slack & Microsoft Teams Notifications:** Automated audit alerts and document share notifications via webhooks.

3. **Event Webhook Dispatcher:**
   - Configurable outbound HTTP webhooks notifying external corporate systems when documents are uploaded, modified, or deleted.

---

## 5. Phase 4: Enterprise Scale & Governance (v3.0)

*Target Timeline: Q4 2027+*

### Key Deliverables

1. **SAML 2.0 & OpenID Connect (OIDC) Single Sign-On:**
   - Native enterprise identity integration with Okta, Azure AD (Entra ID), and PingIdentity.

2. **Hardened Multi-Tenant Isolation & Customer Managed Keys (KMS):**
   - Envelope encryption per tenant using AWS KMS or HashiCorp Vault.
   - Row-Level Security (RLS) database isolation policies.

3. **Native Mobile Applications:**
   - React Native cross-platform mobile apps for iOS and Android consuming VaultDocs REST APIs.

---

## 6. Feature Matrix & Release Timeline

| Feature Category | Capability / Feature | Target Phase | Status / Target |
| :--- | :--- | :---: | :---: |
| **Core DMS** | Streamed Uploads & Immutable Versioning | Phase 1 | **Delivered** |
| **Search** | PostgreSQL GIN Full-Text Search | Phase 1 | **Delivered** |
| **Governance** | RBAC & Immutable Audit Trail | Phase 1 | **Delivered** |
| **Intelligence** | OCR Text Extraction Pipeline | Phase 2 | Planned (Q4 2026) |
| **Intelligence** | `pgvector` Semantic AI Search | Phase 2 | Planned (Q1 2027) |
| **Intelligence** | LLM Summaries & Auto-Tagging | Phase 2 | Planned (Q1 2027) |
| **Storage** | AWS S3 / Azure Blob Storage Provider | Phase 3 | Planned (Q2 2027) |
| **Integrations** | Google Drive / OneDrive / Slack Sync | Phase 3 | Planned (Q3 2027) |
| **Security** | Enterprise SAML 2.0 / Okta SSO | Phase 4 | Planned (Q4 2027) |
| **Security** | Tenant KMS Envelope Encryption | Phase 4 | Planned (Q4 2027) |
| **Clients** | Native Mobile App (iOS / Android) | Phase 4 | Planned (Q4 2027) |
