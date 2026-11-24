/**
 * Centralized API Client Foundation for VaultDocs
 *
 * Provides reusable HTTP request handling, JWT token injection,
 * standard response parsing, error normalization for FastAPI responses,
 * and environment-based configuration.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/v1';

export class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Retrieves the stored JWT access token from localStorage if present.
 */

export const getAuthToken = () => {
  try {
    return localStorage.getItem('vaultdocs_token');
  } catch {
    return null;
  }
};

/**
 * Sets or removes the JWT access token in localStorage.
 */
export const setAuthToken = (token) => {
  try {
    if (token) {
      localStorage.setItem('vaultdocs_token', token);
    } else {
      localStorage.removeItem('vaultdocs_token');
    }
  } catch {
    // Ignore storage quota errors in non-browser environments
  }
};

/**
 * Formats FastAPI error responses into a human-friendly string.
 * Never exposes raw backend stack traces or storage paths.
 */
const parseErrorMessage = (status, data) => {
  if (data && typeof data.detail === 'string') {
    return data.detail;
  }
  if (data && typeof data.detail === 'object' && data.detail !== null) {
    if (typeof data.detail.message === 'string') {
      return data.detail.message;
    }
  }
  if (data && Array.isArray(data.detail)) {
    // FastAPI validation errors (422)
    return data.detail.map((err) => `${err.loc?.join('.') || 'field'}: ${err.msg}`).join(', ');
  }
  if (status === 401) return 'Authentication required. Please log in.';
  if (status === 403) return 'You do not have permission to perform this action.';
  if (status === 404) return 'The requested resource was not found.';
  if (status === 422) return 'Invalid data submitted.';
  if (status >= 500) return 'A server error occurred. Please try again later.';
  return 'An unexpected error occurred.';
};

/**
 * Core request function wrapping standard fetch with headers and interceptors.
 */
async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const headers = new Headers(options.headers || {});

  // Add Auth Token if available and not explicitly disabled
  const token = getAuthToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Set default JSON Content-Type if body is present and not FormData
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const config = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);

    // Handle No Content (204)
    if (response.status === 204) {
      return null;
    }

    let data = null;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      data = text ? { raw: text } : null;
    }

    if (!response.ok) {
      const errorMessage = parseErrorMessage(response.status, data);
      throw new ApiError(errorMessage, response.status, data);
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    // Network errors, connection timeouts, or fetch failures
    throw new ApiError(
      error.message || 'Network error. Please check your internet connection.',
      0,
      null
    );
  }
}

/**
 * Extract a filename from a Content-Disposition header when present.
 */
const parseContentDispositionFilename = (disposition) => {
  if (!disposition) return null;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  return match ? match[1] : null;
};

/**
 * Centralized authenticated download for file/endpoint responses.
 *
 * Streams through the same token-injecting request pipeline as every other
 * API call and returns the decoded blob plus the backend-suggested filename
 * (Content-Disposition) so callers never touch fetch/localStorage directly.
 *
 * @param {string} endpoint - API endpoint path (e.g. `/documents/{id}/download`).
 * @returns {Promise<{blob: Blob, filename: string|null}>}
 */
export async function downloadFile(endpoint) {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const headers = new Headers();
  const token = getAuthToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response;
  try {
    response = await fetch(url, { headers });
  } catch (error) {
    throw new ApiError(
      error?.message || 'Network error. Please check your internet connection.',
      0,
      null
    );
  }

  if (!response.ok) {
    let data = null;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json().catch(() => null);
    }
    throw new ApiError(parseErrorMessage(response.status, data), response.status, data);
  }

  const blob = await response.blob();
  return {
    blob,
    filename: parseContentDispositionFilename(response.headers.get('content-disposition')),
  };
}

/**
 * Trigger a browser download for a previously fetched blob.
 */
export function saveBlob(blob, filename) {
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(objectUrl);
}

/**
 * Centralized API service object exposing HTTP verbs.
 */
export const apiClient = {
  get: (endpoint, options = {}) => request(endpoint, { ...options, method: 'GET' }),

  post: (endpoint, body = null, options = {}) =>
    request(endpoint, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : null,
    }),

  put: (endpoint, body = null, options = {}) =>
    request(endpoint, {
      ...options,
      method: 'PUT',
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : null,
    }),

  patch: (endpoint, body = null, options = {}) =>
    request(endpoint, {
      ...options,
      method: 'PATCH',
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : null,
    }),

  delete: (endpoint, options = {}) => request(endpoint, { ...options, method: 'DELETE' }),

  upload: (endpoint, formData, options = {}) =>
    request(endpoint, {
      ...options,
      method: 'POST',
      body: formData,
    }),
};

/**
 * Upload a file via XMLHttpRequest to get real per-file upload progress events.
 *
 * Uses the exact same BASE_URL and Bearer-token header as the fetch-based
 * `request()` pipeline, and throws the same normalized `ApiError` on failure,
 * so callers get identical behaviour plus progress reporting.
 * Additive-only helper: existing `apiClient.upload` behaviour is untouched.
 *
 * @param {string} endpoint - API endpoint path (e.g. `/documents/{id}/upload`).
 * @param {FormData} formData - Must contain the file under the `file` key.
 * @param {(percent: number) => void} [onProgress] - Called with 0..100.
 * @returns {Promise<any>} Parsed JSON response body (or null for 204).
 */
export const uploadWithProgress = (endpoint, formData, onProgress = null) =>
  new Promise((resolve, reject) => {
    const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);

    const token = getAuthToken();
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }

    if (typeof onProgress === 'function' && xhr.upload) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) {
          onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
        }
      };
    }

    xhr.onload = () => {
      let data = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        reject(new ApiError(parseErrorMessage(xhr.status, data), xhr.status, data));
      }
    };

    xhr.onerror = () => {
      reject(
        new ApiError('Network error. Please check your internet connection.', 0, null)
      );
    };

    xhr.ontimeout = () => {
      reject(new ApiError('Upload timed out. Please try again.', 0, null));
    };

    xhr.send(formData);
  });

export default apiClient;
