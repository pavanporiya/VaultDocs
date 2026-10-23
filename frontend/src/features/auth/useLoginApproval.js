/**
 * Shared state for the "Check your phone to approve this sign-in" waiting
 * screen used by LoginView and AuthModal.
 *
 * Handles: polling the challenge status (push delivery), email approval
 * code submission, resend with cooldown, cancel, and terminal states
 * (approved / denied / expired / cancelled) that always block or complete
 * the login deterministically.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../shared/context/AuthContext';

const POLL_INTERVAL_MS = 3000;

export const useLoginApproval = () => {
  const {
    completeChallenge,
    getChallengeStatus,
    cancelChallenge,
    resendChallenge,
  } = useAuth();

  const [challenge, setChallenge] = useState(null); // { challenge_id, delivery, ... }
  const [status, setStatus] = useState('idle'); // 'idle' | 'waiting' | 'approved' | 'denied' | 'expired' | 'cancelled' | 'error'
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState('');
  const [resendIn, setResendIn] = useState(0);
  const [deviceRemembered, setDeviceRemembered] = useState(false);
  const pollRef = useRef(null);
  const finishingRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Full cleanup: stop polling, drop the challenge, kill cooldowns and
  // pending finish callbacks. Used when the modal reopens (fresh sign-in
  // flow) and when the user logs out — no state may survive a session.
  const reset = useCallback(() => {
    stopPolling();
    finishingRef.current = false;
    setChallenge(null);
    setStatus('idle');
    setError('');
    setBusy(false);
    setCode('');
    setResendIn(0);
    setDeviceRemembered(false);
  }, [stopPolling]);

  // Reset everything when a new challenge starts.
  const begin = useCallback(
    (approvalPayload) => {
      stopPolling();
      finishingRef.current = false;
      setChallenge(approvalPayload);
      setStatus('waiting');
      setError('');
      setCode('');
      setDeviceRemembered(false);
      setResendIn(approvalPayload?.resend_cooldown_seconds || 0);
    },
    [stopPolling]
  );

  const finish = useCallback(
    async (challengeId) => {
      if (finishingRef.current) return;
      finishingRef.current = true;
      try {
        const response = await completeChallenge(challengeId);
        setDeviceRemembered(!!response?.device_remembered);
        setStatus('approved');
      } catch (err) {
        finishingRef.current = false;
        const message =
          err?.message || 'Sign-in could not be completed. Please try again.';
        setError(message);
        setStatus('error');
      }
    },
    [completeChallenge]
  );

  // Poll while the phone decision is pending (push delivery only).
  useEffect(() => {
    if (!challenge || status !== 'waiting' || challenge.delivery !== 'push') {
      return undefined;
    }
    const challengeId = challenge.challenge_id;
    pollRef.current = setInterval(async () => {
      try {
        const result = await getChallengeStatus(challengeId);
        if (result?.status === 'approved') {
          stopPolling();
          await finish(challengeId);
        } else if (result?.status === 'denied') {
          stopPolling();
          setStatus('denied');
          setError('Sign-in denied from your trusted device.');
        } else if (result?.status === 'expired') {
          stopPolling();
          setStatus('expired');
          setError('This sign-in request expired. Please sign in again.');
        } else if (result?.status === 'cancelled') {
          stopPolling();
          setStatus('cancelled');
        }
      } catch (err) {
        // 404: challenge no longer exists. Transient errors keep polling.
        if (err?.status === 404) {
          stopPolling();
          setStatus('error');
          setError('Sign-in request not found. Please sign in again.');
        }
      }
    }, POLL_INTERVAL_MS);
    return stopPolling;
  }, [challenge, status, getChallengeStatus, finish, stopPolling]);

  // Resend cooldown countdown.
  useEffect(() => {
    if (resendIn <= 0) return undefined;
    const timer = setInterval(() => setResendIn((prev) => (prev > 0 ? prev - 1 : 0)), 1000);
    return () => clearInterval(timer);
  }, [resendIn]);

  const finishWithCode = useCallback(
    async (cleanCode) => {
      if (finishingRef.current || !challenge) return;
      finishingRef.current = true;
      setBusy(true);
      try {
        const response = await completeChallenge(challenge.challenge_id, {
          approvalCode: cleanCode,
        });
        setDeviceRemembered(!!response?.device_remembered);
        setStatus('approved');
      } catch (err) {
        finishingRef.current = false;
        setError(err?.message || 'Invalid or expired approval code.');
      } finally {
        setBusy(false);
      }
    },
    [challenge, completeChallenge]
  );

  const submitCode = useCallback(async () => {
    const clean = (code || '').trim();
    if (!/^\d{6}$/.test(clean)) {
      setError('Please enter the 6-digit approval code from your email.');
      return;
    }
    setError('');
    await finishWithCode(clean);
  }, [code, finishWithCode]);

  const resend = useCallback(async () => {
    if (!challenge || resendIn > 0) return;
    setBusy(true);
    setError('');
    try {
      const result = await resendChallenge(challenge.challenge_id);
      setResendIn(result?.resend_cooldown_seconds || 60);
      setChallenge((prev) => ({ ...prev, delivery: result?.delivery || prev.delivery }));
    } catch (err) {
      setError(err?.message || 'Could not resend the approval. Please wait and try again.');
    } finally {
      setBusy(false);
    }
  }, [challenge, resendChallenge, resendIn]);

  const cancel = useCallback(async () => {
    if (!challenge) return;
    stopPolling();
    try {
      await cancelChallenge(challenge.challenge_id);
    } catch {
      // Cancellation is best-effort; the challenge expires server-side anyway.
    }
    setStatus('cancelled');
    setChallenge(null);
  }, [challenge, cancelChallenge, stopPolling]);

  return {
    challenge,
    status,
    error,
    busy,
    code,
    setCode,
    resendIn,
    deviceRemembered,
    begin,
    reset,
    submitCode,
    resend,
    cancel,
    isEmailDelivery: challenge?.delivery === 'email',
    isPushDelivery: challenge?.delivery === 'push',
  };
};

export default useLoginApproval;
