import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('prediction_wallet_api_key');
  if (token && config.headers) {
    // @ts-ignore - Handle Axios header type differences
    config.headers['X-API-KEY'] = token;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Optionally handle global errors, e.g., 401 unauthenticated
    return Promise.reject(error);
  }
);
