/**
 * Centralized fetch wrapper for the VaultDocs API.
 *
 * Responsibilities (and nothing more):
 * - URL building (base URL + path + query params)
 * - Authorization header injection when a token exists
 * - JSON / FormData request bodies
 * - JSON / blob / no-content responses
 * - Consistent ApiError for every non-2xx response
 *
 * All endpoint modules (auth, folders, documents, ...) go through
 * `request` — fetch is never called elsewhere in the API layer.
 *
 * Base URL rules:
 * - Paths start with `/v1/...`. The backend serves the API under `/v1`, so the
 *   base URL is joined as `origin + path`.
 * - Empty/undefined `VITE_API_BASE_URL` (development) = same-origin requests,
 *   which the Vite dev proxy forwards to http://localhost:8000. No CORS.
 * - A configured base (e.g. `https://api.example.com`) is used as the origin.
 *
 * Security: tokens are never logged; error URLs contain no credentials.
 */

import { ApiError, parseApiErrorBody } from "./errors";
import { getAccessToken } from "./token";

/** One safe place to read the configured API origin. */
export function getApiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL?.trim();
  return base && base.length > 0 ? base : (globalThis.location?.origin ?? "");
}

/** Statuses whose bodies we should not attempt to parse as JSON. */
const NO_BODY_STATUSES = new Set([204, 205, 304]);

function buildUrl(
  path: string,
  query?: Record<string, string | number | undefined>,
): string {
  const base = getApiBaseUrl().replace(/\/+$/, "");
  const url = `${base}${path}`;
  if (!query) return url;

  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const qs = search.toString();
  return qs.length > 0 ? `${url}?${qs}` : url;
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token === null ? {} : { Authorization: `Bearer ${token}` };
}

/** Read a successful body as parsed JSON (T = expected shape). */
async function readJson<T>(response: Response, url: string): Promise<T> {
  if (NO_BODY_STATUSES.has(response.status)) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ApiError("Malformed JSON in API response.", {
      status: response.status,
      url,
      cause: error,
    });
  }
}

/** Read an error body, if any, and raise the unified ApiError. */
async function raiseApiError(response: Response, url: string): Promise<never> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null; // HTML/empty error pages (e.g. proxy 502) have no JSON body.
  }

  const { message, detail } = parseApiErrorBody(
    body,
    fallbackMessage(response.status),
  );
  throw new ApiError(message, { status: response.status, detail, url });
}

function fallbackMessage(status: number): string {
  if (status === 0) return "Network error — could not reach the API.";
  if (status === 422) return "The request was rejected as invalid.";
  if (status === 404) return "Not found.";
  if (status >= 500) return "Server error. Please try again later.";
  return `Request failed with status ${status}.`;
}

export type QueryParams = Record<string, string | number | undefined>;

interface RequestOptions {
  /** Query parameters; `undefined` values are skipped. */
  query?: QueryParams;
  /** Serialized JSON body (mutually exclusive with `formData`). */
  json?: unknown;
  /** Multipart body (uploads); never sets Content-Type manually. */
  formData?: FormData;
  /** Extra headers merged over the defaults (auth included). */
  headers?: Record<string, string>;
  /** AbortSignal passthrough for cancellable requests. */
  signal?: AbortSignal;
}

/** Centralized JSON request. Throws ApiError for every non-2xx response. */
export async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = buildUrl(path, options.query);

  const headers: Record<string, string> = {
    ...authHeaders(),
    ...options.headers,
  };
  let body: BodyInit | undefined;
  if (options.formData !== undefined) {
    body = options.formData; // Browser sets the multipart boundary itself.
  } else if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      ...(body !== undefined ? { body } : {}),
      ...(options.signal !== undefined ? { signal: options.signal } : {}),
    });
  } catch (error) {
    // Network failure / abort. Do not leak request details into the message.
    throw new ApiError("Network error — could not reach the API.", {
      status: 0,
      url,
      cause: error,
    });
  }

  if (!response.ok) {
    await raiseApiError(response, url);
  }

  return readJson<T>(response, url);
}

/**
 * Centralized authenticated download. Returns the decoded file and the
 * filename the backend suggested (Content-Disposition), when present.
 *
 * The backend's download endpoints require the Authorization header, so plain
 * links / window.open cannot be used — everything goes through fetch + blob.
 */
export async function downloadFile(
  path: string,
  signal?: AbortSignal,
): Promise<DownloadResult> {
  const url = buildUrl(path);

  let response: Response;
  try {
    response = await fetch(url, {
      headers: authHeaders(),
      ...(signal !== undefined ? { signal } : {}),
    });
  } catch (error) {
    throw new ApiError("Network error — could not reach the API.", {
      status: 0,
      url,
      cause: error,
    });
  }

  if (!response.ok) {
    await raiseApiError(response, url);
  }

  const blob = await response.blob();
  return {
    blob,
    filename: parseFilename(response.headers.get("Content-Disposition")),
  };
}

export interface DownloadResult {
  blob: Blob;
  /** Backend-suggested filename from Content-Disposition, if present. */
  filename: string | null;
}

/** Extract filename from a Content-Disposition header, if present. */
function parseFilename(disposition: string | null): string | null {
  if (disposition === null) return null;
  // Matches filename="..." (the backend always quotes it via FileResponse).
  const match = /filename="([^"]*)"/.exec(disposition);
  return match?.[1] ?? null;
}

/** Trigger a browser download for a fetched blob (caller decides when). */
export function saveBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}
