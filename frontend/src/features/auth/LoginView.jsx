import React, { useState } from 'react';
import { Card, Input, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { LogIn, Shield, AlertCircle } from 'lucide-react';
import './AuthView.css';

export const LoginView = ({ onNavigate }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { login } = useAuth();
  const toast = useToast();

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

    if (!validate()) return;

    setLoading(true);
    try {
      await login(email, password);
      toast.success('Successfully logged in!', 'Welcome Back');
      if (onNavigate) {
        onNavigate('dashboard');
      }
    } catch (err) {
      const msg = err?.message || 'Invalid email or password.';
      setError(msg);
      toast.error(msg, 'Login Failed');
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
          <h2 className="vd-auth-title">Sign In to VaultDocs</h2>
          <p className="vd-auth-subtitle">Enter your credentials to access your workspace</p>
        </div>

        <form onSubmit={handleSubmit} className="vd-auth-form" noValidate>
          {error && (
            <div className="vd-auth-error-alert" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
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
        </form>
      </Card>
    </div>
  );
};

export default LoginView;
