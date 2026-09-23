import React, { useState } from 'react';
import { Card, Input, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { UserPlus, Shield, AlertCircle } from 'lucide-react';
import './AuthView.css';

export const RegisterView = ({ onNavigate }) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { register } = useAuth();
  const toast = useToast();

  const validate = () => {
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validate()) return;

    setLoading(true);
    try {
      await register(fullName.trim(), email.trim(), password);
      toast.success('Account created successfully!', 'Welcome to VaultDocs');
      if (onNavigate) {
        onNavigate('dashboard');
      }
    } catch (err) {
      const msg = err?.message || 'Registration failed. Please try again.';
      setError(msg);
      toast.error(msg, 'Registration Error');
    } finally {
      setLoading(false);
    }
  };

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

        <form onSubmit={handleSubmit} className="vd-auth-form" noValidate>
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
              Create Account
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
