import axios from 'axios';

const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || import.meta.env.VITE_API_URL;

const axiosClient = axios.create({
  baseURL: API_BASE_URL,
});

// Interceptor to inject the token into every request
axiosClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => Promise.reject(error));

// Interceptor to handle global 401 Unauthorized errors
axiosClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_id');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default axiosClient;
