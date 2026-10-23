/**
 * Pending sign-in approval panel: "Check your phone to approve this sign-in."
 *
 * Shared by LoginView and AuthModal. Handles push waiting (poll), the email
 * approval-code fallback, resend with cooldown, and cancel. Denials,
 * expiry and cancellations always block the login.
 */
import React from 'react';
import { Button } from '../../shared/components';
import {
  Smartphone,
  Mail,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  ArrowLeft,
} from 'lucide-react';

export const LoginApprovalPanel = ({ approval, onBack }) => {
  const {
    challenge,
    status,
    error,
    busy,
    code,
    setCode,
    resendIn,
    deviceRemembered,
    submitCode,
    resend,
    cancel,
    isEmailDelivery,
    isPushDelivery,
  } = approval;

  // Terminal: approved (token issued, user loaded by the hook's caller
  // through AuthContext state).
  if (status === 'approved') {
    return (
      <div className="vd-auth-state-banner is-verified" role="status">
        <CheckCircle2 size={16} />
        <span>
          Sign-in approved! You are now signed in
          {deviceRemembered ? ' and this device will be remembered for 30 days.' : '.'}
        </span>
      </div>
    );
  }

  if (status === 'denied' || status === 'expired' || status === 'cancelled') {
    const message =
      status === 'denied'
        ? 'Sign-in denied from your trusted device. This request was blocked.'
        : status === 'expired'
          ? 'This sign-in request expired. Please sign in again.'
          : 'Sign-in request cancelled.';
    return (
      <div className="vd-auth-error-alert" role="alert">
        <XCircle size={18} />
        <span>{message}</span>
        {onBack && (
          <Button variant="outline" size="sm" type="button" onClick={onBack} icon={ArrowLeft}>
            Back to Sign In
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="vd-auth-approval-panel" role="status">
      {status === 'error' && error && (
        <div className="vd-auth-error-alert" role="alert">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {isPushDelivery && (
        <>
          <div className="vd-auth-state-banner is-sent">
            <Smartphone size={16} />
            <span>Check your phone to approve this sign-in.</span>
          </div>
          <p
            style={{
              fontSize: '0.8125rem',
              color: 'var(--color-text-muted, #64748b)',
              textAlign: 'center',
              margin: 0,
            }}
          >
            We sent a notification to your trusted device:
            &ldquo;Are you trying to sign in to VaultDocs?&rdquo; Tap
            &ldquo;Yes, it&rsquo;s me&rdquo; to continue or &ldquo;No, deny&rdquo; to block this
            sign-in. Waiting&hellip;
          </p>
        </>
      )}

      {isEmailDelivery && (
        <>
          <div className="vd-auth-state-banner is-sent">
            <Mail size={16} />
            <span>Check your email to approve this sign-in.</span>
          </div>
          <p
            style={{
              fontSize: '0.8125rem',
              color: 'var(--color-text-muted, #64748b)',
              textAlign: 'center',
              margin: 0,
            }}
          >
            No trusted phone is registered, so we emailed you a 6-digit approval code
            {challenge?.message ? ` — ${challenge.message.toLowerCase()}` : ''}. Enter it below
            to finish signing in.
          </p>
          <div className="vd-otp-input-wrapper">
            <label htmlFor="approval-code-input" className="vd-otp-label">
              6-Digit Approval Code
            </label>
            <input
              id="approval-code-input"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="······"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="vd-otp-input"
              disabled={busy}
              autoFocus
            />
          </div>
          <div className="vd-auth-actions">
            <Button
              variant="primary"
              type="button"
              loading={busy}
              disabled={code.length !== 6}
              onClick={submitCode}
              icon={CheckCircle2}
              fullWidth
            >
              Approve &amp; Sign In
            </Button>
          </div>
          <div className="vd-auth-resend-row">
            <span className="vd-auth-countdown">
              {resendIn > 0 ? `Resend available in ${resendIn}s` : "Didn't receive the code?"}
            </span>
            <button
              type="button"
              className="vd-auth-link-btn"
              disabled={resendIn > 0 || busy}
              onClick={resend}
            >
              {resendIn > 0 ? (
                <>
                  <RefreshCw size={12} className="vd-spin" /> Sending...
                </>
              ) : (
                'Resend Code'
              )}
            </button>
          </div>
        </>
      )}

      {isPushDelivery && status === 'waiting' && (
        <div className="vd-auth-resend-row">
          <span className="vd-auth-countdown">
            {resendIn > 0 ? `Resend available in ${resendIn}s` : "Didn't get the notification?"}
          </span>
          <button
            type="button"
            className="vd-auth-link-btn"
            disabled={resendIn > 0 || busy}
            onClick={resend}
          >
            <RefreshCw size={12} /> Re-send
          </button>
        </div>
      )}

      <div className="vd-auth-footer">
        <button type="button" className="vd-auth-link-btn" disabled={busy} onClick={cancel}>
          <Clock size={14} style={{ display: 'inline', marginRight: 4 }} />
          Cancel this sign-in request
        </button>
        {onBack && (
          <button type="button" className="vd-auth-link-btn" disabled={busy} onClick={onBack}>
            <ArrowLeft size={14} style={{ display: 'inline', marginRight: 4 }} />
            Back to Sign In
          </button>
        )}
      </div>
    </div>
  );
};

export default LoginApprovalPanel;
