/**
 * Document endpoints: CRUD + search + file upload/download (frozen backend).
 *
 * Notes:
 * - Search is a real path (/v1/documents/search) declared before /{document_id}
 *   in the backend router — no shadowing.
 * - POST /v1/documents/{id}/upload stores a NEW immutable version of the file;
 *   it is simultaneously "upload" and "replace" (there is no separate replace
 *   endpoint on the frozen backend).
 * - Download requires the Authorization header → fetch/blob, never <a href>.
 */

import { downloadFile, request, saveBlob } from "./client";
import type {
  Document,
  DocumentCreateRequest,
  DocumentSearchQuery,
  DocumentUpdateRequest,
} from "./types";

/** List all documents owned by the authenticated user (flat). */
export function listDocuments(): Promise<Document[]> {
  return request<Document[]>("GET", "/v1/documents");
}

/** Get one document. 404 when missing or not owned/shared (IDOR-safe). */
export function getDocument(documentId: string): Promise<Document> {
  return request<Document>("GET", `/v1/documents/${documentId}`);
}

/** Create a document (metadata only — file attached via upload). */
export function createDocument(data: DocumentCreateRequest): Promise<Document> {
  return request<Document>("POST", "/v1/documents", { json: data });
}

/**
 * Update a document. Same exclude-unset semantics as folders: fields set to
 * `null` are omitted (backend rejects `folder_id: null` with 422).
 */
export function updateDocument(
  documentId: string,
  data: DocumentUpdateRequest,
): Promise<Document> {
  return request<Document>("PATCH", `/v1/documents/${documentId}`, {
    json: dropNullFields(data),
  });
}

/** Delete a document (owner only). */
export function deleteDocument(documentId: string): Promise<void> {
  return request<void>("DELETE", `/v1/documents/${documentId}`);
}

/** Search documents by name, optionally scoped to a folder, with pagination. */
export function searchDocuments(
  query: DocumentSearchQuery = {},
): Promise<Document[]> {
  return request<Document[]>("GET", "/v1/documents/search", {
    query: {
      q: query.q,
      folder_id: query.folder_id,
      limit: query.limit,
      offset: query.offset,
    },
  });
}

/**
 * Upload (or replace) the file of a document. Creates a new immutable version.
 * The backend accepts POST and PUT interchangeably; POST is used here.
 */
export function uploadDocumentFile(
  documentId: string,
  file: File,
): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);
  return request<Document>("POST", `/v1/documents/${documentId}/upload`, {
    formData,
  });
}

/**
 * Download a document's current file. Returns the blob plus the backend's
 * suggested filename (Content-Disposition); `saveBlob` triggers the browser
 * download. Callers decide whether to save or preview.
 */
export function downloadDocumentFile(documentId: string, signal?: AbortSignal) {
  return downloadFile(`/v1/documents/${documentId}/download`, signal);
}

export { saveBlob };

/** Remove explicitly-`null` fields — matches backend exclude_unset behavior. */
function dropNullFields(data: DocumentUpdateRequest): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (value !== null) body[key] = value;
  }
  return body;
}
