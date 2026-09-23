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

  const login = async (email, password) => {
    const response = await apiClient.post('/auth/login', { email, password });
    if (response && response.access_token) {
      setAuthToken(response.access_token);
      setTokenState(response.access_token);
      const userData = await apiClient.get('/auth/me');
      setUser(userData);
      return userData;
    }
    throw new Error('Login failed: Token not returned');
  };

  const register = async (fullName, email, password) => {
    const userData = await apiClient.post('/auth/register', {
      full_name: fullName,
      email,
      password,
    });
    // Auto login after registration
    await login(email, password);
    return userData;
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
