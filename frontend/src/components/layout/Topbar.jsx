import { LogOut, Menu, Moon, Sun, UserCog } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useDarkMode } from "../../hooks/useDarkMode";
import { cn } from "../../lib/cn";

export default function Topbar({ title, onMenuClick }) {
  const { isDark, toggle } = useDarkMode();
  const { logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    // logout() ném lỗi nếu phiên đã hết hạn (POST /auth/logout cũng cần
    // auth) — vẫn phải điều hướng về /login, vì ý định người dùng ("đăng
    // xuất") đã đạt được ngay khi phiên không còn hợp lệ (final review Fix 5).
    try {
      await logout();
    } finally {
      navigate("/login");
    }
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-card/80 px-4 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-md p-2 text-muted-foreground hover:bg-muted cursor-pointer lg:hidden"
        aria-label="Mở menu điều hướng"
      >
        <Menu className="h-5 w-5" />
      </button>
      <h1 className="flex-1 truncate text-lg font-semibold text-foreground">{title}</h1>
      <button
        type="button"
        onClick={toggle}
        className="flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      >
        {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
      </button>
      <NavLink
        to="/profile"
        className={({ isActive }) =>
          cn(
            "flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            isActive && "bg-primary/10 text-primary"
          )
        }
        aria-label="Hồ sơ học tập"
      >
        <UserCog className="h-5 w-5" />
      </NavLink>
      <button
        type="button"
        onClick={handleLogout}
        className="flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Đăng xuất"
      >
        <LogOut className="h-5 w-5" />
      </button>
    </header>
  );
}
