/**
 * Auth state types + initial-state resolution.
 *
 * Kept framework-free (no React imports) so the state machine stays testable
 * and the React bindings in AuthContext.tsx stay thin.
 *
 * The `unauthorized` state exists to distinguish a definitively invalid token
 * from transient failures: only 401 may clear the session.
 */

import { clearAccessToken, getAccessToken } from "@/api/token";
import { ApiError } from "@/api/errors";
import { getCurrentUser } from "@/api/auth";
import type { User } from "@/api/types";

export type AuthProviderState =
  | { status: "initializing" }
  | { status: "loading" }
  | { status: "unauthorized" }
  | { status: "error"; message: string }
  | { status: "authenticated"; user: User }
  | { status: "unauthenticated" };

/**
 * Map a bootstrap failure to the correct state.
 *
 * Only 401 proves the token is invalid — clear it and drop to unauthenticated.
 * Network/5xx errors must NOT claim the user is logged out: keep the token and
 * surface a retryable error state instead.
 */
export function stateForBootstrapError(error: unknown): AuthProviderState {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      clearAccessToken();
      return { status: "unauthorized" };
    }
    return {
      status: "error",
      message:
        error.status === 0
          ? "Unable to connect to VaultDocs. Please try again."
          : error.displayMessage,
    };
  }
  return {
    status: "error",
    message: "Something went wrong. Please try again.",
  };
}

/**
 * Run the auth bootstrap exactly once at module load (before the first React
 * render): token present? validate via GET /v1/auth/me. This keeps StrictMode's
 * double render and provider remounts from issuing duplicate /me requests.
 */
export async function resolveInitialState(): Promise<AuthProviderState> {
  const token = getAccessToken();
  if (token === null) return { status: "unauthenticated" };

  try {
    const user = await getCurrentUser();
    return { status: "authenticated", user };
  } catch (error) {
    return stateForBootstrapError(error);
  }
}
