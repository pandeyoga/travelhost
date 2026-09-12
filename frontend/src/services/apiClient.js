import axios from "axios";
import { DEFAULT_LANG, getLang } from "@/lib/lang";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Satu instance untuk semua call (kontrak: lihat docs/08_FRONTEND_GUARDRAILS §1).
const apiClient = axios.create({ baseURL: API });

// CMS-06 — bahasa konten publik dikirim OTOMATIS sebagai `?lang=`.
// Dilakukan di interceptor (bukan di setiap halaman) supaya tidak ada satu pun endpoint
// publik yang lupa dilokalkan saat pengunjung memilih English.
apiClient.interceptors.request.use((config) => {
  const url = String(config.url || "");
  const method = String(config.method || "get").toLowerCase();
  const isPublicRead = method === "get" && (url.startsWith("/public/") || url === "/public");
  if (isPublicRead) {
    const lang = getLang();
    const params = config.params || {};
    if (lang && lang !== DEFAULT_LANG && params.lang === undefined) {
      config.params = { ...params, lang };
    }
  }
  return config;
});

export function setAuthToken(token) {
  if (token) {
    apiClient.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common["Authorization"];
  }
}

export default apiClient;
