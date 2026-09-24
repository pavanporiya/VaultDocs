/**
 * One reusable error type for every non-2xx (or failed) API response.
 *
 * Backend error shapes observed (frozen backend):
 * - FastAPI HTTPException: { "detail": "<message>" }
 * - FastAPI request validation (422): { "detail": [{ loc, msg, type, ... }] }
 * - Non-JSON / network failures: no parseable body at all.
 */

/** Parsed `detail` from a FastAPI error body, whichever shape it has. */
export type ApiErrorDetail = string | ApiValidationError[] | null;

export interface ApiValidationError {
  /** e.g. ["body", "email"] */
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** One reusable error type for the whole API layer. */
export class ApiError extends Error {
  /** HTTP status code, or 0 for network failure. */
  readonly status: number;

  /** Parsed backend `detail`, whichever shape FastAPI produced. */
  readonly detail: ApiErrorDetail;

  /** The URL that failed, for debugging (never contains the token). */
  readonly url: string;

  constructor(
    message: string,
    options: {
      status: number;
      detail?: ApiErrorDetail;
      url?: string;
      cause?: unknown;
    },
  ) {
    super(message, { cause: options.cause });
    this.name = "ApiError";
    this.status = options.status;
    this.detail = options.detail ?? null;
    this.url = options.url ?? "";
  }

  /**
   * Human-friendly message for UI display.
   *
   * 422: joins validation messages; other statuses: uses the backend detail
   * string when available, else the fallback.
   */
  get displayMessage(): string {
    if (typeof this.detail === "string") return this.detail;
    if (Array.isArray(this.detail) && this.detail.length > 0) {
      return this.detail.map((e) => e.msg).join("; ");
    }
    return this.message;
  }

  /** True for `apiError.status === 401` (expired/invalid token). */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

/** Shape of FastAPI's error body. `detail` is string or validation array. */
interface FastApiErrorBody {
  detail?: unknown;
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/**
 * Extract a usable message/detail from an error response body.
 * Handles FastAPI's two shapes plus non-JSON bodies. Never throws.
 */
export function parseApiErrorBody(
  body: unknown,
  fallback: string,
): { message: string; detail: ApiErrorDetail } {
  if (body === null || body === undefined)
    return { message: fallback, detail: null };

  const detail = (body as FastApiErrorBody).detail;
  if (typeof detail === "string") return { message: detail, detail };
  if (Array.isArray(detail))
    return { message: fallback, detail: detail as ApiValidationError[] };
  if (typeof (body as { message?: unknown }).message === "string") {
    // Non-FastAPI JSON errors (e.g. reverse proxies).
    const message = (body as { message: string }).message;
    return { message, detail: message };
  }

  return { message: fallback, detail: null };
}
