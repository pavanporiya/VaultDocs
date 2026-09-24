import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import LoginPage from "@/pages/LoginPage";

/** Temporary authenticated placeholder — replaced by the dashboard later. */
function AuthenticatedPlaceholder() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-neutral-950 px-6 text-neutral-100">
      <div className="flex items-center gap-3">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="h-10 w-10 fill-emerald-400"
        >
          <path d="M12 2 4 5v6c0 5.25 3.4 9.74 8 11 4.6-1.26 8-5.75 8-11V5l-8-3Zm0 6a3 3 0 0 1 3 3v1h.5a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-4a1 1 0 0 1-1-1H9v-1a3 3 0 0 1 3-3Zm0 2a1 1 0 0 0-1 1v1h2v-1a1 1 0 0 0-1-1Z" />
        </svg>
        <h1 className="text-4xl font-semibold tracking-tight">VaultDocs</h1>
      </div>
      <p className="text-lg text-emerald-300">Authentication successful.</p>
    </main>
  );
}

/** Register exists as a route target only — the page itself is the next task. */
function RegisterPlaceholder() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950 px-6 text-neutral-100">
      <p className="text-neutral-300">Registration is coming soon.</p>
      <a
        href="/login"
        className="text-sm text-emerald-400 hover:text-emerald-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
      >
        Back to sign in
      </a>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AuthenticatedPlaceholder />
          </ProtectedRoute>
        }
      />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPlaceholder />} />
      {/* Unknown routes land on the protected area for now. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
