import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

// Read a non-httpOnly cookie
function readCookie(name) {
  const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]+)"));
  return m ? decodeURIComponent(m[2]) : null;
}

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

// Attach CSRF header for state-changing requests
api.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const csrf = readCookie("kavach_csrf");
    if (csrf) config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

// Auto-refresh on expired access token
let refreshing = null;

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config || {};
    const status = err.response?.status;
    const detail = err.response?.data?.detail;

    const isAuthEndpoint =
      original.url?.includes("/auth/refresh") ||
      original.url?.includes("/auth/request-otp") ||
      original.url?.includes("/auth/verify-otp") ||
      original.url?.includes("/auth/logout");

    if (status === 401 && !original._retried && !isAuthEndpoint) {
      original._retried = true;
      try {
        if (!refreshing) {
          refreshing = api.post("/auth/refresh").finally(() => {
            refreshing = null;
          });
        }
        await refreshing;
        return api(original);
      } catch (_) {
        // fall through to reject
      }
    }
    return Promise.reject(err);
  }
);

export default api;
