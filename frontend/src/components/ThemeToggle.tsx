import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";

declare global {
  interface Window {
    /** Posé par night-navy/theme-toggle (importé dans main.tsx). */
    NightNavy?: { current: () => Theme; set: (theme: Theme | null) => void; toggle: () => void };
  }
}

/** Bascule clair / sombre du design system Night Navy ; sans choix, le thème suit le système. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => window.NightNavy?.current() ?? "light");

  useEffect(() => {
    const sync = () => setTheme(window.NightNavy?.current() ?? "light");
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    document.documentElement.addEventListener("nn-themechange", sync);
    media?.addEventListener("change", sync);
    return () => {
      document.documentElement.removeEventListener("nn-themechange", sync);
      media?.removeEventListener("change", sync);
    };
  }, []);

  const label = theme === "dark" ? "Passer en mode clair" : "Passer en mode sombre";
  return (
    <button
      type="button"
      onClick={() => window.NightNavy?.toggle()}
      aria-label={label}
      title={label}
      className="nn-icon-btn"
    >
      {theme === "dark" ? <Sun className="h-[17px] w-[17px]" aria-hidden /> : <Moon className="h-[17px] w-[17px]" aria-hidden />}
    </button>
  );
}
