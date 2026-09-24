/**
 * Version endpoints: GET /v1/documents/{id}/versions[/{version_id}[/download]].
 *
 * Access: owner or read-only shared user. Versions are immutable; newest first
 * in list responses. Version downloads use the same fetch/blob path as current
 * files (Authorization header required).
 */

import { downloadFile, request, saveBlob } from "./client";
import type { DocumentVersion } from "./types";

/** List all versions of a document, newest first. */
export function listDocumentVersions(
  documentId: string,
): Promise<DocumentVersion[]> {
  return request<DocumentVersion[]>(
    "GET",
    `/v1/documents/${documentId}/versions`,
  );
}

/** Get one version's metadata. */
export function getDocumentVersion(
  documentId: string,
  versionId: string,
): Promise<DocumentVersion> {
  return request<DocumentVersion>(
    "GET",
    `/v1/documents/${documentId}/versions/${versionId}`,
  );
}

/**
 * Download a specific version's file. Returns blob + suggested filename;
 * pair with `saveBlob` to trigger the browser download.
 */
export function downloadDocumentVersion(
  documentId: string,
  versionId: string,
  signal?: AbortSignal,
) {
  return downloadFile(
    `/v1/documents/${documentId}/versions/${versionId}/download`,
    signal,
  );
}

export { saveBlob };
