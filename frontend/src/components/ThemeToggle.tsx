import { useTheme, type Theme } from "../theme/ThemeProvider";

const OPTIONS: { value: Theme; label: string }[] = [
  { value: "calm", label: "Calm" },
  { value: "dark", label: "Dark" },
  { value: "cyber", label: "Cyber" },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={theme === o.value}
          onClick={() => setTheme(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}