/**
 * Share endpoints (owner-side management, frozen backend):
 * - POST   /v1/documents/{id}/shares           share read-only by email
 * - GET    /v1/documents/{id}/shares           list shares
 * - DELETE /v1/documents/{id}/shares/{share_id} revoke
 *
 * All owner-only; the backend answers 404 for non-owners (IDOR-safe).
 * Recipient is identified by email (must be a registered user). The response
 * carries `shared_with_user_id` only — no email — so the UI cannot display
 * recipient names for shares created before this page load.
 */

import { request } from "./client";
import type { Share, ShareCreateRequest } from "./types";

/** Share a document (read-only) with a registered user, by email. */
export function createShare(
  documentId: string,
  data: ShareCreateRequest,
): Promise<Share> {
  return request<Share>("POST", `/v1/documents/${documentId}/shares`, {
    json: data,
  });
}

/** List all shares of a document (owner only). */
export function listShares(documentId: string): Promise<Share[]> {
  return request<Share[]>("GET", `/v1/documents/${documentId}/shares`);
}

/** Revoke a share. The recipient loses access immediately. */
export function revokeShare(
  documentId: string,
  shareId: string,
): Promise<void> {
  return request<void>(
    "DELETE",
    `/v1/documents/${documentId}/shares/${shareId}`,
  );
}
