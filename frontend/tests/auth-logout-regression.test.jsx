/**
 * Regression tests for the logout / stale sign-in-approval UI bugs:
 *
 * 1. After an approved sign-in, logging out must clear auth state, the stale
 *    "Sign-in approved! You are now signed in" success banner, the challenge
 *    state, timers and pending callbacks.
 * 2. Clicking Navbar "Sign In" after logout must open a fresh login flow —
 *    never a resurrected approval panel.
 * 3. Closing the modal mid-approval and reopening must also start fresh.
 * 4. Trusted-device bypass: the frontend signs in immediately only when the
 *    SERVER returns a token (bypass itself is server-verified); an untrusted
 *    device gets an approval challenge and NO token client-side.
 * 5. Reload/session restoration: a stored token restores the user; logout
 *    clears it.
 * 6. Full-page LoginView: logout clears the approved banner/challenge.
 *
 * All network traffic is faked in-process — no live server, no real accounts.
 */
import React, { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

import AuthModal from '../src/features/auth/AuthModal';
import LoginView from '../src/features/auth/LoginView';
import Navbar from '../src/shared/components/Navbar/Navbar';
import ToastProvider from '../src/shared/components/Toast/ToastContext';
import { AuthProvider, useAuth } from '../src/shared/context/AuthContext';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const USER = { id: 'u-1', email: 'tester@example.com', full_name: 'Tester' };

const APPROVAL_202 = {
  approval_required: true,
  challenge_id: 'challenge-1',
  delivery: 'email',
  message: 'Approve this sign-in with the code we emailed you.',
  expires_in_seconds: 300,
  resend_cooldown_seconds: 60,
};

const APPROVED_COMPLETE = {
  access_token: 'jwt-approved',
  token_type: 'bearer',
  device_remembered: false,
};

const json = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: {
    get: (header) =>
      String(header).toLowerCase() === 'content-type' ? 'application/json' : null,
  },
  json: async () => body,
  text: async () => JSON.stringify(body),
});

/**
 * Install an in-process fetch fake. Unmatched routes return 404 so nothing
 * ever reaches a real network or server.
 */
function installFetch({ login, complete } = {}) {
  const calls = [];
  const mock = vi.fn(async (url, options = {}) => {
    const path = String(url);
    const method = String(options.method || 'GET').toUpperCase();
    calls.push(`${method} ${path}`);

    if (method === 'POST' && path.endsWith('/auth/login')) {
      return login ? login() : json(401, { detail: 'Invalid email or password.' });
    }
    if (
      method === 'POST' &&
      path.includes('/auth/login/challenges/') &&
      path.endsWith('/complete')
    ) {
      return complete ? complete() : json(409, { detail: 'Not approved yet.' });
    }
    if (method === 'GET' && path.endsWith('/auth/me')) {
      return json(200, USER);
    }
    return json(404, { detail: `Unhandled by test fake: ${method} ${path}` });
  });
  globalThis.fetch = mock;
  return { mock, calls };
}

const originalFetch = globalThis.fetch;

/** Mirrors App.jsx wiring: Navbar Sign In / logout + AuthModal. */
function Harness() {
  const { user, logout, isAuthenticated } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState('login');

  const open = (requestedMode = 'login') => {
    setMode(requestedMode);
    setIsOpen(true);
  };

  return (
    <>
      <Navbar
        onToggleSidebar={() => {}}
        user={isAuthenticated && user ? user : null}
        onOpenAuthModal={open}
        onLogout={logout}
        onNavigate={() => {}}
        searchQuery=""
        onSearchChange={() => {}}
      />
      <AuthModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        initialMode={mode}
      />
    </>
  );
}

/** Minimal session probe used for restoration / logout assertions. */
function SessionProbe() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  if (isLoading) return <div>restoring session…</div>;
  return (
    <div>
      <span data-testid="state">{isAuthenticated ? 'authed' : 'anon'}</span>
      {user && <span data-testid="email">{user.email}</span>}
      <button type="button" onClick={logout}>
        TEST-LOGOUT
      </button>
    </div>
  );
}

/** Logout control for the full-page LoginView (stand-in for Navbar logout). */
function LogoutProbe() {
  const { logout } = useAuth();
  return (
    <button type="button" onClick={logout}>
      TEST-LOGOUT
    </button>
  );
}

