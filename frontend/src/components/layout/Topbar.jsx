import { Menu, Moon, Sun } from "lucide-react";
import { useDarkMode } from "../../hooks/useDarkMode";

export default function Topbar({ title, onMenuClick }) {
  const { isDark, toggle } = useDarkMode();

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
    </header>
  );
}
