import { createContext, useCallback, useContext, useEffect, useState } from "react";
import apiClient, { setAuthToken } from "@/services/apiClient";

const AuthContext = createContext(null);
const TOKEN_KEY = "tf_token";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      if (!token) {
        setLoading(false);
        return;
      }
      setAuthToken(token);
      try {
        const res = await apiClient.get("/auth/me");
        if (active) setUser(res.data);
      } catch (e) {
        if (active) {
          localStorage.removeItem(TOKEN_KEY);
          setAuthToken(null);
          setToken(null);
          setUser(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [token]);

  const login = useCallback(async (email, password) => {
    const res = await apiClient.post("/auth/login", { email, password });
    const { token: t, user: u } = res.data;
    localStorage.setItem(TOKEN_KEY, t);
    setAuthToken(t);
    setUser(u);
    setToken(t);
    return u;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch (e) {
      // abaikan — tetap bersihkan sesi lokal
    }
    localStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
    setUser(null);
    setToken(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth harus dipakai di dalam AuthProvider");
  return ctx;
}