const renderHarness = () =>
  render(
    <AuthProvider>
      <ToastProvider>
        <Harness />
      </ToastProvider>
    </AuthProvider>
  );

const renderSessionProbe = () =>
  render(
    <AuthProvider>
      <ToastProvider>
        <SessionProbe />
      </ToastProvider>
    </AuthProvider>
  );

const renderLoginView = () =>
  render(
    <AuthProvider>
      <ToastProvider>
        <LoginView onNavigate={() => {}} />
        <LogoutProbe />
      </ToastProvider>
    </AuthProvider>
  );

const dialog = () => screen.getByRole('dialog');
const queryDialog = () => screen.queryByRole('dialog');

const STALE_BANNER = /Sign-in approved! You are now signed in/;

const fillCredentials = (scope) => {
  const root = scope || dialog();
  fireEvent.change(within(root).getByLabelText(/^Email Address/), {
    target: { value: USER.email },
  });
  fireEvent.change(within(root).getByLabelText(/^Password/), {
    target: { value: 'Password123!' },
  });
  fireEvent.submit(within(root).getByLabelText(/^Password/).closest('form'));
};

const submitApprovalCode = async (scope) => {
  const root = scope || dialog();
  fireEvent.change(await within(root).findByLabelText('6-Digit Approval Code'), {
    target: { value: '123456' },
  });
  fireEvent.click(within(root).getByRole('button', { name: /Approve & Sign In/ }));
};

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

// ---------------------------------------------------------------------------
// 1. Logout + stale modal + fresh Sign In reopen
// ---------------------------------------------------------------------------

