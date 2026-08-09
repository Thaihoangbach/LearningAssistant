import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "edututor-theme";

function getInitial() {
  if (typeof document === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

export function useDarkMode() {
  const [isDark, setIsDark] = useState(getInitial);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem(STORAGE_KEY, isDark ? "dark" : "light");
  }, [isDark]);

  const toggle = useCallback(() => setIsDark((d) => !d), []);

  return { isDark, toggle };
}
