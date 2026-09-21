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
 */
const parseErrorMessage = (status, data) => {
  if (data && typeof data.detail === 'string') {
    return data.detail;
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

export default apiClient;
