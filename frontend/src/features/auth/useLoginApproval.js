/**
 * Shared state for the email OTP sign-in step used by LoginView and AuthModal.
 *
 * Flow: valid credentials from an untrusted device → 202 challenge → the
 * server emails a single-use 6-digit code → the user enters it (with the
 * optional "Remember this device for 30 days" checkbox) → complete issues
 * the JWT and, when the checkbox was checked, a trusted-device cookie.
 *
 * Handles: code submission, resend with cooldown, cancel, and terminal
 * states (approved / expired / cancelled) that always block or complete
 * the login deterministically. No push notifications or status polling —
 * the email OTP is the only approval channel.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../shared/context/AuthContext';

export const useLoginApproval = () => {
  const { completeChallenge, cancelChallenge, resendChallenge } = useAuth();

  const [challenge, setChallenge] = useState(null); // { challenge_id, delivery: 'email', ... }
  const [status, setStatus] = useState('idle'); // 'idle' | 'waiting' | 'approved' | 'expired' | 'cancelled' | 'error'
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState('');
  const [resendIn, setResendIn] = useState(0);
  const [rememberDevice, setRememberDevice] = useState(false);
  const [deviceRemembered, setDeviceRemembered] = useState(false);
  const finishingRef = useRef(false);

  // Full cleanup: drop the challenge, cooldowns and pending finish
  // callbacks. Used when the modal reopens (fresh sign-in flow) and when
  // the user logs out — no state may survive a session.
  const reset = useCallback(() => {
    finishingRef.current = false;
    setChallenge(null);
    setStatus('idle');
    setError('');
    setBusy(false);
    setCode('');
    setResendIn(0);
    setRememberDevice(false);
    setDeviceRemembered(false);
  }, []);

  // Reset everything when a new challenge starts.
  const begin = useCallback((approvalPayload) => {
    finishingRef.current = false;
    setChallenge(approvalPayload);
    setStatus('waiting');
    setError('');
    setCode('');
    setRememberDevice(false);
    setDeviceRemembered(false);
    setResendIn(approvalPayload?.resend_cooldown_seconds || 0);
  }, []);

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
          rememberDevice,
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
    [challenge, completeChallenge, rememberDevice]
  );

  const submitCode = useCallback(async () => {
    const clean = (code || '').trim();
    if (!/^\d{6}$/.test(clean)) {
      setError('Please enter the 6-digit code from your email.');
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
    } catch (err) {
      setError(err?.message || 'Could not resend the code. Please wait and try again.');
    } finally {
      setBusy(false);
    }
  }, [challenge, resendChallenge, resendIn]);

  const cancel = useCallback(async () => {
    if (!challenge) return;
    try {
      await cancelChallenge(challenge.challenge_id);
    } catch {
      // Cancellation is best-effort; the challenge expires server-side anyway.
    }
    setStatus('cancelled');
    setChallenge(null);
  }, [challenge, cancelChallenge]);

  return {
    challenge,
    status,
    error,
    busy,
    code,
    setCode,
    resendIn,
    rememberDevice,
    setRememberDevice,
    deviceRemembered,
    begin,
    reset,
    submitCode,
    resend,
    cancel,
  };
};

export default useLoginApproval;
