/** Centered auth-area loading / retryable-error state (shared, minimal). */

interface AuthLoadingProps {
  message?: string;
  action?: { label: string; onClick: () => void };
}

export function AuthLoading({ message, action }: AuthLoadingProps) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950 px-6 text-neutral-100">
      <div className="flex items-center gap-2">
        <BrandMark className="h-6 w-6" />
        <span className="text-lg font-semibold tracking-tight">VaultDocs</span>
      </div>

      {message === undefined ? (
        <div
          className="mt-2 h-6 w-6 animate-spin rounded-full border-2 border-neutral-700 border-t-emerald-400"
          role="status"
          aria-label="Loading"
        />
      ) : (
        <div className="mt-2 flex flex-col items-center gap-3 text-center">
          <p className="max-w-sm text-sm text-neutral-400">{message}</p>
          {action !== undefined && (
            <button
              type="button"
              onClick={action.onClick}
              className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-200 transition-colors hover:border-neutral-500 hover:bg-neutral-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
            >
              {action.label}
            </button>
          )}
        </div>
      )}
    </main>
  );
}

/** VaultDocs shield/lock mark (inline SVG, no icon dependency). */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className={className}>
      <path d="M12 2 4 5v6c0 5.25 3.4 9.74 8 11 4.6-1.26 8-5.75 8-11V5l-8-3Zm0 6a3 3 0 0 1 3 3v1h.5a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-4a1 1 0 0 1-1-1H9v-1a3 3 0 0 1 3-3Zm0 2a1 1 0 0 0-1 1v1h2v-1a1 1 0 0 0-1-1Z" />
    </svg>
  );
}