describe('logout and stale approval modal', () => {
  it('approval success then logout: Sign In reopens a fresh login flow with no stale banner', async () => {
    installFetch({
      login: () => json(202, APPROVAL_202),
      complete: () => json(200, APPROVED_COMPLETE),
    });
    renderHarness();

    // Open modal and start an approval-required login.
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    fillCredentials();
    await within(dialog()).findByText(/Check your email to approve this sign-in/);
    expect(localStorage.getItem('vaultdocs_token')).toBeNull();

    // Approve with the email code.
    await submitApprovalCode();
    await screen.findByText(STALE_BANNER);

    // Session established, then the modal auto-closes (700ms).
    await waitFor(() => expect(screen.getByTitle('Log Out')).toBeTruthy());
    await waitFor(() => expect(queryDialog()).toBeNull(), { timeout: 4000 });

    // Logout clears auth state.
    fireEvent.click(screen.getByTitle('Log Out'));
    await waitFor(() => expect(localStorage.getItem('vaultdocs_token')).toBeNull());
    expect(screen.queryByText(STALE_BANNER)).toBeNull();

    // Navbar "Sign In" must open a FRESH login form — not the stale popup.
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    await waitFor(() => expect(queryDialog()).not.toBeNull());
    expect(within(dialog()).getByLabelText(/^Email Address/)).toBeTruthy();
    expect(within(dialog()).getByLabelText(/^Password/)).toBeTruthy();
    expect(screen.queryByText(STALE_BANNER)).toBeNull();
    expect(within(dialog()).queryByText(/Check your email to approve/)).toBeNull();

    // No stale pending timer may close or mutate the reopened modal.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 900));
    });
    expect(queryDialog()).not.toBeNull();
    expect(within(dialog()).getByLabelText(/^Email Address/)).toBeTruthy();
    expect(screen.queryByText(STALE_BANNER)).toBeNull();
  });

  it('closing the modal mid-approval and clicking Sign In starts a fresh flow', async () => {
    installFetch({
      login: () => json(202, APPROVAL_202),
      complete: () => json(200, APPROVED_COMPLETE),
    });
    renderHarness();

    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    fillCredentials();
    await within(dialog()).findByText(/Check your email to approve this sign-in/);
    expect(
      within(dialog()).getByRole('button', { name: /Cancel this sign-in request/ })
    ).toBeTruthy();

    // Close the modal while the approval challenge is still pending.
    fireEvent.click(within(dialog()).getByLabelText('Close dialog'));
    await waitFor(() => expect(queryDialog()).toBeNull());

    // Reopen: the stale waiting panel must not resurrect.
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    await waitFor(() => expect(queryDialog()).not.toBeNull());
    expect(within(dialog()).getByLabelText(/^Email Address/)).toBeTruthy();
    expect(within(dialog()).queryByText(/Check your email to approve/)).toBeNull();
    expect(
      within(dialog()).queryByRole('button', { name: /Cancel this sign-in request/ })
    ).toBeNull();
    expect(screen.queryByText(STALE_BANNER)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 2. Trusted vs untrusted device (frontend contract of the server bypass)
// ---------------------------------------------------------------------------

describe('trusted vs untrusted device sign-in', () => {
  it('trusted device: signs in immediately when the server issues a token, no approval step', async () => {
    installFetch({
      login: () =>
        json(200, {
          access_token: 'jwt-trusted-device',
          token_type: 'bearer',
          device_remembered: true,
        }),
      complete: () => json(409, { detail: 'must not be called' }),
    });
    renderHarness();

    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    fillCredentials();

    await waitFor(() => expect(queryDialog()).toBeNull());
    expect(localStorage.getItem('vaultdocs_token')).toBe('jwt-trusted-device');
    expect(screen.queryByText(/Check your email to approve/)).toBeNull();
    expect(screen.queryByText(/Check your phone to approve/)).toBeNull();
    await screen.findByTitle('Log Out');
  });

  it('untrusted device: approval challenge required and NO token issued client-side', async () => {
    installFetch({
      login: () => json(202, APPROVAL_202),
      complete: () => json(200, APPROVED_COMPLETE),
    });
    renderHarness();

    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
    fillCredentials();

    await within(dialog()).findByText(/Check your email to approve this sign-in/);
    // The bypass is server-decided; an untrusted device never gets a token
    // in the login response, so nothing is stored client-side.
    expect(localStorage.getItem('vaultdocs_token')).toBeNull();
    expect(screen.queryByTitle('Log Out')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 3. Reload / session restoration
// ---------------------------------------------------------------------------

describe('session restoration on reload', () => {
  it('restores the user from a stored token, and logout clears the session', async () => {
    localStorage.setItem('vaultdocs_token', 'jwt-restored');
    const { calls } = installFetch();
    renderSessionProbe();

    await screen.findByTestId('email');
    expect(screen.getByTestId('state').textContent).toBe('authed');
    expect(screen.getByTestId('email').textContent).toBe(USER.email);
    expect(calls.some((call) => call.endsWith('/v1/auth/me'))).toBe(true);

    fireEvent.click(screen.getByText('TEST-LOGOUT'));
    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('anon')
    );
    expect(screen.queryByTestId('email')).toBeNull();
    expect(localStorage.getItem('vaultdocs_token')).toBeNull();
  });

  it('fresh load without a stored token restores nothing and never calls /auth/me', async () => {
    const { calls } = installFetch();
    renderSessionProbe();

    await screen.findByTestId('state');
    expect(screen.getByTestId('state').textContent).toBe('anon');
    expect(calls.some((call) => call.endsWith('/v1/auth/me'))).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 4. Full-page LoginView: logout clears the approved banner and challenge
// ---------------------------------------------------------------------------

describe('LoginView logout cleanup', () => {
  it('logout after an approved sign-in clears the success banner and shows a fresh form', async () => {
    installFetch({
      login: () => json(202, APPROVAL_202),
      complete: () => json(200, APPROVED_COMPLETE),
    });
    renderLoginView();

    fillCredentials(document.body);
    await screen.findByText(/Check your email to approve this sign-in/);

    await submitApprovalCode(document.body);
    await screen.findByText(STALE_BANNER);

    // Logout while the approved banner (and its pending redirect timer) lives.
    fireEvent.click(screen.getByText('TEST-LOGOUT'));

    await waitFor(() => expect(screen.queryByText(STALE_BANNER)).toBeNull());
    expect(
      screen.queryByRole('button', { name: /Cancel this sign-in request/ })
    ).toBeNull();
    expect(screen.getByLabelText(/^Email Address/)).toBeTruthy();
    expect(screen.getByLabelText(/^Password/)).toBeTruthy();
    expect(localStorage.getItem('vaultdocs_token')).toBeNull();
  });
});
