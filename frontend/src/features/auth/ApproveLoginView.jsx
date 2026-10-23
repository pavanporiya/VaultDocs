/**
 * Approve Login view — the page on the trusted phone/PWA.
 *
 * Opened from the Web Push notification ("Are you trying to sign in to
 * VaultDocs?" / "Yes, it's me" / "No, deny"). Approval is only possible
 * with an authenticated trusted-device session on this browser; the page
 * (and the push itself) never grants access on its own.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import {
  ShieldCheck,
  ShieldX,
  Smartphone,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react';
import '../auth/AuthView.css';

const STATUS_POLL_MS = 4000;

export const ApproveLoginView = ({ onNavigate }) => {
  const urlParams = new URLSearchParams(window.location.search);
  const challengeId = (urlParams.get('challenge') || '').trim();
  const requestedAction =
    urlParams.get('action') === 'approve' || urlParams.get('action') === 'deny'
      ? urlParams.get('action')
      : null;

  const { isAuthenticated, isLoading, approveChallenge, denyChallenge, getChallengeStatus } =
    useAuth();
  const toast = useToast();

  const [phase, setPhase] = useState('checking'); // checking | confirm | busy | approved | denied | blocked | error | expired
  const [message, setMessage] = useState('');
  const autoActionRef = useRef(false);

  const loadStatus = useCallback(async () => {
    if (!challengeId) return 'unknown';
    try {
      const result = await getChallengeStatus(challengeId);
      return result?.status || 'unknown';
    } catch {
      return 'unknown';
    }
  }, [challengeId, getChallengeStatus]);

  const performDecision = useCallback(
    async (decision) => {
      if (!challengeId) return;
      setPhase('busy');
      try {
        if (decision === 'approve') {
          await approveChallenge(challengeId);
          setPhase('approved');
          toast.success('Sign-in approved. The other device can now finish signing in.', 'Approved');
        } else {
          await denyChallenge(challengeId);
          setPhase('denied');
          toast.info('Sign-in denied. The request was blocked.', 'Denied');
        }
      } catch (err) {
        const status = err?.status;
        if (status === 403) {
          setPhase('blocked');
          setMessage(
            err?.message ||
              'This phone is not a trusted device for the account that requested this sign-in.'
          );
        } else if (status === 404) {
          setPhase('error');
          setMessage('This sign-in request no longer exists. It may have expired.');
        } else if (status === 409 || status === 410) {
          setPhase('error');
          setMessage(err?.message || 'This sign-in request has already been handled.');
        } else {
          setPhase('error');
          setMessage(err?.message || 'Could not process the decision. Please try again.');
        }
      }
    },
    [challengeId, approveChallenge, denyChallenge, toast]
  );

  // Determine whether this browser may approve, and honour notification
  // action taps (approve/deny) exactly once.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!challengeId) {
        setPhase('error');
        setMessage('Missing sign-in request. Open this page from your notification.');
        return;
      }

      if (isLoading) return;

      if (!isAuthenticated) {
        setPhase('blocked');
        setMessage(
          'This phone is not signed in to VaultDocs. Sign in on this device first — approval requires a trusted device session.'
        );
        return;
      }

      const status = await loadStatus();
      if (cancelled) return;

      if (status !== 'pending') {
        if (status === 'approved') setPhase('approved');
        else if (status === 'denied') setPhase('denied');
        else if (status === 'expired') {
          setPhase('expired');
          setMessage('This sign-in request has expired. Ask the other device to sign in again.');
        } else if (status === 'cancelled') {
          setPhase('denied');
          setMessage('This sign-in request was cancelled on the other device.');
        } else {
          setPhase('error');
          setMessage('This sign-in request no longer exists.');
        }
        return;
      }

      setPhase('confirm');

      // A tap on the notification action button is the explicit decision.
      if (requestedAction && !autoActionRef.current) {
        autoActionRef.current = true;
        performDecision(requestedAction);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [challengeId, isAuthenticated, isLoading, requestedAction]);

  // While confirming, watch for the pending challenge being resolved
  // elsewhere so this screen stays truthful.
  useEffect(() => {
    if (phase !== 'confirm') return undefined;
    const timer = setInterval(async () => {
      const status = await loadStatus();
      if (status === 'approved') setPhase('approved');
      else if (status === 'denied') setPhase('denied');
      else if (status === 'expired') {
        setPhase('expired');
        setMessage('This sign-in request has expired.');
      } else if (status === 'cancelled') {
        setPhase('denied');
        setMessage('This sign-in request was cancelled.');
      } else if (status === 'unknown') {
        setPhase('error');
        setMessage('This sign-in request no longer exists.');
      }
    }, STATUS_POLL_MS);
    return () => clearInterval(timer);
  }, [phase, loadStatus]);

  const renderContent = () => {
    switch (phase) {
      case 'checking':
        return (
          <div className="vd-auth-state-banner is-sent" role="status">
            <Smartphone size={16} />
            <span>Checking sign-in request&hellip;</span>
          </div>
        );

      case 'busy':
        return (
          <div className="vd-auth-state-banner is-sent" role="status">
            <Clock size={16} />
            <span>Sending your decision&hellip;</span>
          </div>
        );

      case 'confirm':
        return (
          <>
            <div className="vd-auth-state-banner is-sent" role="status">
              <Smartphone size={16} />
              <span>A sign-in to VaultDocs was requested from another device.</span>
            </div>
            <p
              style={{
                textAlign: 'center',
                fontSize: '0.9375rem',
                fontWeight: 600,
                margin: '0.5rem 0',
              }}
            >
              Are you trying to sign in to VaultDocs?
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
              <Button
                variant="primary"
                type="button"
                icon={ShieldCheck}
                fullWidth
                onClick={() => performDecision('approve')}
              >
                Yes, it&rsquo;s me
              </Button>
              <Button
                variant="danger"
                type="button"
                icon={ShieldX}
                fullWidth
                onClick={() => performDecision('deny')}
              >
                No, deny
              </Button>
            </div>
          </>
        );

      case 'approved':
        return (
          <div className="vd-auth-state-banner is-verified" role="status">
            <CheckCircle2 size={16} />
            <span>Sign-in approved. You can return to the other device now.</span>
          </div>
        );

      case 'denied':
        return (
          <div className="vd-auth-error-alert" role="alert">
            <XCircle size={18} />
            <span>{message || 'Sign-in denied. The request was blocked.'}</span>
          </div>
        );

      case 'blocked':
        return (
          <div className="vd-auth-error-alert" role="alert">
            <AlertCircle size={18} />
            <span>{message}</span>
          </div>
        );

      case 'expired':
      case 'error':
      default:
        return (
          <div className="vd-auth-error-alert" role="alert">
            <AlertCircle size={18} />
            <span>{message || 'This sign-in request cannot be processed.'}</span>
          </div>
        );
    }
  };

  return (
    <div className="vd-auth-page">
      <Card className="vd-auth-card" elevation="md" padding="lg">
        <div className="vd-auth-header">
          <div className="vd-auth-logo-badge">
            <ShieldCheck size={24} />
          </div>
          <h2 className="vd-auth-title">Sign-In Approval</h2>
          <p className="vd-auth-subtitle">VaultDocs device approval</p>
        </div>
        {renderContent()}
        <div className="vd-auth-footer">
          <button
            type="button"
            className="vd-auth-link-btn"
            onClick={() => onNavigate && onNavigate('dashboard')}
          >
            Go to VaultDocs
          </button>
        </div>
      </Card>
    </div>
  );
};

export default ApproveLoginView;
