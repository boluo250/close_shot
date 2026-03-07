import axios from "axios";
import { useAuthStore } from "../stores/auth";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";
let isHandlingUnauthorized = false;

export const api = axios.create({
  baseURL,
  timeout: 15000
});

api.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${auth.token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status;
    const auth = useAuthStore();
    if (status === 401 && auth.token && !isHandlingUnauthorized) {
      isHandlingUnauthorized = true;
      auth.logout();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
      setTimeout(() => {
        isHandlingUnauthorized = false;
      }, 300);
    }
    return Promise.reject(error);
  }
);

