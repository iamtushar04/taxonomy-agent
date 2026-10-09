import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [userId, setUserId] = useState(localStorage.getItem('user_id'));
  const [userName, setUserName] = useState(localStorage.getItem('user_name') || '');

  useEffect(() => {
    if (token) {
      localStorage.setItem('access_token', token);
    } else {
      localStorage.removeItem('access_token');
    }
    
    if (userId) {
      localStorage.setItem('user_id', userId);
    } else {
      localStorage.removeItem('user_id');
    }
    
    if (userName) {
      localStorage.setItem('user_name', userName);
    } else {
      localStorage.removeItem('user_name');
    }
  }, [token, userId, userName]);

  const login = (newToken, newUserId, newUserName) => {
    setToken(newToken);
    setUserId(newUserId);
    if (newUserName) {
      setUserName(newUserName);
    }
  };

  const logout = () => {
    setToken(null);
    setUserId(null);
    setUserName('');
  };

  return (
    <AuthContext.Provider value={{ token, userId, userName, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
