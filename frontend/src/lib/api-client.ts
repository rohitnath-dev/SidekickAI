import axios from 'axios';
import Cookies from 'js-cookie';

let API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

if (typeof window !== 'undefined') {
  const hostname = window.location.hostname;
  if (hostname.includes('onrender.com')) {
    // If hostname contains -1, strip it to point to backend, e.g. sidekickai-1.onrender.com -> sidekickai.onrender.com
    const backendHost = hostname.replace('-1.onrender.com', '.onrender.com');
    API_BASE_URL = `https://${backendHost}/api/v1`;
  }
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = Cookies.get('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response Interceptor: Handle auth errors and format structured exceptions
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.data && error.response.data.detail) {
      const detail = error.response.data.detail;
      if (typeof detail === 'object' && detail !== null) {
        error.response.data.errorDetails = detail;
        error.response.data.detail = detail.message || JSON.stringify(detail);
      }
    }
    if (error.response && error.response.status === 401) {
      // If unauthorized, clear tokens and redirect to login
      Cookies.remove('access_token');
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
