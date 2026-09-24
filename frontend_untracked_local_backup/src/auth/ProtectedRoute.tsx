import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./useAuth";
import { AuthLoading } from "./AuthLoading";

/**
 * Route guard for authenticated areas.
 *
 * - initializing/loading/error: bootstrap still resolving or retryable — show
 *   a centered state, never redirect on a network error (that would log the
 *   user out on a flaky connection).
 * - unauthenticated/unauthorized: redirect to /login, remembering where the
 *   user wanted to go.
 *
 * Only the backend proves authentication; this guard is UX routing.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { state, retryBootstrap } = useAuth();
  const location = useLocation();

  switch (state.status) {
    case "initializing":
    case "loading":
      return <AuthLoading />;

    case "error":
      return (
        <AuthLoading
          message={state.message}
          action={{ label: "Try again", onClick: retryBootstrap }}
        />
      );

    case "unauthenticated":
    case "unauthorized":
      return (
        <Navigate to="/login" replace state={{ from: location.pathname }} />
      );

    case "authenticated":
      return <>{children}</>;
  }
}
