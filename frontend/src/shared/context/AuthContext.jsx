import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient, { getAuthToken, setAuthToken } from '../services/apiClient';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setTokenState] = useState(getAuthToken());
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = useCallback(async () => {
    const currentToken = getAuthToken();
    if (!currentToken) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const userData = await apiClient.get('/auth/me');
      setUser(userData);
    } catch {
      // If token is invalid or expired, clear it
      setAuthToken(null);
      setTokenState(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCurrentUser();
  }, [fetchCurrentUser]);

  const login = async (email, password, options = {}) => {
    const response = await apiClient.post('/auth/login', {
      email,
      password,
      remember_device: !!options.rememberDevice,
    });

    // New/untrusted device: the server demands phone (or email) approval
    // first. No token exists yet — hand the challenge to the caller.
    if (response && response.approval_required) {
      return response;
    }

    if (response && response.access_token) {
      setAuthToken(response.access_token);
      setTokenState(response.access_token);
      const userData = await apiClient.get('/auth/me');
      setUser(userData);
      return response;
    }
    throw new Error('Login failed: Token not returned');
  };

  /** Poll the sanitized status of a pending sign-in approval challenge. */
  const getChallengeStatus = (challengeId) =>
    apiClient.get(`/auth/login/challenges/${encodeURIComponent(challengeId)}`);

  /**
   * Finish an approved sign-in challenge. On success the JWT is stored and
   * the user is loaded, exactly like a normal login.
   */
  const completeChallenge = async (challengeId, { approvalCode, deviceName } = {}) => {
    const response = await apiClient.post(
      `/auth/login/challenges/${encodeURIComponent(challengeId)}/complete`,
      {
        approval_code: approvalCode || null,
        device_name: deviceName || null,
      }
    );
    if (response && response.access_token) {
      setAuthToken(response.access_token);
      setTokenState(response.access_token);
      const userData = await apiClient.get('/auth/me');
      setUser(userData);
      return response;
    }
    throw new Error('Sign-in could not be completed.');
  };

  /** Cancel a pending sign-in challenge from this (waiting) browser. */
  const cancelChallenge = (challengeId) =>
    apiClient.post(`/auth/login/challenges/${encodeURIComponent(challengeId)}/cancel`);

  /** Re-send the approval prompt (push re-delivery or a fresh email code). */
  const resendChallenge = (challengeId) =>
    apiClient.post(`/auth/login/challenges/${encodeURIComponent(challengeId)}/resend`);

  /** Approve a pending sign-in from a trusted device (phone/PWA). */
  const approveChallenge = (challengeId) =>
    apiClient.post(`/auth/login/challenges/${encodeURIComponent(challengeId)}/approve`);

  /** Deny a pending sign-in from a trusted device (phone/PWA). */
  const denyChallenge = (challengeId) =>
    apiClient.post(`/auth/login/challenges/${encodeURIComponent(challengeId)}/deny`);

  const register = async (fullName, email, password) => {
    const registerResponse = await apiClient.post('/auth/register', {
      full_name: fullName,
      email,
      password,
    });
    return registerResponse;
  };

  const verifyOtp = async (email, otp) => {
    const response = await apiClient.post('/auth/verify-otp', { email, otp });
    if (response && response.access_token) {
      setAuthToken(response.access_token);
      setTokenState(response.access_token);
      if (response.user) {
        setUser(response.user);
      } else {
        const userData = await apiClient.get('/auth/me');
        setUser(userData);
      }
      return response;
    }
    throw new Error('Verification failed: Access token was not returned.');
  };

  const resendOtp = async (email) => {
    return apiClient.post('/auth/resend-otp', { email });
  };

  const forgotPassword = async (email) => {
    return apiClient.post('/auth/forgot-password', { email });
  };

  const verifyResetToken = async (token, email) => {
    return apiClient.post('/auth/verify-reset-token', {
      token: token ? token.trim().toUpperCase() : '',
      email: email ? email.trim() : undefined,
    });
  };

  const resetPassword = async (token, newPassword, email) => {
    return apiClient.post('/auth/reset-password', {
      token: token ? token.trim().toUpperCase() : '',
      new_password: newPassword,
      email: email ? email.trim() : undefined,
    });
  };

  const logout = () => {
    setAuthToken(null);
    setTokenState(null);
    setUser(null);
  };

  const value = {
    user,
    token,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    verifyOtp,
    resendOtp,
    forgotPassword,
    verifyResetToken,
    resetPassword,
    getChallengeStatus,
    completeChallenge,
    cancelChallenge,
    resendChallenge,
    approveChallenge,
    denyChallenge,
    logout,
    refreshUser: fetchCurrentUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
