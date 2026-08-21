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
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    try {
      const token = localStorage.getItem('access_token');
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (e) {
      console.warn('Failed to read access token from localStorage:', e);
    }
  }
  return config;
});

apiClient.interceptors.request.use(
  (config) => {
    const token = Cookies && typeof Cookies.get === 'function' ? Cookies.get('access_token') : undefined;
    if (token && config.headers && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Response Interceptor: Handle auth errors and format structured exceptions
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response && error.response.data && error.response.data.detail) {
      const detail = error.response.data.detail;
      if (typeof detail === 'object' && detail !== null) {
        error.response.data.errorDetails = detail;
        error.response.data.detail = detail.message || JSON.stringify(detail);
      }
    }
    
    // Check if 401 and request wasn't already retried, and is not the refresh request itself
    const isRefreshRequest = originalRequest.url && (originalRequest.url.endsWith('/auth/refresh') || originalRequest.url.includes('/auth/refresh'));
    if (error.response && error.response.status === 401 && !originalRequest._retry && !isRefreshRequest) {
      // Avoid redirecting if we are already on login or register pages
      if (typeof window !== 'undefined' && (window.location.pathname.startsWith('/login') || window.location.pathname.startsWith('/register'))) {
        return Promise.reject(error);
      }
      
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => {
            return apiClient(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }
      
      originalRequest._retry = true;
      isRefreshing = true;
      
      try {
        console.log("[Auth Interceptor] 401 encountered. Attempting silent token refresh...");
        const refreshResponse = await apiClient.post('/auth/refresh');
        if (refreshResponse.data?.access_token) {
          try {
            localStorage.setItem('access_token', refreshResponse.data.access_token);
          } catch (e) {
            console.warn('Failed to save refreshed access token to localStorage:', e);
          }
        }
        isRefreshing = false;
        processQueue(null);
        return apiClient(originalRequest);
      } catch (refreshError) {
        console.error("[Auth Interceptor] Silent refresh failed. Redirecting to login.", refreshError);
        isRefreshing = false;
        processQueue(refreshError);
        
        // Remove access_token cookie/localStorage as backup
        if (typeof window !== 'undefined') {
          try {
            localStorage.removeItem('access_token');
          } catch (e) {
            console.warn('Failed to remove access token from localStorage:', e);
          }
        }
        if (Cookies && typeof Cookies.remove === 'function') {
          Cookies.remove('access_token');
        }
        
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

