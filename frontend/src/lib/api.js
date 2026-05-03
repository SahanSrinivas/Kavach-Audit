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

// Auto-refresh on expired access token + global network-error toast
let refreshing = null;
let networkErrorShown = false;

function notifyNetworkError(detail) {
  if (networkErrorShown) return;
  networkErrorShown = true;
  setTimeout(() => (networkErrorShown = false), 4000);
  // Lazy import to avoid SSR/test issues
  import("sonner")
    .then(({ toast }) => {
      toast.error("Couldn't reach Kavach servers", {
        description: detail || "Please check your connection and retry.",
      });
    })
    .catch(() => {});
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config || {};
    const status = err.response?.status;

    // Network/CORS/timeout — no response object
    if (!err.response) {
      notifyNetworkError();
      return Promise.reject(err);
    }

    // 5xx — backend is up but unhappy
    if (status >= 500 && status <= 599) {
      notifyNetworkError("Server is having a moment. Please retry.");
    }

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
