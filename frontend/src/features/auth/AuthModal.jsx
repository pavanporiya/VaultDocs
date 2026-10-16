import React, { useState, useEffect } from 'react';
import { Modal, Input, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { LogIn, UserPlus, Mail, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import './AuthView.css';
import './AuthModal.css';

export const AuthModal = ({ isOpen, onClose, initialMode = 'login' }) => {
  const [mode, setMode] = useState(initialMode); // 'login' | 'register' | 'otp'
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // OTP inputs & states
  const [otpCode, setOtpCode] = useState('');
  const [otpState, setOtpState] = useState('idle'); // 'idle' | 'sent' | 'invalid' | 'expired' | 'verified' | 'error'
  const [resending, setResending] = useState(false);
  const [resendTimer, setResendTimer] = useState(0);

  const { login, register, verifyOtp, resendOtp } = useAuth();
  const toast = useToast();

  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
      setError('');
      setOtpCode('');
      setOtpState('idle');
    }
  }, [isOpen, initialMode]);

  useEffect(() => {
    if (resendTimer <= 0) return;
    const interval = setInterval(() => {
      setResendTimer((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [resendTimer]);

  const resetForm = () => {
    setFullName('');
    setEmail('');
    setPassword('');
    setOtpCode('');
    setError('');
    setOtpState('idle');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!email || !password) {
      setError('Please fill in all required fields.');
      return;
    }

    if (mode === 'register' && !fullName) {
      setError('Please enter your full name.');
      return;
    }

    if (mode === 'register' && password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
        toast.success('Successfully logged in!', 'Welcome Back');
        resetForm();
        onClose();
      } else {
        await register(fullName.trim(), email.trim(), password);
        setMode('otp');
        setOtpState('sent');
        setResendTimer(60);
        toast.info('Verification code sent!', 'Check your Gmail/inbox');
      }
    } catch (err) {
      const isUnverified =
        err?.status === 403 &&
        (err?.data?.detail?.needs_verification ||
          (typeof err?.message === 'string' && err.message.toLowerCase().includes('not verified')));

      if (isUnverified) {
        setMode('otp');
        setOtpState('idle');
        toast.warning('Account not verified yet. Please enter verification code.', 'Verification Needed');
      } else {
        const msg = err?.message || 'Authentication failed.';
        setError(msg);
        toast.error(msg, 'Error');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtpSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const cleanOtp = otpCode.trim();
    if (cleanOtp.length !== 6 || !/^\d{6}$/.test(cleanOtp)) {
      setError('Please enter the 6-digit numeric verification code.');
      setOtpState('invalid');
      return;
    }

    setLoading(true);
    try {
      await verifyOtp(email.trim(), cleanOtp);
      setOtpState('verified');
      toast.success('Account verified and logged in!', 'Welcome to VaultDocs');
      setTimeout(() => {
        resetForm();
        onClose();
      }, 700);
    } catch (err) {
      const msg = err?.message || 'Verification failed. Please try again.';
      setError(msg);
      if (msg.toLowerCase().includes('expired')) {
        setOtpState('expired');
      } else if (msg.toLowerCase().includes('invalid')) {
        setOtpState('invalid');
      } else {
        setOtpState('error');
      }
      toast.error(msg, 'Verification Failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (resendTimer > 0 || resending) return;
    if (!email.trim()) return;

    setResending(true);
    setError('');
    try {
      const res = await resendOtp(email.trim());
      const cooldown = res?.resend_cooldown_seconds || 60;
      setResendTimer(cooldown);
      setOtpState('sent');
      setOtpCode('');
      toast.success('New verification code sent!', 'Check your inbox');
    } catch (err) {
      const msg = err?.message || 'Failed to resend verification code.';
      setError(msg);
      toast.error(msg, 'Resend Failed');
    } finally {
      setResending(false);
    }
  };

  const toggleMode = () => {
    setMode((prev) => (prev === 'login' ? 'register' : 'login'));
    setError('');
  };

  const getTitle = () => {
    if (mode === 'otp') return 'Verify Your Email';
    if (mode === 'register') return 'Create VaultDocs Account';
    return 'Sign In to VaultDocs';
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        resetForm();
        onClose();
      }}
      title={getTitle()}
      size="sm"
    >
      {mode === 'otp' ? (
        <form onSubmit={handleVerifyOtpSubmit} className="vd-auth-form" noValidate>
          <div style={{ textAlign: 'center', marginBottom: '0.25rem' }}>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted, #64748b)', margin: 0 }}>
              Enter the 6-digit code sent to
            </p>
            <div className="vd-auth-email-tag" style={{ marginTop: '0.375rem' }}>
              <Mail size={12} />
              <span>{email}</span>
            </div>
          </div>

          {otpState === 'sent' && (
            <div className="vd-auth-state-banner is-sent" role="status">
              <CheckCircle2 size={16} />
              <span>Verification code dispatched. Check your Gmail inbox.</span>
            </div>
          )}

          {otpState === 'invalid' && (
            <div className="vd-auth-state-banner is-invalid" role="alert">
              <AlertCircle size={16} />
              <span>{error || 'Invalid verification code.'}</span>
            </div>
          )}

          {otpState === 'expired' && (
            <div className="vd-auth-state-banner is-expired" role="alert">
              <AlertCircle size={16} />
              <span>Verification code expired. Request a new code below.</span>
            </div>
          )}

          {otpState === 'verified' && (
            <div className="vd-auth-state-banner is-verified" role="status">
              <CheckCircle2 size={16} />
              <span>Account verified!</span>
            </div>
          )}

          {otpState === 'error' && error && (
            <div className="vd-auth-error-alert" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <div className="vd-otp-input-wrapper">
            <label htmlFor="modal-otp-input" className="vd-otp-label">
              6-Digit Verification Code
            </label>
            <input
              id="modal-otp-input"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="······"
              value={otpCode}
              onChange={(e) => {
                const val = e.target.value.replace(/\D/g, '').slice(0, 6);
                setOtpCode(val);
                if (error) setError('');
              }}
              className="vd-otp-input"
              disabled={loading || otpState === 'verified'}
              autoFocus
            />
            <span className="vd-otp-hint">Enter the 6 numbers from your email</span>
          </div>

          <div className="vd-auth-actions">
            <Button
              variant="primary"
              type="submit"
              loading={loading}
              disabled={otpCode.trim().length !== 6 || otpState === 'verified'}
              icon={CheckCircle2}
              fullWidth
            >
              {otpState === 'verified' ? 'Verified!' : 'Verify & Continue'}
            </Button>
          </div>

          <div className="vd-auth-resend-row">
            <span className="vd-auth-countdown">
              {resendTimer > 0 ? `Resend in ${resendTimer}s` : "Didn't receive the code?"}
            </span>
            <button
              type="button"
              className="vd-auth-link-btn"
              disabled={resendTimer > 0 || resending || loading}
              onClick={handleResendOtp}
            >
              {resending ? (
                <>
                  <RefreshCw size={12} className="vd-spin" /> Sending...
                </>
              ) : (
                'Resend Code'
              )}
            </button>
          </div>

          <div className="vd-auth-toggle-row">
            <button
              type="button"
              className="vd-auth-toggle-btn"
              onClick={() => {
                setMode('login');
                setError('');
              }}
            >
              Back to Sign in
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={handleSubmit} className="vd-auth-form" noValidate>
          {error && (
            <div className="vd-auth-error-alert" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          {mode === 'register' && (
            <Input
              label="Full Name"
              placeholder="Jane Doe"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              disabled={loading}
            />
          )}

          <Input
            label="Email Address"
            type="email"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={loading}
          />

          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            helperText={mode === 'register' ? 'Minimum 8 characters' : undefined}
            disabled={loading}
          />

          {mode === 'login' && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '-0.375rem' }}>
              <button
                type="button"
                className="vd-auth-link-btn"
                style={{ fontSize: '0.8125rem' }}
                onClick={() => {
                  onClose();
                  window.history.pushState({}, '', '/forgot-password');
                  window.dispatchEvent(new PopStateEvent('popstate'));
                }}
              >
                Forgot Password?
              </button>
            </div>
          )}

          <div className="vd-auth-actions">
            <Button
              variant="primary"
              type="submit"
              loading={loading}
              icon={mode === 'login' ? LogIn : UserPlus}
              fullWidth
            >
              {mode === 'login' ? 'Sign In' : 'Create Account'}
            </Button>
          </div>

          <div className="vd-auth-toggle-row">
            <span>
              {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}
            </span>
            <button type="button" className="vd-auth-toggle-btn" onClick={toggleMode}>
              {mode === 'login' ? 'Register now' : 'Sign in'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
};

export default AuthModal;

