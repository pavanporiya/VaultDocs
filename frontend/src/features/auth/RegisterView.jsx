import React, { useState, useEffect } from 'react';
import { Card, Input, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { UserPlus, Shield, AlertCircle, Mail, CheckCircle2, RefreshCw, ArrowLeft } from 'lucide-react';
import './AuthView.css';

export const RegisterView = ({ onNavigate }) => {
  // Step: 'form' | 'otp'
  const [step, setStep] = useState('form');

  // Form inputs
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // OTP inputs
  const [otpCode, setOtpCode] = useState('');

  // Loading & state management: 'idle' | 'sending' | 'sent' | 'invalid' | 'expired' | 'verified' | 'error'
  const [otpState, setOtpState] = useState('idle');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState('');

  // Resend cooldown timer in seconds
  const [resendTimer, setResendTimer] = useState(0);

  const { register, verifyOtp, resendOtp } = useAuth();
  const toast = useToast();

  // Handle live countdown timer for OTP resend cooldown
  useEffect(() => {
    if (resendTimer <= 0) return;
    const interval = setInterval(() => {
      setResendTimer((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [resendTimer]);

  const validateForm = () => {
    if (!fullName.trim() || fullName.trim().length < 2) {
      setError('Full Name must be at least 2 characters.');
      return false;
    }
    if (!email.trim()) {
      setError('Email address is required.');
      return false;
    }
    if (!/\S+@\S+\.\S+/.test(email)) {
      setError('Please enter a valid email address.');
      return false;
    }
    if (!password || password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return false;
    }
    return true;
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validateForm()) return;

    setLoading(true);
    setOtpState('sending');
    try {
      await register(fullName.trim(), email.trim(), password);
      setStep('otp');
      setOtpState('sent');
      setResendTimer(60);
      toast.info('Verification code sent!', 'Check your Gmail/inbox');
    } catch (err) {
      const msg = err?.message || 'Registration failed. Please try again.';
      setError(msg);
      setOtpState('error');
      toast.error(msg, 'Registration Error');
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
      toast.success('Account verified successfully!', 'Welcome to VaultDocs');
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

  // Render Step 2: OTP Verification Screen
  if (step === 'otp') {
    return (
      <div className="vd-auth-page">
        <Card className="vd-auth-card" elevation="md" padding="lg">
          <div className="vd-auth-header">
            <div className="vd-auth-logo-badge">
              <Mail size={24} />
            </div>
            <h2 className="vd-auth-title">Verify Your Email</h2>
            <p className="vd-auth-subtitle">
              We dispatched a 6-digit verification code to
            </p>
            <div className="vd-auth-email-tag">
              <Mail size={12} />
              <span>{email}</span>
            </div>
          </div>

          <form onSubmit={handleVerifyOtpSubmit} className="vd-auth-form" noValidate>
            {/* Contextual Status Banners */}
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

            {/* OTP 6-Digit Input */}
            <div className="vd-otp-input-wrapper">
              <label htmlFor="otp-input" className="vd-otp-label">
                6-Digit Verification Code
              </label>
              <input
                id="otp-input"
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
                {otpState === 'verified' ? 'Verified!' : 'Verify Email'}
              </Button>
            </div>

            {/* Resend Cooldown Row */}
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

            {/* Back to Edit Email */}
            <div className="vd-auth-footer">
              <button
                type="button"
                className="vd-auth-link-btn"
                onClick={() => {
                  setStep('form');
                  setError('');
                }}
                disabled={loading}
              >
                <ArrowLeft size={14} style={{ display: 'inline', marginRight: 4 }} />
                Wrong email address? Go back
              </button>
            </div>
          </form>
        </Card>
      </div>
    );
  }

  // Render Step 1: Initial Registration Form
  return (
    <div className="vd-auth-page">
      <Card className="vd-auth-card" elevation="md" padding="lg">
        <div className="vd-auth-header">
          <div className="vd-auth-logo-badge">
            <Shield size={24} />
          </div>
          <h2 className="vd-auth-title">Create VaultDocs Account</h2>
          <p className="vd-auth-subtitle">Join VaultDocs to securely store and share documents</p>
        </div>

        <form onSubmit={handleRegisterSubmit} className="vd-auth-form" noValidate>
          {error && (
            <div className="vd-auth-error-alert" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <Input
            label="Full Name"
            placeholder="Jane Doe"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            disabled={loading}
          />

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
            helperText="Minimum 8 characters"
            disabled={loading}
          />

          <div className="vd-auth-actions">
            <Button
              variant="primary"
              type="submit"
              loading={loading}
              icon={UserPlus}
              fullWidth
            >
              {loading ? 'Sending Code...' : 'Create Account'}
            </Button>
          </div>

          <div className="vd-auth-footer">
            <span>Already have an account?</span>
            <button
              type="button"
              className="vd-auth-link-btn"
              onClick={() => onNavigate && onNavigate('login')}
            >
              Sign in
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default RegisterView;
