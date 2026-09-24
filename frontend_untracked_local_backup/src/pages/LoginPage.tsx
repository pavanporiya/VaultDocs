import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError, isApiError } from "@/api/errors";
import { useAuth } from "@/auth/useAuth";
import { BrandMark } from "@/auth/AuthLoading";

/**
 * VaultDocs login page.
 *
 * Flow: validate locally -> authStore.login (POST /v1/auth/login stores the
 * token via the api layer, then GET /v1/auth/me) -> redirect to the page the
 * user originally wanted (location.state.from) or "/".
 *
 * Validation is intentionally native/hand-rolled — no form framework. The
 * email regex checks shape only; the backend remains the authority.
 */

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface FieldErrors {
  email?: string;
  password?: string;
}

function validate(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  if (email.trim().length === 0) {
    errors.email = "Email is required.";
  } else if (!EMAIL_PATTERN.test(email.trim())) {
    errors.email = "Enter a valid email address.";
  }
  if (password.length === 0) {
    errors.password = "Password is required.";
  }
  return errors;
}

/** Map an API failure to a user-facing message. No stack traces, no paths. */
function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Invalid email or password.";
    if (error.status === 422)
      return "Enter a valid email address and password.";
    if (error.status === 0 || error.status >= 500) {
      return "Unable to connect to VaultDocs. Please try again.";
    }
    return error.displayMessage;
  }
  return "Something went wrong. Please try again.";
}

export default function LoginPage() {
  const { state, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);

  const submitting = state.status === "loading";

  // Already signed in? Nothing to do here.
  if (state.status === "authenticated") {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    setFormError(null);

    const errors = validate(email, password);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    try {
      await login(email.trim(), password);
      const from =
        typeof location.state === "object" &&
        location.state !== null &&
        "from" in location.state &&
        typeof (location.state as { from?: unknown }).from === "string"
          ? (location.state as { from: string }).from
          : "/";
      navigate(from, { replace: true });
    } catch (error) {
      setFormError(loginErrorMessage(error));
      setPassword(""); // Never keep a failed password around.
      if (isApiError(error) && error.status === 401) {
        setPasswordFocus();
      }
    }
  }

  function setPasswordFocus(): void {
    document.getElementById("password")?.focus();
  }

  const emailInvalid = fieldErrors.email !== undefined;
  const passwordInvalid = fieldErrors.password !== undefined;

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-950 px-4 py-12">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/30">
            <BrandMark className="h-6 w-6 fill-emerald-400" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-semibold tracking-tight text-neutral-100">
              VaultDocs
            </h1>
            <p className="mt-1 text-sm text-neutral-400">
              Secure document management
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-6 shadow-lg shadow-black/20 sm:p-8">
          <h2 className="text-lg font-semibold text-neutral-100">
            Welcome back
          </h2>
          <p className="mt-1 text-sm text-neutral-400">
            Sign in to access your documents.
          </p>

          <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
            {formError !== null && (
              <div
                role="alert"
                className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2.5 text-sm text-red-300"
              >
                {formError}
              </div>
            )}

            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="block text-sm font-medium text-neutral-200"
              >
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                autoFocus
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-invalid={emailInvalid || undefined}
                aria-describedby={emailInvalid ? "email-error" : undefined}
                disabled={submitting}
                className="block w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 disabled:opacity-50"
                placeholder="you@company.com"
              />
              {emailInvalid && (
                <p id="email-error" className="text-xs text-red-400">
                  {fieldErrors.email}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-neutral-200"
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-pressed={showPassword}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="text-xs text-neutral-400 transition-colors hover:text-neutral-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-invalid={passwordInvalid || undefined}
                aria-describedby={
                  passwordInvalid ? "password-error" : undefined
                }
                disabled={submitting}
                className="block w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 disabled:opacity-50"
                placeholder="••••••••"
              />
              {passwordInvalid && (
                <p id="password-error" className="text-xs text-red-400">
                  {fieldErrors.password}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-neutral-950 transition-colors hover:bg-emerald-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-neutral-400">
            Don&apos;t have an account?{" "}
            <Link
              to="/register"
              className="font-medium text-emerald-400 transition-colors hover:text-emerald-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
            >
              Create account
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
