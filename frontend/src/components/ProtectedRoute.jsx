import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

// "unknown" chưa render gì (tránh nhấp nháy Login lúc F5 trước khi GET
// /auth/me trả lời — docs/auth-spec.md mục 11), KHÔNG coi là chưa đăng nhập.
export default function ProtectedRoute() {
  const { status } = useAuth();

  if (status === "unknown") return null;
  if (status === "unauthenticated") return <Navigate to="/login" replace />;
  return <Outlet />;
}
