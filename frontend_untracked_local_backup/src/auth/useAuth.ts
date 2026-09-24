import { useAuthContext } from "./AuthContext";

/** Convenience hook for components: auth state + login/logout/retry. */
export function useAuth() {
  return useAuthContext();
}
