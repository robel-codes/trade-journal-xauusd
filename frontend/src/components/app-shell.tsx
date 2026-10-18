"use client";
import { BarChart3, BookOpen, CandlestickChart, Database, FileText, FlaskConical, LayoutDashboard, LibraryBig, LogOut, Moon, Settings, Sun, Trophy } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { cx } from "./ui";

type Me = { id: string; email: string; display_name: string };
type SettingsT = { timezone: string; theme: "dark" | "light"; base_currency: string; sessions: { key: string; label: string; timezone: string; start: string; end: string }[] };

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/journal", label: "Journal", icon: BookOpen },
  { href: "/strategies", label: "Strategy Library", icon: LibraryBig },
  { href: "/research", label: "Research", icon: FlaskConical },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { href: "/data", label: "Market Data", icon: Database },
  { href: "/charts", label: "Charts", icon: CandlestickChart },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

const Ctx = createContext<{ settings: SettingsT | undefined; reloadSettings: () => void; tz: string }>({ settings: undefined, reloadSettings: () => {}, tz: "UTC" });
export const useAppSettings = () => useContext(Ctx);

export function setTheme(theme: "dark" | "light") {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("xau.theme", theme); } catch {}
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const me = useApi<Me>("/auth/me");
  const settings = useApi<SettingsT>("/settings");
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => { if (settings.data) setTheme(settings.data.theme); }, [settings.data]);
  useEffect(() => { setNow(new Date()); const t = setInterval(() => setNow(new Date()), 30_000); return () => clearInterval(t); }, []);
  const tz = settings.data?.timezone ?? "UTC";

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  }
  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    setTheme(next);
    api("/settings", { method: "PUT", json: { theme: next } }).catch(() => {});
  }

  return (
    <Ctx.Provider value={{ settings: settings.data, reloadSettings: settings.reload, tz }}>
      <div className="flex h-full min-h-screen">
        <aside className="sticky top-0 flex h-screen w-[212px] shrink-0 flex-col border-r border-line bg-panel">
          <div className="flex h-12 items-center gap-2 border-b border-line px-4">
            <BarChart3 className="size-4 text-accent" aria-hidden />
            <span className="text-[13px] font-semibold tracking-wide">XAU LAB</span>
            <span className="num ml-auto text-[10.5px] text-fg-faint">v0.1</span>
          </div>
          <nav aria-label="Main" className="flex-1 overflow-y-auto p-2">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? path === "/" : path.startsWith(href);
              return (
                <Link key={href} href={href} aria-current={active ? "page" : undefined}
                  className={cx("mb-0.5 flex h-8 items-center gap-2.5 rounded-[5px] px-2.5 text-[13px]",
                    active ? "bg-accent-soft text-fg" : "text-fg-dim hover:bg-panel-2 hover:text-fg")}>
                  <Icon className={cx("size-4", active ? "text-accent" : "")} aria-hidden />{label}
                </Link>
              );
            })}
          </nav>
          <div className="border-t border-line p-3 text-[11.5px] text-fg-faint">
            <div className="truncate text-fg-dim">{me.data?.display_name || me.data?.email || " "}</div>
            <div className="num mt-0.5">{now ? new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short" }).format(now) : "—"} · {tz}</div>
            <div className="mt-2 flex gap-1">
              <button type="button" onClick={toggleTheme} className="flex h-7 flex-1 items-center justify-center gap-1.5 rounded border border-line hover:text-fg cursor-pointer" aria-label="Toggle light or dark theme">
                <Sun className="size-3.5 [[data-theme=light]_&]:hidden" /><Moon className="hidden size-3.5 [[data-theme=light]_&]:block" />Theme
              </button>
              <button type="button" onClick={logout} className="flex h-7 flex-1 items-center justify-center gap-1.5 rounded border border-line hover:text-fg cursor-pointer">
                <LogOut className="size-3.5" />Sign out
              </button>
            </div>
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-6 py-5">{children}</main>
      </div>
    </Ctx.Provider>
  );
}
