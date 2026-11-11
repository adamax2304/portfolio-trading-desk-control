import type { ReactNode } from "react";
import type { ActStatus, Signal } from "./types";

// ---- formatting helpers ----------------------------------------------------
export const fmt = (n?: number | null) =>
  n == null ? "—" : Math.abs(n) >= 1000 ? n.toLocaleString(undefined, { maximumFractionDigits: 1 })
    : Math.abs(n) < 10 ? n.toFixed(3) : n.toFixed(2);
export const fmtR = (r?: number | null) => (r == null ? "—" : `${r >= 0 ? "+" : ""}${r.toFixed(1)}R`);
export const fmtUsd = (n?: number | null) => (n == null ? "—" : `${n >= 0 ? "+" : "-"}$${Math.abs(n).toFixed(1)}`);
export function rel(ts?: string | null): string {
  if (!ts) return "—";
  const ms = Date.now() - Date.parse(ts);
  if (Number.isNaN(ms)) return "—";
  const m = Math.floor(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
}

// ---- badges ----------------------------------------------------------------
const ACT_BADGE: Record<ActStatus, { cls: string; text: string }> = {
  actionable: { cls: "b-profit", text: "ACTIONABLE" },
  shadow: { cls: "b-shadow", text: "SHADOW ONLY" },
  late: { cls: "b-warn", text: "DO NOT CHASE" },
  blocked: { cls: "b-muted", text: "BLOCKED" },
  closed: { cls: "b-muted", text: "CLOSED" },
};
export const ActionabilityBadge = ({ s }: { s: ActStatus }) =>
  <span className={`badge ${ACT_BADGE[s].cls}`}>{ACT_BADGE[s].text}</span>;

export function StatusDot({ ok }: { ok: boolean }) {
  return <span className={`inline-block w-2 h-2 rounded-full ${ok ? "bg-profit" : "bg-danger"} animate-pulseDot`}
    style={{ boxShadow: ok ? "0 0 8px #27d18b" : "0 0 8px #ff5d6c" }} />;
}

export function ModeBadge({ mode }: { mode: string }) {
  const m = (mode || "").toLowerCase();
  const cls = m === "paper" ? "b-accent" : m === "disabled" ? "b-muted" : "b-danger";
  return <span className={`badge ${cls}`}>{(mode || "—").toUpperCase()}</span>;
}

export function badgeTone(b: string): string {
  const t = b.toLowerCase();
  if (t.includes("shadow")) return "b-shadow";
  if (t.includes("do not") || t.includes("very late") || t.includes("squeeze")) return "b-danger";
  if (t.includes("late") || t.includes("half-size")) return "b-warn";
  if (t.includes("catalyst") || t.includes("manual actionable")) return "b-accent";
  if (t.includes("ok") || t.includes("fresh")) return "b-profit";
  return "b-muted";
}
export const Badge = ({ tone = "b-muted", children }: { tone?: string; children: ReactNode }) =>
  <span className={`badge ${tone}`}>{children}</span>;

// ---- metric card -----------------------------------------------------------
export function MetricCard({ label, value, tone = "text-text", sub }:
  { label: string; value: ReactNode; tone?: string; sub?: ReactNode }) {
  return (
    <div className="glass-soft p-3.5 animate-rise">
      <div className="label">{label}</div>
      <div className={`metric mt-1.5 ${tone}`}>{value}</div>
      {sub && <div className="text-[11px] text-faint mt-1">{sub}</div>}
    </div>
  );
}

// ---- sparkline (tiny inline svg) -------------------------------------------
export function Sparkline({ points, tone = "#35e0f0", w = 64, h = 22 }:
  { points: number[]; tone?: string; w?: number; h?: number }) {
  if (!points || points.length < 2) return null;
  const min = Math.min(...points), max = Math.max(...points), span = max - min || 1;
  const d = points.map((p, i) => `${(i / (points.length - 1)) * w},${h - ((p - min) / span) * h}`).join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={d} fill="none" stroke={tone} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ---- KV ---------------------------------------------------------------------
export function KV({ k, v, tone = "" }: { k: string; v: ReactNode; tone?: string }) {
  // min-w-0 lets the cell shrink inside a grid; break-words wraps long price strings
  // instead of overflowing the card on narrow widths.
  return <div className="min-w-0"><div className="label truncate">{k}</div><div className={`tnum text-[13px] mt-0.5 break-words ${tone}`}>{v}</div></div>;
}

// compact KV for dense price rows — smaller mono, wraps, optionally spans the full row.
export function KVsm({ k, v, tone = "", full = false }: { k: string; v: ReactNode; tone?: string; full?: boolean }) {
  return <div className={`min-w-0 ${full ? "col-span-2" : ""}`}><div className="label truncate">{k}</div><div className={`tnum text-[12px] mt-0.5 break-words leading-tight ${tone}`}>{v}</div></div>;
}

// ---- signal card -----------------------------------------------------------
export function SignalCard({ s, onChart, onManual }:
  { s: Signal; onChart: (s: Signal) => void; onManual: (s: Signal) => void }) {
  const a = s.actionability;
  const canManual = a.actionable && a.status === "actionable";
  const blocked = !canManual;
  return (
    <div className={`glass p-3.5 mb-3 animate-rise ${blocked ? "opacity-[0.82]" : ""}`}
      style={canManual ? { borderColor: "rgba(39,209,139,0.35)", boxShadow: "0 0 0 1px rgba(39,209,139,0.18), 0 18px 40px -28px #000" } : undefined}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-semibold text-[15px] truncate">
            {s.symbol} <span className={`text-[12px] font-normal ${s.direction === "short" ? "text-danger" : "text-profit"}`}>{s.direction?.toUpperCase()}</span>
          </div>
          <div className="text-[11px] text-muted mt-0.5">{s.asset_class} · {s.mode} · Tier {s.tier} · {Math.round(s.score)}{s.narrative ? ` · ${s.narrative}` : ""}</div>
        </div>
        <ActionabilityBadge s={a.status} />
      </div>

      {(s.entry_low || s.entry_high) && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-2 mt-3">
          <KVsm k="Entry" v={s.entry_low && s.entry_high && s.entry_low !== s.entry_high ? `${fmt(s.entry_low)}–${fmt(s.entry_high)}` : fmt(s.entry_trigger ?? s.entry_low ?? s.entry_high)} />
          <KVsm k="Stop" v={fmt(s.stop_loss)} tone="text-danger" />
          <KVsm k="TP1 / TP2 / TP3" v={`${fmt(s.tp1)} / ${fmt(s.tp2)} / ${fmt(s.tp3)}`} tone="text-profit" full />
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 mt-3 overflow-hidden">
        {a.badges.slice(0, 5).map((b, i) => <Badge key={i} tone={badgeTone(b)}>{b}</Badge>)}
      </div>

      {blocked && a.reasons.length > 0 && (
        <div className="text-[11px] text-faint mt-2.5 leading-relaxed">{a.reasons.join(" · ")}</div>
      )}

      <div className="flex gap-2 mt-3">
        <button className="btn flex-1" onClick={() => onChart(s)}>Chart</button>
        {canManual
          ? <button className="btn btn-accent flex-1" onClick={() => onManual(s)}>Manual Entry</button>
          : <button className="btn flex-1" disabled>Not actionable</button>}
      </div>
    </div>
  );
}

// ---- trade card ------------------------------------------------------------
// A trade is "closed/resolved" determined WITHOUT the legacy final_r — from the outcome class /
// display status / close time / paper-execution R. (final_r is a legacy touch metric, never used
// to drive UI state or shown as a result.)
const _TERMINAL_OC = ["win", "loss", "flat", "expired_unresolved", "no_entry", "needs_review"];
export function isClosedTrade(s: Signal): boolean {
  if (s.close_time != null) return true;
  if (s.paper_execution_r != null) return true;
  if (s.outcome_class && _TERMINAL_OC.includes(s.outcome_class)) return true;
  const ds = s.display_status ?? "";
  return ds.startsWith("closed") || ds === "entered_unresolved_expired" || ds === "no_entry_expired";
}

// PART 7 — partial-exit lifecycle label for OPEN positions (keep after TP1).
function partialLifecycle(s: Signal): { label: string; tone: string; nextTp?: number } | null {
  if (isClosedTrade(s)) return null;                  // closed handled elsewhere
  if (!s.entry_triggered && !s.entry_triggered_at) return null;
  if (s.tp3_hit) return { label: "TP3 filled · closing", tone: "b-profit" };
  if (s.tp2_hit) return { label: "TP2 filled · runner to TP3", tone: "b-profit", nextTp: s.tp3 };
  if (s.tp1_hit) return { label: "TP1 filled · waiting TP2/TP3", tone: "b-profit", nextTp: s.tp2 };
  return { label: "Entry filled · waiting TP1", tone: "b-accent", nextTp: s.tp1 };
}

export function TradeCard({ s, onClick }: { s: Signal; onClick: () => void }) {
  const closed = isClosedTrade(s);
  // authoritative R = paper execution (USD net is the real PnL); never lead with the touch final_r
  const pnlTone = closed ? ((s.paper_execution_r ?? 0) >= 0 ? "text-profit" : "text-danger") : "text-muted";
  const plc = partialLifecycle(s);
  return (
    <div className="glass p-3.5 mb-3 animate-rise cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
      role="button" tabIndex={0} aria-label={`Open ${s.symbol} ${s.direction ?? ""} detail`}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}>
      <div className="flex items-center justify-between">
        <div className="font-semibold text-[15px]">{s.symbol} <span className={`text-[12px] font-normal ${s.direction === "short" ? "text-danger" : "text-profit"}`}>{s.direction?.toUpperCase()}</span></div>
        <div className={`text-[15px] font-semibold tnum ${pnlTone}`}>{closed ? (s.paper_execution_r != null ? fmtR(s.paper_execution_r) : "—") : s.actionability.status}</div>
      </div>
      {plc && (
        <div className="mt-2"><Badge tone={plc.tone}>{plc.label}</Badge></div>
      )}
      <div className="grid grid-cols-3 gap-2 mt-2.5">
        <KV k="Entry" v={fmt(s.entry_trigger ?? s.entry_low)} />
        <KV k="Stop" v={fmt(s.stop_loss)} tone="text-danger" />
        <KV k={closed ? "Exit" : (plc?.nextTp ? "Next TP" : "TP1")} v={fmt(plc?.nextTp ?? s.tp1)} tone="text-profit" />
      </div>
      {!closed && s.entry_triggered_at && (
        <div className="text-[11px] text-faint mt-2">live {rel(s.entry_triggered_at)} · {s.mode}</div>
      )}
      {closed && (
        <div className="text-[11px] text-faint mt-2">{s.operator_label ?? s.display_status ?? s.paper_execution_outcome ?? s.final_outcome} · MFE {fmt(s.mfe_r)}R · MAE {fmt(s.mae_r)}R · {s.news_supported ? "catalyst" : "technical"}</div>
      )}
    </div>
  );
}

// ---- feedback states -------------------------------------------------------
export const Skeleton = ({ h = 96 }: { h?: number }) => <div className="skel mb-3" style={{ height: h }} />;
export function SkeletonList({ n = 4, h = 110 }: { n?: number; h?: number }) {
  return <>{Array.from({ length: n }).map((_, i) => <Skeleton key={i} h={h} />)}</>;
}

export function EmptyState({ icon = "○", title, sub }: { icon?: string; title: string; sub?: string }) {
  return (
    <div className="glass-soft p-8 text-center animate-rise">
      <div className="text-3xl text-faint mb-2">{icon}</div>
      <div className="text-[14px] font-medium">{title}</div>
      {sub && <div className="text-[12px] text-faint mt-1">{sub}</div>}
    </div>
  );
}

export function ErrorBanner({ msg, onRetry }: { msg: string; onRetry?: () => void }) {
  return (
    <div className="glass p-4 mb-3" style={{ borderColor: "rgba(255,93,108,0.4)" }}>
      <div className="text-[13px] text-danger font-medium">Connection problem</div>
      <div className="text-[12px] text-faint mt-1">{msg}</div>
      {onRetry && <button className="btn btn-danger mt-3" onClick={onRetry}>Retry</button>}
    </div>
  );
}
