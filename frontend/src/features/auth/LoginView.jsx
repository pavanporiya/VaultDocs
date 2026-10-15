import React, { useState, useEffect } from 'react';
import { Card, Input, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { LogIn, Shield, AlertCircle, Mail, CheckCircle2, RefreshCw, ArrowLeft } from 'lucide-react';
import './AuthView.css';

export const LoginView = ({ onNavigate }) => {
  // Step: 'login' | 'otp'
  const [step, setStep] = useState('login');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [unverifiedEmail, setUnverifiedEmail] = useState('');

  // OTP inputs & states
  const [otpCode, setOtpCode] = useState('');
  const [otpState, setOtpState] = useState('idle'); // 'idle' | 'sent' | 'invalid' | 'expired' | 'verified' | 'error'
  const [resending, setResending] = useState(false);
  const [resendTimer, setResendTimer] = useState(0);

  const { login, verifyOtp, resendOtp } = useAuth();
  const toast = useToast();

  // Handle live countdown timer for OTP resend cooldown
  useEffect(() => {
    if (resendTimer <= 0) return;
    const interval = setInterval(() => {
      setResendTimer((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [resendTimer]);

  const validate = () => {
    if (!email.trim()) {
      setError('Email address is required.');
      return false;
    }
    if (!/\S+@\S+\.\S+/.test(email)) {
      setError('Please enter a valid email address.');
      return false;
    }
    if (!password) {
      setError('Password is required.');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setUnverifiedEmail('');

    if (!validate()) return;

    setLoading(true);
    try {
      await login(email, password);
      toast.success('Successfully logged in!', 'Welcome Back');
      if (onNavigate) {
        onNavigate('dashboard');
      }
    } catch (err) {
      const isUnverified =
        err?.status === 403 &&
        (err?.data?.detail?.needs_verification ||
          (typeof err?.message === 'string' && err.message.toLowerCase().includes('not verified')));

      const msg = err?.message || 'Invalid email or password.';
      setError(msg);

      if (isUnverified) {
        const targetEmail = err?.data?.detail?.email || email.trim();
        setUnverifiedEmail(targetEmail);
        toast.warning('Account not verified yet. Verification code required.', 'Verification Needed');
      } else {
        toast.error(msg, 'Login Failed');
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
      const targetEmail = unverifiedEmail || email.trim();
      await verifyOtp(targetEmail, cleanOtp);
      setOtpState('verified');
      toast.success('Account verified and logged in!', 'Welcome to VaultDocs');
      setTimeout(() => {
        if (onNavigate) {
          onNavigate('dashboard');
        }
      }, 800);
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

    const targetEmail = unverifiedEmail || email.trim();
    if (!targetEmail) return;

    setResending(true);
    setError('');
    try {
      const res = await resendOtp(targetEmail);
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

  const switchToOtp = () => {
    setStep('otp');
    setError('');
    setOtpState('idle');
  };

  const switchToLogin = () => {
    setStep('login');
    setError('');
    setOtpCode('');
    setOtpState('idle');
  };

  // Step 2: OTP Verification Mode
  if (step === 'otp') {
    const activeEmail = unverifiedEmail || email.trim();
    return (
      <div className="vd-auth-page">
        <Card className="vd-auth-card" elevation="md" padding="lg">
          <div className="vd-auth-header">
            <div className="vd-auth-logo-badge">
              <Mail size={24} />
            </div>
            <h2 className="vd-auth-title">Verify Your Email</h2>
            <p className="vd-auth-subtitle">
              Enter the 6-digit verification code sent to
            </p>
            {activeEmail && (
              <div className="vd-auth-email-tag">
                <Mail size={12} />
                <span>{activeEmail}</span>
              </div>
            )}
          </div>

          <form onSubmit={handleVerifyOtpSubmit} className="vd-auth-form" noValidate>
            {otpState === 'sent' && (
              <div className="vd-auth-state-banner is-sent" role="status">
                <CheckCircle2 size={16} />
                <span>Verification code dispatched. Check your Gmail inbox.</span>
              </div>
            )}

            {otpState === 'invalid' && (
              <div className="vd-auth-state-banner is-invalid" role="alert">
                <AlertCircle size={16} />
                <span>{error || 'Invalid verification code. Please check and try again.'}</span>
              </div>
            )}

            {otpState === 'expired' && (
              <div className="vd-auth-state-banner is-expired" role="alert">
                <AlertCircle size={16} />
                <span>Verification code has expired. Request a new code below.</span>
              </div>
            )}

            {otpState === 'verified' && (
              <div className="vd-auth-state-banner is-verified" role="status">
                <CheckCircle2 size={16} />
                <span>Account verified! Loading your secure workspace...</span>
              </div>
            )}

            {otpState === 'error' && error && (
              <div className="vd-auth-error-alert" role="alert">
                <AlertCircle size={18} />
                <span>{error}</span>
              </div>
            )}

            <div className="vd-otp-input-wrapper">
              <label htmlFor="login-otp-input" className="vd-otp-label">
                6-Digit Verification Code
              </label>
              <input
                id="login-otp-input"
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
                {otpState === 'verified' ? 'Verified!' : 'Verify Email & Sign In'}
              </Button>
            </div>

            <div className="vd-auth-resend-row">
              <span className="vd-auth-countdown">
                {resendTimer > 0 ? (
                  `Resend available in ${resendTimer}s`
                ) : (
                  "Didn't receive the code?"
                )}
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

            <div className="vd-auth-footer">
              <button
                type="button"
                className="vd-auth-link-btn"
                onClick={switchToLogin}
                disabled={loading}
              >
                <ArrowLeft size={14} style={{ display: 'inline', marginRight: 4 }} />
                Back to Sign In
              </button>
            </div>
          </form>
        </Card>
      </div>
    );
  }

  // Step 1: Normal Sign In Form
  return (
    <div className="vd-auth-page">
      <Card className="vd-auth-card" elevation="md" padding="lg">
        <div className="vd-auth-header">
          <div className="vd-auth-logo-badge">
            <Shield size={24} />
          </div>
          <h2 className="vd-auth-title">Sign In to VaultDocs</h2>
          <p className="vd-auth-subtitle">Enter your credentials to access your workspace</p>
        </div>

        <form onSubmit={handleSubmit} className="vd-auth-form" noValidate>
          {unverifiedEmail ? (
            <div
              className="vd-auth-state-banner is-invalid"
              style={{
                flexDirection: 'column',
                alignItems: 'flex-start',
                gap: '0.625rem',
                padding: '0.875rem 1rem',
              }}
              role="alert"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertCircle size={18} />
                <span>{error}</span>
              </div>
              <Button
                variant="secondary"
                size="sm"
                type="button"
                onClick={switchToOtp}
                icon={Mail}
              >
                Enter Verification Code
              </Button>
            </div>
          ) : (
            error && (
              <div className="vd-auth-error-alert" role="alert">
                <AlertCircle size={18} />
                <span>{error}</span>
              </div>
            )
          )}

          <Input
            label="Email Address"
            type="email"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (unverifiedEmail) setUnverifiedEmail('');
            }}
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
            disabled={loading}
          />

          <div className="vd-auth-actions">
            <Button
              variant="primary"
              type="submit"
              loading={loading}
              icon={LogIn}
              fullWidth
            >
              Sign In
            </Button>
          </div>

          <div className="vd-auth-footer">
            <span>Don't have an account?</span>
            <button
              type="button"
              className="vd-auth-link-btn"
              onClick={() => onNavigate && onNavigate('register')}
            >
              Register now
            </button>
          </div>

          <div style={{ textAlign: 'center', marginTop: '-0.25rem' }}>
            <button
              type="button"
              className="vd-auth-link-btn"
              style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted, #64748b)' }}
              onClick={switchToOtp}
            >
              Have a verification code? Verify here
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default LoginView;

