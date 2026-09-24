/**
 * Minimal token accessor abstraction.
 *
 * Task 3 (auth UI/context) will own how the token is stored; until then the
 * API layer reads/writes it here. Storage is centralized in this module so
 * replacing the mechanism later touches exactly one file.
 *
 * Note: token is held in localStorage because the frozen backend authenticates
 * via the Authorization header only (no cookie session, no refresh endpoint).
 * This is the accepted MVP tradeoff (see frontend investigation report).
 */

const TOKEN_STORAGE_KEY = "vaultdocs.access_token";

let memoryToken: string | null = null;

export function getAccessToken(): string | null {
  if (memoryToken !== null) return memoryToken;
  try {
    memoryToken = globalThis.localStorage?.getItem(TOKEN_STORAGE_KEY) ?? null;
  } catch {
    // localStorage unavailable (SSR/privacy mode) — stay memory-only.
  }
  return memoryToken;
}

export function setAccessToken(token: string): void {
  memoryToken = token;
  try {
    globalThis.localStorage?.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    // Memory-only fallback; login still works for this page session.
  }
}

export function clearAccessToken(): void {
  memoryToken = null;
  try {
    globalThis.localStorage?.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Nothing to clean up.
  }
}
