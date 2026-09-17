import { createContext, useCallback, useContext, useEffect, useState } from "react";
import * as api from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // "unknown" tránh nhấp nháy màn Login lúc F5 trong khi GET /auth/me
  // chưa trả lời — xem docs/auth-spec.md mục 11.
  const [status, setStatus] = useState("unknown");

  useEffect(() => {
    api
      .getCurrentUser()
      .then((u) => {
        setUser(u);
        setStatus("authenticated");
      })
      .catch(() => {
        setUser(null);
        setStatus("unauthenticated");
      });
  }, []);

  const login = useCallback(async (email, password) => {
    const u = await api.login(email, password);
    setUser(u);
    setStatus("authenticated");
    return u;
  }, []);

  const register = useCallback(async (email, password, displayName) => {
    const u = await api.register(email, password, displayName);
    setUser(u);
    setStatus("authenticated");
    return u;
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải được gọi bên trong AuthProvider");
  return ctx;
}
