/**
 * TypeScript types mirroring the actual VaultDocs backend responses/requests.
 *
 * Source of truth: backend/src/vaultdocs/schemas/ (frozen backend MVP).
 * Do not invent fields. Backend response models are verified below.
 */

// -----------------------------------------------------------------------------
// Users / Auth
// -----------------------------------------------------------------------------

/** Backend: UserResponse (schemas/auth.py) */
export interface User {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
}

/** Backend: TokenResponse (schemas/auth.py) */
export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// -----------------------------------------------------------------------------
// Folders
// -----------------------------------------------------------------------------

/** Backend: FolderResponse (schemas/folder.py) */
export interface Folder {
  id: string;
  name: string;
  owner_id: string;
  parent_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface FolderCreateRequest {
  name: string;
  parent_id?: string;
}

/**
 * Backend PATCH omits unset fields (`model_dump(exclude_unset=True)`).
 * To clear `parent_id` the field must be OMITTED, not set to null — sending
 * `parent_id: null` fails backend validation (422). `null` in this type is a
 * deliberate frontend marker meaning "omit the field in the request body".
 */
export type FolderUpdateRequest = {
  name?: string;
  parent_id?: string | null;
};

// -----------------------------------------------------------------------------
// Documents
// -----------------------------------------------------------------------------

/**
 * Backend: DocumentResponse (schemas/document.py).
 *
 * The backend also returns `file_path` (a server filesystem path). It is a
 * backend implementation detail — the frontend must never use it. It is
 * intentionally NOT modeled here.
 */
export interface Document {
  id: string;
  name: string;
  owner_id: string;
  folder_id: string | null;
  original_filename: string | null;
  file_size: number | null;
  content_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentCreateRequest {
  name: string;
  folder_id?: string;
}

/**
 * Same exclude-unset semantics as folders: `null` means "omit the field".
 * `folder_id: null` cannot actually clear a document's folder on the frozen
 * backend (422 on UUID parse) — omitted means "no change".
 */
export type DocumentUpdateRequest = {
  name?: string;
  folder_id?: string | null;
};

// -----------------------------------------------------------------------------
// Document versions
// -----------------------------------------------------------------------------

/** Backend: DocumentVersionResponse (schemas/document.py) */
export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  original_filename: string;
  file_size: number;
  content_type: string;
  created_at: string;
}

// -----------------------------------------------------------------------------
// Sharing
// -----------------------------------------------------------------------------

/** Backend: ShareCreate (schemas/share.py) — sharing is by recipient email. */
export interface ShareCreateRequest {
  user_email: string;
}

/** Backend: ShareResponse (schemas/share.py) — no recipient email returned. */
export interface Share {
  id: string;
  document_id: string;
  shared_with_user_id: string;
  created_at: string;
  updated_at: string;
}

// -----------------------------------------------------------------------------
// Health
// -----------------------------------------------------------------------------

/** Backend: health check response (api/v1/health.py) */
export interface HealthResponse {
  status: string;
  database: string;
  environment: string;
  version: string;
}

// -----------------------------------------------------------------------------
// Search
// -----------------------------------------------------------------------------

/** Query parameters for GET /v1/documents/search (all optional). */
export interface DocumentSearchQuery {
  /** Name query. Backend returns all user's documents when omitted/empty. */
  q?: string;
  folder_id?: string;
  limit?: number;
  offset?: number;
}
