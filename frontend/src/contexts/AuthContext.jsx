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

  // Xoá state cục bộ để báo "server nói tôi chưa đăng nhập nữa" — dùng khi
  // logout() thất bại (session đã chết từ trước, xem handleLogout ở
  // Topbar.jsx) hoặc bất kỳ nơi nào khác phát hiện phiên đã hết hạn.
  const handleAuthFailure = useCallback(() => {
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const logout = useCallback(async () => {
    // POST /auth/logout tự nó cần auth — nếu cookie đã hết hạn, gọi này ném
    // lỗi. Vẫn phải dọn state cục bộ trong mọi trường hợp (finally), vì ý
    // định của người dùng ("đăng xuất") coi như đã đạt được ngay khi phiên
    // không còn hợp lệ nữa (final review Fix 4/5).
    try {
      await api.logout();
    } finally {
      handleAuthFailure();
    }
  }, [handleAuthFailure]);

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout, handleAuthFailure }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải được gọi bên trong AuthProvider");
  return ctx;
}
