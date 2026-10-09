import React, { useState } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleNextStep = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Email and password are required');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const authUrl = window.APP_CONFIG?.VITE_AUTH_URL || import.meta.env.VITE_AUTH_URL;
      const response = await axios.post(authUrl, { email, password });
      
      if (response.data && response.data.access_token) {
        const username = email.split('@')[0];
        const displayName = username.charAt(0).toUpperCase() + username.slice(1).toLowerCase();
        login(response.data.access_token, response.data.id || response.data.user_id || "auth-user", displayName);
        navigate('/');
      }
    } catch (err) {
      if (err.response && err.response.status === 400) {
        // OTP is required for this user
        setStep(2);
      } else {
        setError(err.response?.data?.error || err.response?.data?.message || 'Login failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!otp) {
      setError('OTP is required');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const authUrl = window.APP_CONFIG?.VITE_AUTH_URL || import.meta.env.VITE_AUTH_URL;
      
      // We pass username, password, and otp to the external login endpoint
      // Adjust this payload based on your microservice's exact requirements
      const response = await axios.post(authUrl, {
        email,
        password,
        totp_token: otp
      });

      if (response.data && response.data.access_token) {
        const username = email.split('@')[0];
        const displayName = username.charAt(0).toUpperCase() + username.slice(1).toLowerCase();
        login(response.data.access_token, response.data.id, displayName);
        navigate('/');
      } else {
        setError('Invalid response from authentication server');
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.message || 'Login failed. Please check your credentials and OTP.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f7fa' }}>
      <div style={{ background: 'white', padding: '40px', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', width: '350px' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '20px', color: '#333' }}>Wissen Research</h2>
        <h4 style={{ textAlign: 'center', marginBottom: '20px', color: '#666', fontWeight: 'normal' }}>Login to Taxonomy App</h4>
        
        {error && <div style={{ color: '#721c24', background: '#f8d7da', padding: '10px', borderRadius: '4px', marginBottom: '20px', fontSize: '14px' }}>{error}</div>}
        
        {step === 1 ? (
          <form onSubmit={handleNextStep}>
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#555' }}>Email</label>
              <input 
                type="text" 
                value={email} 
                onChange={(e) => setEmail(e.target.value)}
                style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#555' }}>Password</label>
              <input 
                type="password" 
                value={password} 
                onChange={(e) => setPassword(e.target.value)}
                style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', boxSizing: 'border-box' }}
              />
            </div>
            <button type="submit" disabled={loading} style={{ width: '100%', padding: '10px', background: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
              {loading ? 'Checking...' : 'Next'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#555' }}>Enter TOTP (OTP)</label>
              <input 
                type="text" 
                value={otp} 
                onChange={(e) => setOtp(e.target.value)}
                style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', boxSizing: 'border-box', textAlign: 'center', fontSize: '18px', letterSpacing: '4px' }}
                maxLength={6}
              />
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button type="button" onClick={() => setStep(1)} disabled={loading} style={{ flex: 1, padding: '10px', background: '#e2e6ea', color: '#333', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                Back
              </button>
              <button type="submit" disabled={loading} style={{ flex: 2, padding: '10px', background: '#28a745', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
                {loading ? 'Verifying...' : 'Login'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default Login;
