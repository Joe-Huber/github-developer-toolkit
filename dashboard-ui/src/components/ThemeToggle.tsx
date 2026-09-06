import type { ThemeMode } from "../lib/theme";
import { useTheme } from "../lib/theme";
import { AutoIcon, MoonIcon, SunIcon } from "./icons";

const OPTIONS: { mode: ThemeMode; label: string; Icon: typeof SunIcon }[] = [
  { mode: "light", label: "Light theme", Icon: SunIcon },
  { mode: "dark", label: "Dark theme", Icon: MoonIcon },
  { mode: "system", label: "System theme", Icon: AutoIcon },
];

export function ThemeToggle() {
  const { mode, setMode } = useTheme();

  return (
    <div
      role="group"
      aria-label="Color theme"
      className="inline-flex items-center rounded-md border border-border bg-bg/40 p-0.5"
    >
      {OPTIONS.map(({ mode: option, label, Icon }) => (
        <button
          key={option}
          type="button"
          aria-pressed={mode === option}
          title={label}
          onClick={() => setMode(option)}
          className={`p-1.5 rounded transition-colors ${
            mode === option
              ? "bg-accent/15 text-accent"
              : "text-muted hover:text-text"
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}
