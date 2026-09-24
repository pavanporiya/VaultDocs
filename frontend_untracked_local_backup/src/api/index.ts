/**
 * Public surface of the API layer.
 *
 * Import from '@/api' in app code. Internal modules stay importable for
 * advanced use (e.g. importing ApiError directly for instanceof checks).
 */

export { ApiError, isApiError } from "./errors";
export type { ApiErrorDetail, ApiValidationError } from "./errors";

export { getAccessToken, setAccessToken, clearAccessToken } from "./token";

export { request, downloadFile, saveBlob, getApiBaseUrl } from "./client";
export type { QueryParams, DownloadResult } from "./client";

export { registerUser, login } from "./auth";
export {
  listFolders,
  getFolder,
  createFolder,
  updateFolder,
  deleteFolder,
} from "./folders";
export {
  listDocuments,
  getDocument,
  createDocument,
  updateDocument,
  deleteDocument,
  searchDocuments,
  uploadDocumentFile,
  downloadDocumentFile,
} from "./documents";
export {
  listDocumentVersions,
  getDocumentVersion,
  downloadDocumentVersion,
} from "./versions";
export { createShare, listShares, revokeShare } from "./sharing";
export { getHealth } from "./health";

export type {
  User,
  TokenResponse,
  RegisterRequest,
  LoginRequest,
  Folder,
  FolderCreateRequest,
  FolderUpdateRequest,
  Document,
  DocumentCreateRequest,
  DocumentUpdateRequest,
  DocumentVersion,
  Share,
  ShareCreateRequest,
  HealthResponse,
  DocumentSearchQuery,
} from "./types";
