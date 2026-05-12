import axios from "axios";
import { useAuthStore } from "../stores/auth";
import { ADMIN_LOGIN_PATH } from "./adminSecurity";

const envBaseURL = import.meta.env.VITE_API_BASE_URL;
const DEFAULT_API_BASE_URL =
  typeof window !== "undefined" && window.location?.origin ? window.location.origin : "";
const baseURL =
  typeof envBaseURL === "string" && envBaseURL.trim()
    ? envBaseURL.trim()
    : DEFAULT_API_BASE_URL;
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
      if (window.location.pathname !== ADMIN_LOGIN_PATH) {
        window.location.href = ADMIN_LOGIN_PATH;
      }
      setTimeout(() => {
        isHandlingUnauthorized = false;
      }, 300);
    }
    return Promise.reject(error);
  }
);
