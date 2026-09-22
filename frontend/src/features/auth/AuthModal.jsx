import React, { useState } from 'react';
import { Modal, Input, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { LogIn, UserPlus } from 'lucide-react';
import './AuthModal.css';

export const AuthModal = ({ isOpen, onClose, initialMode = 'login' }) => {
  const [mode, setMode] = useState(initialMode); // 'login' or 'register'
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { login, register } = useAuth();
  const toast = useToast();

  const resetForm = () => {
    setFullName('');
    setEmail('');
    setPassword('');
    setError('');
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

    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
        toast.success('Successfully logged in!', 'Welcome Back');
      } else {
        await register(fullName, email, password);
        toast.success('Account created and logged in!', 'Welcome to VaultDocs');
      }
      resetForm();
      onClose();
    } catch (err) {
      setError(err.message || 'Authentication failed.');
      toast.error(err.message || 'Authentication failed.', 'Error');
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setMode((prev) => (prev === 'login' ? 'register' : 'login'));
    setError('');
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        resetForm();
        onClose();
      }}
      title={mode === 'login' ? 'Sign In to VaultDocs' : 'Create VaultDocs Account'}
      size="sm"
    >
      <form onSubmit={handleSubmit} className="vd-auth-form">
        {error && <div className="vd-auth-error-alert">{error}</div>}

        {mode === 'register' && (
          <Input
            label="Full Name"
            placeholder="Jane Doe"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        )}

        <Input
          label="Email Address"
          type="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <Input
          label="Password"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          helperText={mode === 'register' ? 'Minimum 8 characters' : undefined}
        />

        <div className="vd-auth-actions">
          <Button
            variant="primary"
            type="submit"
            loading={loading}
            icon={mode === 'login' ? LogIn : UserPlus}
            style={{ width: '100%' }}
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
    </Modal>
  );
};

export default AuthModal;
