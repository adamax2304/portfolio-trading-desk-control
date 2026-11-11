import type { Status } from "./types";
import { StatusDot } from "./components";

export const TABS = [
  { id: "Home", icon: "ti-layout-dashboard" },
  { id: "Signals", icon: "ti-rss" },
  { id: "Trades", icon: "ti-arrows-left-right" },
  { id: "Market", icon: "ti-world" },
  { id: "Risk", icon: "ti-shield-half" },
  { id: "System", icon: "ti-heart-rate-monitor" },
] as const;

function tickAge(ts?: string | null): string {
  if (!ts) return "—";
  const m = (Date.now() - Date.parse(ts)) / 60000;
  return Number.isNaN(m) ? "—" : m < 1 ? "live" : `${m.toFixed(1)}m`;
}

export function TopStatusStrip({ st }: { st?: Status }) {
  const online = !!st?.engine_online;
  return (
    <div className="sticky top-0 z-30" style={{ paddingTop: "var(--safe-t)" }}>
      <div className="glass rounded-none border-x-0 border-t-0 px-4 py-2 flex items-center gap-2 text-[11px]"
        style={{ borderRadius: 0, backdropFilter: "blur(14px)", background: "rgba(7,10,18,0.78)" }}>
        <StatusDot ok={online} />
        <span className="font-medium text-text">{(st?.trading_mode ?? "—").toUpperCase()}</span>
        <span className="text-faint">·</span>
        <span className={online ? "text-profit" : "text-danger"}>{online ? "Engine OK" : "Engine offline"}</span>
        <span className="text-faint">·</span>
        <span className="text-muted tnum">tick {tickAge(st?.last_monitor_tick)}</span>
        <span className="ml-auto badge b-danger">LIVE LOCKED</span>
      </div>
    </div>
  );
}

export function BottomNav({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40">
      <div className="mx-auto max-w-[480px] px-3" style={{ paddingBottom: "calc(var(--safe-b) + 8px)" }}>
        <div className="glass flex justify-around py-1.5 px-1" style={{ borderRadius: 20, background: "rgba(11,16,32,0.92)" }}>
          {TABS.map((t) => {
            const on = tab === t.id;
            return (
              <button key={t.id} onClick={() => onTab(t.id)}
                className={`flex flex-col items-center gap-0.5 py-1.5 px-2 rounded-xl transition ${on ? "text-accent" : "text-faint"}`}
                style={on ? { background: "rgba(53,224,240,0.1)" } : undefined} aria-label={t.id}>
                <i className={`ti ${t.icon} text-[19px] leading-none`} />
                <span className="text-[9.5px] font-medium">{t.id}</span>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
