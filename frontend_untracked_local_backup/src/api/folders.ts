/**
 * Folder endpoints: CRUD under /v1/folders (frozen backend).
 *
 * PATCH semantics (verified in backend/services/folder.py):
 * `model_dump(exclude_unset=True)` — omitted fields are left unchanged, and
 * `parent_id: null` is rejected (422). `FolderUpdateRequest` therefore models
 * `null` as "omit", and updateFolder drops `null` fields before sending.
 */

import { request } from "./client";
import type { Folder, FolderCreateRequest, FolderUpdateRequest } from "./types";

/** List all folders owned by the authenticated user (flat, unordered tree). */
export function listFolders(): Promise<Folder[]> {
  return request<Folder[]>("GET", "/v1/folders");
}

/** Get one folder. 404 when missing or owned by someone else (IDOR-safe). */
export function getFolder(folderId: string): Promise<Folder> {
  return request<Folder>("GET", `/v1/folders/${folderId}`);
}

/** Create a folder, optionally nested under `parent_id`. */
export function createFolder(data: FolderCreateRequest): Promise<Folder> {
  return request<Folder>("POST", "/v1/folders", { json: data });
}

/**
 * Update a folder. Fields present on the request object are sent; fields
 * explicitly set to `null` are omitted (backend would reject `null`).
 */
export function updateFolder(
  folderId: string,
  data: FolderUpdateRequest,
): Promise<Folder> {
  return request<Folder>("PATCH", `/v1/folders/${folderId}`, {
    json: dropNullFields(data),
  });
}

/** Delete a folder. */
export function deleteFolder(folderId: string): Promise<void> {
  return request<void>("DELETE", `/v1/folders/${folderId}`);
}

/** Remove explicitly-`null` fields — matches backend exclude_unset behavior. */
function dropNullFields(data: FolderUpdateRequest): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (value !== null) body[key] = value;
  }
  return body;
}
