import {
  createContext,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { getCurrentUser, login as loginRequest } from "@/api/auth";
import { clearAccessToken } from "@/api/token";
import {
  resolveInitialState,
  stateForBootstrapError,
  type AuthProviderState,
} from "./auth-context";

/**
 * Framework-free auth store consumed through useSyncExternalStore.
 *
 * Why not useState/useEffect in the provider? The bootstrap promise must run
 * exactly once per page load regardless of StrictMode double-rendering or
 * provider remounts. A module-level store gives that for free, and
 * useSyncExternalStore handles tearing/consistency.
 *
 * Login/logout live on the store (not effects) so the state machine is:
 *   initial state -> (login | logout | retryBootstrap) -> state
 * with no async effects to race.
 */

type Listener = () => void;

class AuthStore {
  private state: Promise<AuthProviderState>;

  private cached: AuthProviderState = { status: "initializing" };

  private listeners = new Set<Listener>();

  constructor() {
    this.state = Promise.resolve(resolveInitialState());
    void this.state.then((resolved) => {
      this.cached = resolved;
      this.emit();
    });
  }

  getState = (): AuthProviderState => this.cached;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private emit(): void {
    for (const listener of this.listeners) listener();
  }

  private setState(state: AuthProviderState): void {
    this.cached = state;
    this.emit();
  }

  /**
   * Authenticate with email/password; token is stored by the api layer.
   *
   * Rejects on failure (after mirroring the failure into auth state) so the
   * login page can display the error and stay on the form. Swallowing here
   * would make the caller navigate away on failed logins.
   */
  async login(email: string, password: string): Promise<void> {
    this.setState({ status: "loading" });
    try {
      await loginRequest({ email, password });
      const user = await getCurrentUser();
      this.setState({ status: "authenticated", user });
    } catch (error) {
      // Login failure never leaves a half-session behind.
      clearAccessToken();
      this.setState(stateForBootstrapError(error));
      throw error;
    }
  }

  /** Client-side logout: the backend has no logout endpoint (frozen MVP). */
  logout(): void {
    clearAccessToken();
    this.setState({ status: "unauthenticated" });
  }

  /** Retry bootstrap after a retryable error (network/5xx). */
  retryBootstrap(): void {
    this.state = Promise.resolve(resolveInitialState());
    this.setState({ status: "loading" });
    void this.state.then((resolved) => {
      this.cached = resolved;
      this.emit();
    });
  }
}

export const authStore = new AuthStore();

// -----------------------------------------------------------------------------
// React bindings
// -----------------------------------------------------------------------------

export interface AuthContextValue {
  readonly state: AuthProviderState;
  login(email: string, password: string): Promise<void>;
  logout(): void;
  retryBootstrap(): void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const state = useSyncExternalStore(
    authStore.subscribe,
    authStore.getState,
    authStore.getState,
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      login: (email, password) => authStore.login(email, password),
      logout: () => authStore.logout(),
      retryBootstrap: () => authStore.retryBootstrap(),
    }),
    [state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Access the auth state + actions. Throws outside an AuthProvider. */
export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return context;
}
