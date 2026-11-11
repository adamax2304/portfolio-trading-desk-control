import { useState, useEffect } from "react";
import type { ReactNode } from "react";
import type { Signal, TradeLifecycle, TradeCalendarDay, TradePnlAnalytics } from "./types";
import { api, haptic, hapticNotify } from "./api";
import {
  useStatus, useSignals, useTrades, useChart, useMarket, useRisk, useHealth,
  useAudit, useCommands, useDashboard, useClosed, useClosedAnalytics, useNearWinners, usePaperFeatures, usePortfolio, usePortfolioCompare, usePortfolioByAsset, useChartEvents, useLifecycle, useMarketDashboard, queryClient,
  useStocksPositionSummary, useStocksPositionCandidates, useNewsSourceHealth, useNewsEntityHealth, useNewsCatalysts,
  useCryptoOverlayReport, useCryptoOverlaySignal,
} from "./query";
import {
  MetricCard, SignalCard, TradeCard, Badge, ActionabilityBadge, StatusDot,
  EmptyState, SkeletonList, Skeleton, ErrorBanner, KV, fmt, fmtR, fmtUsd, rel, badgeTone, isClosedTrade,
} from "./components";
import { ChartPanel } from "./Chart";
import { RiskEditModal } from "./RiskEditModal";
import type { EditTarget } from "./RiskEditModal";

// ================================================================ HOME =====
export function Home({ go, onPause }: { go: (t: string) => void; onPause: () => void }) {
  const pf = usePaperFeatures();
  const port = usePortfolio();
  const cmp = usePortfolioCompare();
  const byAsset = usePortfolioByAsset();
  const st = useStatus();
  const sig = useSignals();
  const health = useHealth();
  const dash = useDashboard();
  const signals = sig.data?.signals ?? [];
  const shadowLate = signals.filter((s) => ["shadow", "late"].includes(s.actionability.status));
  const errCount = (health.data?.errors ?? []).reduce((a, e) => a + e.count, 0);
  // Canonical, deduped, book-separated numbers (replaces the old raw sum-over-200
  // signals that produced e.g. -26R by mixing shadow + dupes + 5 days as "today").
  const d = dash.data;
  const op = d?.operator;
  // MAIN number = Paper Execution R (Model F: early MFE-armed protection).
  // Touch R (old highest-TP-touched final_r) is now secondary / signal-quality only.
  const todayR = op?.today.paper_execution_r ?? 0;
  const todayTouchR = op?.today.legacy_touch_r ?? 0;
  const openRisk = (op?.open_now ?? 0) * 1; // 1R per open paper unit
  const pendingN = op?.waiting_now ?? 0;
  const paperUnavail = op?.today.paper_unavailable_n ?? 0;

  const alerts: { icon: string; text: string; tone: string }[] = [];
  if (st.data && !st.data.engine_online) alerts.push({ icon: "ti-plug-off", text: "Monitor offline / stale tick", tone: "b-danger" });
  if (errCount > 0) alerts.push({ icon: "ti-alert-triangle", text: `${errCount} system errors in 24h`, tone: "b-warn" });
  shadowLate.filter((s) => s.actionability.status === "late").slice(0, 2).forEach((s) =>
    alerts.push({ icon: "ti-clock-exclamation", text: `${s.symbol} late entry — do not chase`, tone: "b-warn" }));
  signals.filter((s) => s.concentration_status === "shadow_sector_cap").slice(0, 1).forEach((s) =>
    alerts.push({ icon: "ti-stack-2", text: `${s.symbol} sector cap — shadowed`, tone: "b-shadow" }));
  if ((d?.delivery_gaps ?? 0) > 0)
    alerts.push({ icon: "ti-send-off", text: `${d!.delivery_gaps} entry alert(s) not delivered (delivery gap)`, tone: "b-warn" });

  return (
    <Screen>
      {/* hero */}
      <div className="glass p-4 animate-rise" style={{ background: "linear-gradient(160deg, rgba(53,224,240,0.07), rgba(124,108,255,0.05) 60%, rgba(255,255,255,0.02))" }}>
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[20px] font-semibold tracking-tight">AI Trading Desk</div>
            <div className="flex items-center gap-1.5 mt-1 text-[12px]">
              <StatusDot ok={!!st.data?.engine_online} />
              <span className="text-muted">{st.data?.engine_online ? "Online" : "Offline"} · {st.data?.demo_mode ? "demo" : "live data"} · tick {rel(st.data?.last_monitor_tick)}</span>
            </div>
          </div>
          <button className="btn btn-danger !px-3" onClick={() => { haptic("heavy"); onPause(); }} aria-label="emergency pause"><i className="ti ti-player-pause text-base" /></button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {(st.data?.badges ?? ["Engine", "Live LOCKED"]).map((b, i) =>
            <Badge key={i} tone={b.includes("LOCK") ? "b-danger" : b.includes("shadow") ? "b-shadow" : "b-accent"}>{b}</Badge>)}
        </div>
      </div>

      {/* paper portfolio — $5000 deposit, 0.5% risk, dynamic leverage, net of fees */}
      {port.data?.available && (
        <>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <MetricCard label="Paper Equity" value={`$${(port.data.equity_usdt ?? 0).toFixed(0)}`} tone={(port.data.return_pct ?? 0) >= 0 ? "text-profit" : "text-danger"} sub={`start $${port.data.initial_equity_usdt.toFixed(0)} · ${(port.data.return_pct ?? 0) >= 0 ? "+" : ""}${port.data.return_pct ?? 0}% · net of fees`} />
            <MetricCard label="Today Net $" value={`${(port.data.today_net_pnl_usdt ?? 0) >= 0 ? "+" : ""}$${(port.data.today_net_pnl_usdt ?? 0).toFixed(1)}`} tone={(port.data.today_net_pnl_usdt ?? 0) >= 0 ? "text-profit" : "text-danger"} sub={`${(port.data.today_net_r ?? 0) >= 0 ? "+" : ""}${port.data.today_net_r ?? 0}R · 7d ${(port.data.d7_net_pnl_usdt ?? 0) >= 0 ? "+" : ""}$${(port.data.d7_net_pnl_usdt ?? 0).toFixed(0)}`} />
            <MetricCard label="Max Drawdown" value={`${port.data.max_drawdown_pct ?? 0}%`} tone="text-text" sub={`risk ${(port.data.risk_per_trade_pct * 100).toFixed(1)}%/trade · 0.5% of equity`} />
            {/* PART 1 — execution cost split: exchange fees, slippage and funding are DISTINCT (never call slippage a "fee") */}
            <MetricCard label="Execution Cost" value={`$${(port.data.total_execution_cost_usdt ?? port.data.fees_paid_usdt ?? 0).toFixed(0)}`} tone="text-faint" sub={`fees $${(port.data.exchange_fees_usdt ?? 0).toFixed(0)} · slippage $${(port.data.slippage_usdt ?? 0).toFixed(0)} · funding ${port.data.funding_known ? `$${(port.data.funding_usdt ?? 0).toFixed(0)}` : "n/a"} · ${port.data.trades ?? 0}t W${port.data.wins ?? 0}/L${port.data.losses ?? 0}`} />
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <MetricCard label="Leverage" value={`${port.data.avg_leverage ?? 0}x avg`} tone="text-text" sub={`max ${port.data.max_leverage ?? 0}x · ${port.data.risk_capped_trades ?? 0} risk-capped · leverage ≠ risk`} />
            <MetricCard label="Open / Margin" value={`${port.data.open_positions ?? 0} pos`} tone="text-faint" sub={`open risk $${(port.data.open_risk_usdt ?? 0).toFixed(0)} · margin $${(port.data.margin_used_usdt ?? 0).toFixed(0)} (historical=0)`} />
          </div>
          <div className="glass-soft p-2.5 mt-3 text-[11px] text-faint leading-relaxed">{port.data.note} · profile {port.data.fee_profile}{port.data.fee_estimated_any ? " · ⚠ some fees estimated" : " · fees exact (exit-notional)"}</div>
          {/* PART 3 — per-asset P&L: crypto and stocks costed separately (distinct fee/funding models) */}
          {byAsset.data?.available && (
            <div className="glass-soft p-2.5 mt-3 text-[11px] leading-relaxed" data-testid="portfolio-by-asset">
              <div className="text-faint mb-1.5">Per-asset P&L — crypto and stocks counted separately (distinct cost models)</div>
              <div className="grid grid-cols-2 gap-3">
                {(["crypto", "stocks"] as const).map((k) => {
                  const a = byAsset.data![k];
                  if (!a || a.trades === 0)
                    return <MetricCard key={k} label={k === "crypto" ? "Crypto" : "Stocks"} value="—" tone="text-faint" sub="no trades" />;
                  return (
                    <MetricCard key={k} label={k === "crypto" ? "Crypto" : "Stocks"}
                      value={`${a.net_pnl_usdt >= 0 ? "+" : ""}$${a.net_pnl_usdt.toFixed(0)}`}
                      tone={a.net_pnl_usdt >= 0 ? "text-profit" : "text-danger"}
                      sub={`${a.trades}t · W${a.win_rate}% · fees $${a.exchange_fees_usdt.toFixed(0)} · slip $${a.slippage_usdt.toFixed(0)}${a.funding_usdt ? ` · fund $${a.funding_usdt.toFixed(0)}` : ""}`} />
                  );
                })}
              </div>
              {byAsset.data.stocks && !byAsset.data.stocks.cost_model_appropriate && byAsset.data.stocks.cost_model_note && (
                <div className="text-warn mt-1.5">⚠ {byAsset.data.stocks.cost_model_note}</div>
              )}
              {(byAsset.data.unknown_asset_trades ?? 0) > 0 && (
                <div className="text-faint mt-1 opacity-70">{byAsset.data.unknown_asset_trades} trade(s) with unknown asset class</div>
              )}
            </div>
          )}
          {/* PART 6 — mechanical taker (A) vs structural + maker-first + fee-aware + 2x (B) */}
          {cmp.data?.available && (
            <div className="glass-soft p-2.5 mt-3 text-[11px] leading-relaxed">
              <div className="text-faint mb-1">Paper execution model — production TP unchanged · paper TP = structural/maker-first · leverage {cmp.data.leverage_policy}</div>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="A · mechanical+taker" value={`${(cmp.data.mechanical_taker?.return_pct ?? 0) >= 0 ? "+" : ""}${cmp.data.mechanical_taker?.return_pct ?? 0}%`} tone="text-faint" sub={`$${(cmp.data.mechanical_taker?.equity_usdt ?? 0).toFixed(0)} · cost $${(cmp.data.mechanical_taker?.fees_paid_usdt ?? 0).toFixed(0)}`} />
                <MetricCard label="B · structural+maker-first" value={`${(cmp.data.structural_maker_first?.return_pct ?? 0) >= 0 ? "+" : ""}${cmp.data.structural_maker_first?.return_pct ?? 0}%`} tone={(cmp.data.delta_return_pct ?? 0) >= 0 ? "text-profit" : "text-danger"} sub={`$${(cmp.data.structural_maker_first?.equity_usdt ?? 0).toFixed(0)} · cost $${(cmp.data.structural_maker_first?.fees_paid_usdt ?? 0).toFixed(0)}`} />
              </div>
              <div className="text-faint mt-2">Δ {(cmp.data.delta_return_pct ?? 0) >= 0 ? "+" : ""}{cmp.data.delta_return_pct ?? 0}pp · cost saved {fmtUsd(cmp.data.fees_saved_usdt ?? 0)} · maker entries {cmp.data.maker_entries ?? 0}/{(cmp.data.maker_entries ?? 0) + (cmp.data.taker_entries ?? 0)} · maker exits {cmp.data.maker_exits ?? 0} · structural TP {cmp.data.structural_tp_trades ?? 0} / ATR-fallback {cmp.data.atr_fallback_tp_trades ?? 0}</div>
              {/* PART 11 — A/B comparability: same trades over the same window, else the delta is stale/apples-to-oranges */}
              {cmp.data.comparison_integrity && (
                <div className={`mt-1 ${cmp.data.comparison_integrity.comparable ? "text-faint" : "text-warn"}`} data-testid="compare-integrity">
                  {cmp.data.comparison_integrity.comparable
                    ? `✓ like-for-like · ${cmp.data.comparison_integrity.common_trades} common trades (A ${cmp.data.comparison_integrity.A.trades} / B ${cmp.data.comparison_integrity.B.trades})`
                    : `⚠ ${cmp.data.comparison_integrity.warnings.join(" · ")}`}
                </div>
              )}
              <div className="text-faint mt-1 opacity-70">{cmp.data.note}</div>
            </div>
          )}
        </>
      )}
      {port.data && !port.data.available && (
        <div className="glass-soft p-2.5 mt-3 text-[11px] text-warn">Paper portfolio: {port.data.reason} — run paper_portfolio_backfill.</div>
      )}

      {/* metrics — Paper Execution R (Model F) is the headline; Touch R is secondary/optimistic */}
      <div className="grid grid-cols-2 gap-3 mt-3">
        <MetricCard label="Today R · Paper Exec" value={fmtR(todayR)} tone={todayR >= 0 ? "text-profit" : "text-danger"} sub="Model F · early MFE protection · UTC day" />
        <MetricCard label="Legacy Touch R" value={fmtR(todayTouchR)} tone="text-faint" sub="highest TP touched · optimistic · NOT PnL (diagnostic)" />
        <MetricCard label="48h R · Paper Exec" value={fmtR(op?.h48.paper_execution_r ?? 0)} tone={(op?.h48.paper_execution_r ?? 0) >= 0 ? "text-profit" : "text-danger"} sub={`W${op?.h48.win ?? 0}/L${op?.h48.loss ?? 0} · BE${op?.h48.be_scratch_n ?? 0} · ${op?.h48.paper_resolved_n ?? 0} resolved`} />
        <MetricCard label="Shadow 48h R · Paper" value={fmtR(d?.shadow.h48.paper_execution_r ?? 0)} tone="text-shadowc" sub={`not actionable · ${d?.shadow.h48.expired_unresolved ?? 0} expired`} />
      </div>
      {/* protection stats row */}
      <div className="grid grid-cols-2 gap-3 mt-3">
        <MetricCard label="Open risk" value={`${openRisk.toFixed(1)}R`} tone="text-text" sub={`${op?.open_now ?? 0} open · ${pendingN} waiting`} />
        <MetricCard label="48h Protected" value={`${op?.h48.protected_n ?? 0}`} tone="text-accent" sub={`${op?.h48.original_stops_avoided_n ?? 0} stops→BE/lock · ${op?.h48.giveback_n ?? 0} giveback`} />
      </div>
      {/* honest accounting note: paper exec vs touch vs no-risk-mgmt */}
      <div className="glass-soft p-3 mt-3 text-[11px] text-faint leading-relaxed">
        <span className="text-muted">{d?.headline.label ?? "Today R = Paper Execution R (Model F); Touch R = old highest-TP-touched, optimistic."}</span>
        {d && <> · Risk model: {d.headline.risk_model} · Paper 48h {fmtR(d.paper.h48.paper_execution_r)} (legacy touch {fmtR(d.paper.h48.legacy_touch_r)}) · {d.delivery_gaps} delivery gap(s)</>}
        {paperUnavail > 0 && <span className="text-warn"> · ⚠ {paperUnavail} trade(s) missing MFE — paper R unavailable (not silently zeroed)</span>}
      </div>

      {/* Paper Feature Flags — what is active in paper (accounting/display/advisory only) */}
      {pf.data && (
        <div className="glass p-3 mt-3">
          <div className="flex items-center justify-between mb-2">
            <div className="label">Paper Features <span className="text-faint">· {pf.data.risk_model}</span></div>
            <div className="flex gap-1.5">
              <Badge tone="b-accent">{pf.data.counts.active} active</Badge>
              <Badge tone="b-shadow">{pf.data.counts.shadow} shadow</Badge>
              <Badge tone="b-muted">{pf.data.counts.archived} archived</Badge>
              <Badge tone="b-danger">{pf.data.counts.dangerous} locked</Badge>
            </div>
          </div>
          {pf.data.active.map((f) => (
            <div key={f.key} className="flex items-start justify-between py-1 text-[12px] hairline last:border-0">
              <div className="min-w-0">
                <span className="text-text">{f.label}</span>
                {f.mode && <span className="text-faint"> · {f.mode}</span>}
                <div className="text-[11px] text-faint truncate">{f.evidence}</div>
              </div>
              <span className="text-[10px] text-faint tnum shrink-0 ml-2">{f.decision_date}</span>
            </div>
          ))}
          <div className="text-[11px] text-faint mt-2 pt-2 hairline">
            Dangerous/locked (do NOT enable): {pf.data.dangerous_locked.map((f) => f.label).join(" · ")}. Live {pf.data.live_locked ? "LOCKED" : "?"} · auto-live {pf.data.auto_live_locked ? "LOCKED" : "?"}. {pf.data.note}
          </div>
        </div>
      )}

      {/* action required */}
      {alerts.length > 0 && (
        <div className="glass p-4 mt-3" style={{ borderColor: "rgba(246,183,60,0.3)" }}>
          <div className="label mb-2 text-warn">Action required</div>
          {alerts.slice(0, 4).map((al, i) => (
            <div key={i} className="flex items-center gap-2 py-1.5 hairline last:border-0">
              <i className={`ti ${al.icon} text-warn`} />
              <span className="text-[13px]">{al.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* event feed */}
      <div className="glass p-4 mt-3">
        <div className="label mb-2">Latest desk events</div>
        {sig.isLoading && <SkeletonList n={3} h={28} />}
        {signals.slice(0, 7).map((s) => {
          const closed = isClosedTrade(s);
          const pr = s.paper_execution_r;   // authoritative paper R (USD net = the real PnL)
          const icon = closed ? ((pr ?? 0) >= 0 ? "ti-target-arrow" : "ti-shield-x")
            : s.actionability.status === "shadow" ? "ti-eye-off"
            : s.actionability.status === "late" ? "ti-clock-exclamation"
            : s.entry_triggered_at ? "ti-arrow-up-right" : "ti-radar";
          return (
            <div key={s.signal_id} className="flex items-center gap-2.5 py-1.5 hairline last:border-0">
              <i className={`ti ${icon} text-[15px] text-muted`} />
              <span className="text-[13px] flex-1 truncate">{s.symbol} <span className="text-faint">{s.mode}</span></span>
              {closed ? <span className={`text-[12px] tnum ${(pr ?? 0) >= 0 ? "text-profit" : "text-danger"}`}>{pr != null ? fmtR(pr) : "—"}</span>
                : <Badge tone={badgeTone(s.actionability.status)}>{s.actionability.status}</Badge>}
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-2 mt-3">
        <button className="btn" onClick={() => go("Signals")}><i className="ti ti-rss mr-1.5" />Signals</button>
        <button className="btn" onClick={() => go("Trades")}><i className="ti ti-arrows-left-right mr-1.5" />Trades</button>
      </div>
    </Screen>
  );
}

// ============================================================= SIGNALS =====
export function Signals({ onChart, onManual }: { onChart: (s: Signal) => void; onManual: (s: Signal) => void }) {
  const [asset, setAsset] = useState("All");
  const [stat, setStat] = useState("All");
  const q = useSignals();
  let list = q.data?.signals ?? [];
  if (asset !== "All") list = list.filter((s) => s.asset_class === asset.toLowerCase());
  if (stat !== "All") list = list.filter((s) => s.actionability.status === stat.toLowerCase());

  return (
    <Screen>
      <H title="Signals" sub="what you can take — and why not" />
      <Seg options={["All", "Crypto", "Stocks"]} value={asset} onChange={setAsset} />
      <div className="mt-2"><Seg options={["All", "Actionable", "Shadow", "Late", "Closed"]} value={stat} onChange={setStat} /></div>
      <div className="mt-3">
        {q.isLoading && <SkeletonList n={4} h={150} />}
        {q.isError && <ErrorBanner msg="Could not load signals." onRetry={() => q.refetch()} />}
        {!q.isLoading && list.length === 0 && <EmptyState icon="◎" title="No signals match" sub="Adjust the filters above." />}
        {list.map((s) => <SignalCard key={s.signal_id} s={s} onChart={onChart} onManual={onManual} />)}
      </div>
    </Screen>
  );
}

// ============================================================== TRADES =====
export function Trades({ onChart }: { onChart: (s: Signal) => void }) {
  const [b, setB] = useState("open");
  const live = useTrades(b);
  const list = live.data?.trades ?? [];
  const empty: Record<string, [string, string]> = {
    open: ["No open actionable trades", "Check Pending (waiting for entry) and Closed/Shadow for the rest."],
    pending: ["No pending entries", "No actionable setups waiting for entry right now."],
  };
  return (
    <Screen>
      <H title="Trades" />
      <Seg options={["open", "pending", "closed", "shadow"]} value={b} onChange={setB} cap />
      {b === "closed" && <ClosedBook initialBook="operator" onChart={onChart} />}
      {b === "shadow" && <ClosedBook initialBook="shadow" onChart={onChart} />}
      {(b === "open" || b === "pending") && (
        <div className="mt-3">
          {live.isLoading && <SkeletonList n={3} h={120} />}
          {!live.isLoading && list.length === 0 && <EmptyState icon="⊘" title={empty[b][0]} sub={empty[b][1]} />}
          {list.map((s) => <TradeCard key={s.signal_id} s={s} onClick={() => onChart(s)} />)}
        </div>
      )}
    </Screen>
  );
}

// ---- Closed Trades canonical book view (deduped, book-separated, honest R) ---
const OUTCOME_META: Record<string, { label: string; tone: string }> = {
  win: { label: "WIN", tone: "b-profit" },
  loss: { label: "LOSS", tone: "b-danger" },
  flat: { label: "FLAT", tone: "b-muted" },
  expired_unresolved: { label: "EXPIRED (unresolved)", tone: "b-warn" },
  no_entry: { label: "NO-ENTRY", tone: "b-muted" },
  needs_review: { label: "NEEDS REVIEW", tone: "b-warn" },
  open: { label: "OPEN", tone: "b-accent" },
  waiting: { label: "WAITING", tone: "b-muted" },
  shadow_open: { label: "SHADOW", tone: "b-shadow" },
};
const DELIVERY_META: Record<string, { label: string; tone: string }> = {
  sent: { label: "delivered", tone: "b-profit" },
  not_sent: { label: "not sent", tone: "b-muted" },
  late_shadow: { label: "late→shadow", tone: "b-warn" },
  shadow_only: { label: "shadow", tone: "b-shadow" },
  shadow_sector_cap: { label: "sector-cap", tone: "b-shadow" },
};
function deliveryMeta(s: string | undefined) {
  if (!s) return { label: "—", tone: "b-muted" };
  if (s.startsWith("error") || s.startsWith("failed")) return { label: "delivery error", tone: "b-danger" };
  return DELIVERY_META[s] ?? { label: s, tone: "b-muted" };
}
function catalystMeta(s: Signal) {
  const v = s.catalyst_supported;
  if (v === "supported") return { label: "catalyst", tone: "b-accent" };
  if (v === "unsupported") return { label: "technical-only", tone: "b-muted" };
  return { label: "catalyst unknown", tone: "b-warn" }; // linkage missing/stale → honest, not false "no catalyst"
}
function regimeLabel(s: Signal) {
  const r = (s.market_regime || "").trim();
  return r ? r : "unknown";
}

const CLOSED_RANGE_HOURS: Record<string, number> = { Today: 24, "48h": 48, "7d": 168, "30d": 720 };

function isoDay(ts?: string | null) {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

function PnlCurve({ data }: { data?: TradePnlAnalytics }) {
  if (!data || data.series.length === 0) {
    return (
      <div className="glass p-3.5 mt-3">
        <div className="label">PnL curve</div>
        <div className="text-[12px] text-faint mt-2">No closed trades in this range yet.</div>
      </div>
    );
  }
  const useUsd = data.pnl_usd_available;
  const vals = [0, ...data.series.map((p) => useUsd ? p.cumulative_usd : p.cumulative_r)];
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const w = 320, h = 104, pad = 10;
  const step = (w - pad * 2) / Math.max(vals.length - 1, 1);
  const zeroY = pad + (h - pad * 2) - ((0 - min) / span) * (h - pad * 2);
  const pts = vals.map((v, i) => {
    const x = pad + i * step;
    const y = pad + (h - pad * 2) - ((v - min) / span) * (h - pad * 2);
    return `${x},${y}`;
  }).join(" ");
  const end = vals[vals.length - 1] ?? 0;
  const tone = end >= 0 ? "#27d18b" : "#ff5d6c";
  return (
    <div className="glass p-3.5 mt-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="label">PnL curve</div>
          <div className="text-[11px] text-faint mt-1">
            {useUsd ? "USD net after costs" : "Paper Execution R fallback"} - {data.trades} closed - DD {useUsd ? fmtUsd(data.max_drawdown_usd) : fmtR(data.max_drawdown_r)}
          </div>
        </div>
        <div className={`text-right text-[18px] font-semibold tnum ${end >= 0 ? "text-profit" : "text-danger"}`}>
          {useUsd ? fmtUsd(data.total_pnl_usd) : fmtR(data.total_r)}
        </div>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-[118px] mt-2 overflow-visible">
        <line x1={pad} x2={w - pad} y1={zeroY} y2={zeroY} stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
        <polyline points={pts} fill="none" stroke={tone} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      {data.missing_usd_trades > 0 && (
        <div className="text-[10px] text-warn mt-1">{data.missing_usd_trades} trade(s) have no USD ledger row; R remains visible as diagnostic.</div>
      )}
    </div>
  );
}

function calendarSpan(days: TradeCalendarDay[], hours: number): (TradeCalendarDay & { empty?: boolean })[] {
  const byDay = new Map(days.map((d) => [d.date, d]));
  const end = new Date();
  const start = new Date(end.getTime() - hours * 3600_000);
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()));
  const last = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate()));
  const out: (TradeCalendarDay & { empty?: boolean })[] = [];
  while (cursor <= last) {
    const key = cursor.toISOString().slice(0, 10);
    out.push(byDay.get(key) ?? { date: key, trades: 0, net_pnl_usd: 0, net_r: 0, wins: 0, losses: 0, flat: 0, missing_usd: 0, trade_ids: [], empty: true });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return out;
}

function TradingCalendar({ data, hours, selectedDay, onSelect }:
  { data?: TradePnlAnalytics; hours: number; selectedDay: string | null; onSelect: (d: string | null) => void }) {
  const days = calendarSpan(data?.days ?? [], hours);
  return (
    <div className="glass p-3.5 mt-3">
      <div className="flex items-center justify-between">
        <div className="label">Trading calendar</div>
        {selectedDay && <button className="text-[11px] text-accent" onClick={() => onSelect(null)}>show all</button>}
      </div>
      <div className="grid grid-cols-7 gap-1.5 mt-2">
        {days.map((d) => {
          const has = d.trades > 0;
          const pos = d.net_pnl_usd !== 0 ? d.net_pnl_usd > 0 : d.net_r >= 0;
          const active = selectedDay === d.date;
          return (
            <button
              key={d.date}
              disabled={!has}
              onClick={() => { haptic("light"); onSelect(active ? null : d.date); }}
              className={`rounded-md border px-1.5 py-1.5 text-left min-h-[54px] ${active ? "border-accent/80 bg-accent/10" : has ? "border-white/10 bg-white/[0.035]" : "border-white/[0.04] bg-white/[0.015] opacity-45"}`}
            >
              <div className="text-[10px] text-faint">{d.date.slice(5)}</div>
              <div className={`text-[12px] font-semibold tnum ${has ? (pos ? "text-profit" : "text-danger") : "text-faint"}`}>
                {has ? (data?.pnl_usd_available ? fmtUsd(d.net_pnl_usd) : fmtR(d.net_r)) : "-"}
              </div>
              {has && <div className="text-[9px] text-faint">{d.trades} trades</div>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ClosedBook({ initialBook, onChart }: { initialBook: string; onChart: (s: Signal) => void }) {
  const [book, setBook] = useState(initialBook);
  const [rangeLabel, setRangeLabel] = useState("48h");
  const [outcome, setOutcome] = useState("All");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const hours = CLOSED_RANGE_HOURS[rangeLabel] ?? 48;
  useEffect(() => setSelectedDay(null), [book, rangeLabel]);
  const dash = useDashboard();
  const q = useClosed(book, hours);
  const analytics = useClosedAnalytics(book, hours);
  const nw = useNearWinners(book, hours);
  let rows = q.data?.trades ?? [];
  if (outcome !== "All") rows = rows.filter((s) => (s.outcome_class ?? "") === outcome.toLowerCase().replace(/ /g, "_"));
  if (selectedDay) rows = rows.filter((s) => isoDay(s.close_time ?? s.created_at) === selectedDay);
  const blk = dash.data ? (dash.data as any)[book] : null;
  const win = rangeLabel === "Today" ? blk?.today : rangeLabel === "48h" ? blk?.h48 : blk?.d7;

  return (
    <div className="mt-3">
      {/* book selector */}
      <Seg options={["operator", "paper", "shadow"]} value={book} onChange={setBook} cap />
      <div className="mt-2"><Seg options={["Today", "48h", "7d", "30d"]} value={rangeLabel} onChange={setRangeLabel} /></div>
      <PnlCurve data={analytics.data} />
      <TradingCalendar data={analytics.data} hours={hours} selectedDay={selectedDay} onSelect={setSelectedDay} />

      {/* honest book R header */}
      {win && (
        <div className="glass p-3.5 mt-3">
          <div className="flex items-center justify-between">
            <div className="label capitalize">{book} book · {rangeLabel}</div>
            <div className="text-right">
              <span className={`text-[20px] font-semibold tnum ${(win.paper_execution_r ?? 0) >= 0 ? "text-profit" : "text-danger"}`}>{fmtR(win.paper_execution_r)}</span>
              <div className="text-[9px] text-faint uppercase tracking-wide">Paper Exec R</div>
            </div>
          </div>
          <div className="text-[11px] text-faint mt-1">
            paper-exec R from terminal closes only · W{win.win}/L{win.loss}/Flat{win.flat} · expired-unresolved {win.expired_unresolved} · needs-review {win.needs_review} · {blk?.duplicates_collapsed ?? 0} dupes collapsed
          </div>
          <div className="text-[10px] text-faint mt-0.5">Legacy Touch R {fmtR(win.legacy_touch_r)} · optimistic · not PnL (diagnostic)</div>
          {book === "operator" && <div className="text-[11px] text-faint mt-0.5">Shadow &amp; undelivered excluded. Expired-after-entry is NOT counted as PnL.</div>}
        </div>
      )}

      {/* outcome filter */}
      <div className="mt-2"><Seg options={["All", "Win", "Loss", "Flat", "Expired unresolved", "No entry", "Needs review"]} value={outcome} onChange={setOutcome} /></div>

      {/* rows */}
      <div className="mt-3">
        {selectedDay && <div className="label mb-2">Trades on {selectedDay}</div>}
        {q.isLoading && <SkeletonList n={3} h={96} />}
        {!q.isLoading && rows.length === 0 && <EmptyState icon="⊘" title="No closed trades" sub={`No ${book} trades closed in the last ${rangeLabel}.`} />}
        {rows.map((s) => <ClosedRow key={s.signal_id} s={s} onOpen={() => onChart(s)} />)}
      </div>

      {/* near-winner expired diagnostics */}
      {(nw.data?.count ?? 0) > 0 && (
        <div className="glass p-3.5 mt-3" style={{ borderColor: "rgba(246,183,60,0.3)" }}>
          <div className="label mb-1 text-warn">Expired after entry — near winners</div>
          <div className="text-[11px] text-faint mb-2">{nw.data!.note} (MFE ≥ 0.8R but expired at 0R)</div>
          {nw.data!.items.slice(0, 6).map((s) => (
            <div key={s.signal_id} className="flex justify-between items-center py-1.5 hairline last:border-0 text-[12px]">
              <span className="truncate">{s.symbol} <span className="text-faint">{s.direction} · {s.mode}</span></span>
              <span className="flex items-center gap-2"><span className="text-profit tnum">MFE {fmt(s.mfe_r)}R</span><span className="text-faint tnum">MAE {fmt(s.mae_r)}R</span></span>
            </div>
          ))}
        </div>
      )}

    </div>
  );
}

function ClosedRow({ s, onOpen }: { s: Signal; onOpen: () => void }) {
  const oc = OUTCOME_META[s.outcome_class ?? "open"] ?? OUTCOME_META.open;
  const dm = deliveryMeta(s.delivery_state);
  const cm = catalystMeta(s);
  // MAIN = paper execution R (Model F); legacy touch R shown faint as a labelled diagnostic.
  const r = s.paper_execution_r;
  const tr = s.legacy_touch_r;
  return (
    <button onClick={() => { haptic("light"); onOpen(); }}
      className="glass w-full text-left p-3.5 mb-2.5 active:scale-[0.99] transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent/40">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-[14px]">{s.symbol} <span className={s.direction === "short" ? "text-danger" : "text-profit"}>{(s.direction || "").toUpperCase()}</span></div>
        <div className="flex items-center gap-2">
          {r != null && <span className={`text-[15px] font-semibold tnum ${r >= 0 ? "text-profit" : "text-danger"}`}>{fmtR(r)}</span>}
          {tr != null && tr !== r && <span className="text-[11px] text-faint tnum">legacy touch {fmtR(tr)}</span>}
          <Badge tone={oc.tone}>{oc.label}</Badge>
        </div>
      </div>
      <div className="text-[11px] text-faint mt-1">{s.asset_class} · {s.mode} · Tier {s.tier} · {s.close_explanation}</div>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {s.giveback && <Badge tone="b-warn">giveback→protected</Badge>}
        {s.lock_armed ? <Badge tone="b-accent">lock +0.5R</Badge> : s.protection_armed && <Badge tone="b-accent">BE armed</Badge>}
        {s.cohort_warning && <Badge tone="b-warn">weak cohort</Badge>}
        <Badge tone="b-muted">MFE {fmt(s.mfe_r)}R</Badge>
        <Badge tone="b-muted">MAE {fmt(s.mae_r)}R</Badge>
        <Badge tone={dm.tone}>{dm.label}</Badge>
        <Badge tone={cm.tone}>{cm.label}</Badge>
        <Badge tone="b-muted">regime: {regimeLabel(s)}</Badge>
        {(s.duplicates_collapsed_count ?? 0) > 0 && <Badge tone="b-muted">+{s.duplicates_collapsed_count} dup</Badge>}
      </div>
    </button>
  );
}

// Price-scaled execution overlay (SVG) — every level/fill at its TRUE price height, so
// a +3R TP3 fill sits at TP3, never near TP1/TP2 (ETH fix). Full candle overlay is TODO.
function ExecChart({ lc }: { lc: TradeLifecycle }) {
  const pl = lc.price_ladder;
  if (!pl) return null;
  const long = (lc.direction || "long").toLowerCase() !== "short";
  const lines: { price: number; label: string; color: string }[] = [];
  if (pl.entry != null) lines.push({ price: pl.entry, label: "Entry", color: "var(--text)" });
  if (pl.initial_stop != null) lines.push({ price: pl.initial_stop, label: "Stop", color: "var(--danger)" });
  if (pl.current_stop != null && pl.current_stop !== pl.initial_stop)
    lines.push({ price: pl.current_stop, label: "Stop→", color: "var(--warn)" });
  (pl.tps || []).forEach((t) => { if (t.price != null) lines.push({ price: t.price, label: t.label, color: "var(--profit)" }); });
  const fills = (lc.events || []).filter((e) => e.price != null && /filled|exit/.test(e.event))
    .map((e) => ({ price: e.price as number, label: e.event.replace("_filled", "").replace("_exit", " exit").toUpperCase(), r: e.realized_r, usd: e.realized_pnl_usdt }));
  const prices = [...lines.map((l) => l.price), ...fills.map((f) => f.price)].filter((p) => p != null);
  if (!prices.length) return null;
  const min = Math.min(...prices), max = Math.max(...prices);
  const pad = (max - min) * 0.12 || max * 0.01 || 1;
  const lo = min - pad, hi = max + pad;
  const W = 320, H = 200, L = 64, R = 92;
  const y = (p: number) => H - 8 - ((p - lo) / (hi - lo)) * (H - 16);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
      <rect x={L} y={6} width={W - L - R} height={H - 12} fill="rgba(255,255,255,0.02)" rx={4} />
      {lines.map((l, i) => (
        <g key={`l${i}`}>
          <line x1={L} x2={W - R} y1={y(l.price)} y2={y(l.price)} stroke={l.color} strokeWidth={1}
                strokeDasharray={l.label.startsWith("Stop") ? "3 3" : undefined} opacity={0.8} />
          <text x={4} y={y(l.price) + 3} fill={l.color} fontSize={9}>{l.label}</text>
          <text x={W - R + 4} y={y(l.price) + 3} fill="var(--faint)" fontSize={9} className="tnum">{l.price}</text>
        </g>
      ))}
      {fills.map((f, i) => (
        <g key={`f${i}`}>
          <circle cx={L + 18 + i * 26} cy={y(f.price)} r={4} fill={long ? "var(--profit)" : "var(--danger)"} stroke="#000" strokeWidth={0.5} />
          <text x={L + 18 + i * 26} y={y(f.price) - 7} fill="var(--text)" fontSize={8} textAnchor="middle">{f.label}</text>
        </g>
      ))}
    </svg>
  );
}

function lifecycleStatusMeta(st?: string): { label: string; tone: string } {
  const m: Record<string, { label: string; tone: string }> = {
    waiting_entry: { label: "Waiting entry", tone: "b-muted" },
    missed_no_entry: { label: "Missed — no entry", tone: "b-warn" },
    entry_filled_active: { label: "Entry filled · waiting TP1", tone: "b-accent" },
    tp1_filled_active: { label: "TP1 filled · waiting TP2/TP3", tone: "b-profit" },
    tp2_filled_active: { label: "TP2 filled · runner to TP3", tone: "b-profit" },
    closed_win: { label: "Closed · win", tone: "b-profit" },
    stopped: { label: "Stopped", tone: "b-danger" },
    expired: { label: "Expired flat", tone: "b-warn" },
    closed_partial_stop: { label: "Partial + stopped", tone: "b-warn" },
    closed_partial_expired: { label: "Partial + expired", tone: "b-warn" },
  };
  return m[st || ""] || { label: st || "—", tone: "b-muted" };
}

// Exchange-like lifecycle panel: position summary, price ladder, execution timeline, chart.
function LifecyclePanel({ lc, hideChart }: { lc: TradeLifecycle; hideChart?: boolean }) {
  if (!lc?.available) return null;
  const p = lc.position; const pl = lc.price_ladder;
  const sm = lifecycleStatusMeta(lc.status);
  return (
    <div className="glass-soft p-3 mb-3 text-[12px]">
      <div className="flex items-center justify-between mb-1.5">
        <div className="label">Position lifecycle</div>
        <Badge tone={sm.tone}>{sm.label}</Badge>
      </div>
      {/* Position summary */}
      {p && (
        <div className="grid grid-cols-3 gap-2 mb-2">
          <KV k="Risk $" v={`$${(p.risk_usdt ?? 0).toFixed(1)} · ${((p.risk_pct ?? 0) * 100).toFixed(1)}%`} />
          <KV k="Notional" v={`$${(p.notional_usdt ?? 0).toFixed(0)}`} />
          <KV k="Qty" v={`${(p.qty ?? 0).toFixed(4)}`} />
          <KV k="Leverage" v={`${p.leverage ?? "—"}x`} />
          <KV k="Margin" v={`$${(p.margin_usdt ?? 0).toFixed(0)}`} />
          <KV k="Liq≈" v={p.liquidation_price != null ? `${p.liquidation_price}` : "—"} />
        </div>
      )}
      {p && <div className="text-[11px] text-faint mb-2">{p.leverage_reason} · liq {(((p.liq_distance_pct ?? 0) * 100).toFixed(0))}% vs stop {(((p.stop_distance_pct ?? 0) * 100).toFixed(1))}% · leverage ≠ risk{p.risk_capped ? " · risk-capped" : ""}{p.liquidation_buffer_ok === false ? " · ⚠ liq buffer" : ""}</div>}
      {/* Price ladder with $ per TP */}
      {pl && (
        <>
          <div className="label mb-1">Price ladder · $ per fill</div>
          <div className="grid grid-cols-1 gap-1 mb-2">
            <Row k="Entry" v={`${pl.entry}`} sub="0.0R" />
            <Row k="Initial stop" v={`${pl.initial_stop}`} sub={`max loss ${fmtUsd(pl.max_loss_at_stop_usdt ?? 0)}`} tone="text-danger" />
            {pl.current_stop != null && pl.current_stop !== pl.initial_stop &&
              <Row k="Current stop" v={`${pl.current_stop}`} sub={`${pl.current_stop_r != null ? pl.current_stop_r + "R locked" : ""}`} tone="text-warn" />}
            {(pl.tps || []).map((t, i) => (
              <Row key={i} k={`${t.label} (${Math.round((t.pct_closed ?? 0) * 100)}%)`} v={`${t.price ?? "—"}`}
                   sub={`${t.r != null ? t.r + "R" : "—"} · ${t.pnl_if_filled_usdt != null ? fmtUsd(t.pnl_if_filled_usdt) : "—"}`} tone="text-profit" />
            ))}
          </div>
        </>
      )}
      {/* Realized */}
      <div className="grid grid-cols-3 gap-2 mb-2">
        <KV k="Blended R" v={lc.blended_r != null ? fmtR(lc.blended_r) : "—"} />
        <KV k="Realized $" v={lc.realized_pnl_usdt != null ? fmtUsd(lc.realized_pnl_usdt) : "—"} />
        <KV k="Remaining" v={`${((lc.remaining_qty ?? 0)).toFixed(4)}`} />
      </div>
      {/* Chart overlay (price-scaled) */}
      {!hideChart && <>
        <div className="label mb-1">Execution chart (price-scaled)</div>
        <ExecChart lc={lc} />
        <div className="text-[11px] text-faint mt-1 mb-2">Lines = entry/stop/moved-stop/TP; dots = actual fills at true price.</div>
      </>}
      {/* Execution timeline */}
      <div className="label mb-1">Execution timeline</div>
      {(lc.events || []).map((e, i) => (
        <div key={i} className="flex justify-between items-start py-0.5">
          <span className="text-muted">
            <span className="text-text">{e.event.replace(/_/g, " ")}</span>
            {e.order_type ? <span className="text-faint"> · {e.order_type}</span> : ""}
            {e.reason ? <span className="text-faint"> · {e.reason}</span> : ""}
          </span>
          <span className="text-faint tnum whitespace-nowrap ml-2">
            {e.price != null ? `${e.price}` : ""}{e.realized_r != null ? ` · ${e.realized_r}R` : ""}{e.realized_pnl_usdt != null ? ` · ${fmtUsd(e.realized_pnl_usdt)}` : ""}{e.timestamp ? ` · ${rel(e.timestamp)}` : ""}
          </span>
        </div>
      ))}
      {lc.audit && (
        <div className="text-[11px] text-faint mt-2 pt-2 hairline">
          Audit: touch R {lc.audit.touch_final_r ?? "—"} (optimistic) · MFE {lc.audit.mfe_r ?? "—"}R · MAE {lc.audit.mae_r ?? "—"}R · {lc.audit.note}
        </div>
      )}
    </div>
  );
}

// PART 5 — exchange-like price ladder / outcome table (Stop/Entry/TP1-3/Current).
function PriceLadderTable({ lc }: { lc: TradeLifecycle }) {
  if (!lc?.available || !lc.price_ladder) return null;
  const pl = lc.price_ladder;
  const partByTp: Record<string, { pnl_usdt: number; fee_usdt: number; qty_closed: number }> = {};
  (lc.partials || []).forEach((p) => { partByTp[p.tp] = { pnl_usdt: p.pnl_usdt, fee_usdt: p.fee_usdt, qty_closed: p.qty_closed }; });
  const filledTs: Record<string, string> = {};
  (lc.events || []).forEach((e) => {
    if (e.event === "tp1_filled" && e.timestamp) filledTs.TP1 = e.timestamp;
    if (e.event === "tp2_filled" && e.timestamp) filledTs.TP2 = e.timestamp;
    if (e.event === "tp3_filled" && e.timestamp) filledTs.TP3 = e.timestamp;
  });
  const closed = !!lc.status && /closed|stopped|expired/.test(lc.status);
  const ptp: any = (lc as any).paper_tp;  // PART 3 — structural vs mechanical TP set
  const structural = ptp && ptp.applied;
  type Rw = { label: string; price?: number | null; r?: number | null; net?: number | null; fee?: number | null; status: string; tone: string; ts?: string; src?: string };
  const rows: Rw[] = [];
  rows.push({ label: "Initial stop", price: pl.initial_stop, r: -1, net: pl.max_loss_at_stop_usdt, status: "protective", tone: "text-danger" });
  if (pl.current_stop != null && pl.current_stop !== pl.initial_stop)
    rows.push({ label: "Current stop", price: pl.current_stop, r: pl.current_stop_r, status: "moved · active", tone: "text-warn" });
  rows.push({ label: "Entry", price: pl.entry, r: 0, status: "filled", tone: "text-text" });
  (pl.tps || []).forEach((t) => {
    const part = partByTp[t.label];
    const filled = !!part;
    const src = (t as any).tp_source as string | undefined;
    rows.push({ label: `${t.label} (${Math.round((t.pct_closed ?? 0) * 100)}%)`, price: t.price, r: t.r,
      net: filled ? part.pnl_usdt : t.pnl_if_filled_usdt, fee: filled ? part.fee_usdt : null,
      status: filled ? "filled" : (closed ? "not reached" : "waiting"),
      tone: filled ? "text-profit" : "text-muted", ts: filledTs[t.label],
      src: src && src !== "atr_ladder" ? src.replace(/_/g, " ") : undefined });
  });
  return (
    <div className="glass-soft p-3 mb-3 text-[12px]">
      <div className="label mb-1.5 flex items-center gap-2">
        <span>Price ladder · outcomes</span>
        {ptp?.tp_set_type && (
          <Badge tone={structural ? "b-accent" : "b-muted"}>
            {structural ? `TP: ${ptp.tp_set_type}` : "TP: ATR ladder"}
          </Badge>
        )}
      </div>
      <div className="grid gap-1" style={{ gridTemplateColumns: "1.4fr 1fr 0.6fr 0.9fr 1fr" }}>
        <div className="text-faint">Level</div><div className="text-faint text-right">Price</div>
        <div className="text-faint text-right">R</div><div className="text-faint text-right">Net $</div>
        <div className="text-faint text-right">Status</div>
        {rows.map((r, i) => (
          <FragmentRow key={i} r={r} />
        ))}
      </div>
      <div className="text-[11px] text-faint mt-1.5">{closed ? `Closed · ${lc.status}` : "Active — waiting rows fill as price reaches each level."} Net $ on partial slice, after fees.</div>
      {(() => {
        const sp: any = (lc as any).stop_protection;
        if (!sp) return null;
        const t1 = sp.after_tp1, t2 = sp.after_tp2;
        const fmt = (t: any) => t?.basis ? `${String(t.basis).replace(/_/g, " ")} (${t.r != null ? (t.r > 0 ? "+" : "") + Number(t.r).toFixed(2) + "R" : "—"})` : "—";
        return (
          <div className="text-[11px] mt-1 flex items-center gap-2">
            <Badge tone={sp.prefers_structure ? "b-accent" : "b-muted"}>
              stop: {sp.prefers_structure ? "structural" : "BE/lock"}
            </Badge>
            <span className="text-faint">after TP1 → {fmt(t1)} · after TP2 → {fmt(t2)}</span>
          </div>
        );
      })()}
    </div>
  );
}
function FragmentRow({ r }: { r: { label: string; price?: number | null; r?: number | null; net?: number | null; status: string; tone: string; ts?: string; src?: string } }) {
  return (
    <>
      <div className={`${r.tone} truncate`} title={r.src ? `${r.label} · ${r.src}` : r.label}>
        {r.label}{r.src && <span className="text-faint text-[10px]"> · {r.src}</span>}
      </div>
      <div className="text-right tnum text-text">{r.price ?? "—"}</div>
      <div className="text-right tnum text-faint">{r.r != null ? `${r.r > 0 ? "+" : ""}${r.r}` : "—"}</div>
      <div className={`text-right tnum ${(r.net ?? 0) >= 0 ? "text-profit" : "text-danger"}`}>{r.net != null ? fmtUsd(r.net) : "—"}</div>
      <div className="text-right text-faint truncate" title={r.status}>{r.status}</div>
    </>
  );
}

function Row({ k, v, sub, tone }: { k: string; v: string; sub?: string; tone?: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-muted">{k}</span>
      <span className="text-faint"><span className={`tnum ${tone ?? "text-text"}`}>{v}</span>{sub ? <span className="text-faint"> · {sub}</span> : ""}</span>
    </div>
  );
}

function ClosedDetail({ s, onClose, onChart }: { s: Signal; onClose: () => void; onChart: () => void }) {
  const oc = OUTCOME_META[s.outcome_class ?? "open"] ?? OUTCOME_META.open;
  const ce = useChartEvents(s.signal_id ?? null);
  const lcq = useLifecycle(s.signal_id ?? null);
  const tl: { t?: string; label: string }[] = [
    { t: s.created_at, label: "Signal created" },
    { t: s.entry_triggered_at, label: "Entry touched / filled" },
    { t: s.entry_alert_at, label: `Entry alert ${s.entry_alert_sent ? "sent" : (s.entry_alert_status ?? "not sent")}` },
    { t: s.close_alert_at ?? s.close_time, label: `Closed: ${s.close_reason} ${s.close_alert_sent ? "(alert sent)" : ""}` },
  ].filter((x) => x.t);
  // Model F protection events (derived, no timestamp — shown as a sequence note).
  const protSteps: string[] = [];
  if (s.protection_armed) protSteps.push("MFE ≥ +0.6R → stop moved to breakeven");
  if (s.lock_armed) protSteps.push("MFE ≥ +1.0R → locked +0.5R");
  if (s.giveback) protSteps.push("price reversed → closed at protected stop (not the touched TP)");
  const peR = s.paper_execution_r;
  const tchR = s.legacy_touch_r;
  return (
    <div className="fixed inset-0 z-50 flex items-end" style={{ background: "rgba(0,0,0,0.55)" }} onClick={onClose}>
      <div className="glass w-full p-4 rounded-t-2xl animate-rise" style={{ paddingBottom: "calc(var(--safe-b) + 16px)" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-2">
          <div className="text-[17px] font-semibold">{s.symbol} <span className={s.direction === "short" ? "text-danger" : "text-profit"}>{(s.direction || "").toUpperCase()}</span></div>
          <Badge tone={oc.tone}>{oc.label}</Badge>
        </div>
        <div className="text-[12px] text-muted mb-3">{s.close_explanation}</div>

        <div className="grid grid-cols-3 gap-2 mb-3">
          <KV k="Paper Exec R" v={peR != null ? fmtR(peR) : "—"} />
          <KV k="Legacy Touch R" v={tchR != null ? fmtR(tchR) : "—"} />
          <KV k="Risk model" v={s.risk_model ?? "—"} />
          <KV k="MFE" v={`${fmt(s.mfe_r)}R`} />
          <KV k="MAE" v={`${fmt(s.mae_r)}R`} />
          <KV k="Book" v={s.book ?? "—"} />
          <KV k="Delivery" v={deliveryMeta(s.delivery_state).label} />
          <KV k="Catalyst" v={catalystMeta(s).label} />
          <KV k="Regime" v={regimeLabel(s)} />
          <KV k="Playbook" v={s.setup_type ?? "—"} />
          <KV k="Dupes" v={`${s.duplicates_collapsed_count ?? 0}`} />
        </div>

        {(s.catalyst_headline || s.catalyst_label_computed_at) && (
          <div className="glass-soft p-3 mb-3 text-[12px]">
            <div className="label mb-1">Catalyst</div>
            {s.catalyst_headline && <div className="text-muted">{s.catalyst_headline}</div>}
            {s.catalyst_label_computed_at && <div className="text-faint mt-1">labels computed {rel(s.catalyst_label_computed_at)}</div>}
          </div>
        )}

        {/* Paper execution accounting (Model F) — old-vs-new explanation */}
        {peR != null && tchR != null && peR !== tchR && (
          <div className="glass-soft p-3 mb-3 text-[12px]">
            <div className="label mb-1">Paper execution (Model F)</div>
            <div className="text-muted">Old accounting counted the highest TP touched ({fmtR(tchR)}). New paper execution applies early MFE-armed protection and closes at the protected stop ({fmtR(peR)}).</div>
            {protSteps.length > 0 && (
              <ul className="mt-1.5 text-faint list-disc pl-4">{protSteps.map((p, i) => <li key={i}>{p}</li>)}</ul>
            )}
          </div>
        )}

        {/* Paper sizing + fees + exact TP R + chart markers (PARTS 4/5/6/7) */}
        {ce.data?.available && (
          <div className="glass-soft p-3 mb-3 text-[12px]">
            <div className="label mb-1">Paper sizing & exit</div>
            <div className="grid grid-cols-3 gap-2">
              <KV k="Leverage" v={ce.data.leverage_used != null ? `${ce.data.leverage_used}x` : "—"} />
              <KV k="Notional" v={ce.data.position_notional_usdt != null ? `$${ce.data.position_notional_usdt.toFixed(0)}` : "—"} />
              <KV k="Margin" v={ce.data.margin_used_usdt != null ? `$${ce.data.margin_used_usdt.toFixed(0)}` : "—"} />
              <KV k="Risk $" v={ce.data.risk_usdt != null ? `$${ce.data.risk_usdt.toFixed(1)}` : "—"} />
              <KV k="Net $" v={ce.data.net_pnl_usdt != null ? fmtUsd(ce.data.net_pnl_usdt) : "—"} />
              <KV k="Exit px" v={ce.data.exit_price != null ? `${ce.data.exit_price}` : "—"} />
            </div>
            <div className="text-[11px] text-faint mt-1.5">leverage ≠ risk — stop distance × size defines risk.</div>
            <div className="label mt-2 mb-1">TP levels (exact R)</div>
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="b-muted">TP1 {ce.data.tp_r_exact?.tp1 ?? "—"}R</Badge>
              <Badge tone="b-muted">TP2 {ce.data.tp_r_exact?.tp2 ?? "—"}R</Badge>
              <Badge tone="b-muted">TP3 {ce.data.tp_r_exact?.tp3 ?? "—"}R</Badge>
              {ce.data.tp_quality && <Badge tone="b-warn">{ce.data.tp_quality.label}</Badge>}
              <Badge tone="b-muted">VP {ce.data.tp_quality?.volume_profile_supported ?? "unknown"}</Badge>
            </div>
            {ce.data.tp_quality && <div className="text-[11px] text-faint mt-1">{ce.data.tp_quality.note}</div>}
            {/* PART 6 — paper TP = structural/maker-first (B book); production TP unchanged */}
            {ce.data.paper_execution_b && (
              <>
                <div className="label mt-2 mb-1">Paper execution — structural + maker-first (B)</div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone="b-accent">{ce.data.paper_execution_b.tp_set_label ?? "—"}</Badge>
                  <Badge tone="b-muted">entry {ce.data.paper_execution_b.entry_order_type ?? "—"}</Badge>
                  <Badge tone="b-muted">exit {ce.data.paper_execution_b.exit_order_type ?? "—"}</Badge>
                  <Badge tone="b-muted">stop {ce.data.paper_execution_b.stop_order_type ?? "taker"}</Badge>
                  <Badge tone="b-muted">{ce.data.paper_execution_b.leverage_used ?? "—"}x</Badge>
                </div>
                <div className="text-[11px] text-faint mt-1">
                  B net {ce.data.paper_execution_b.net_pnl_usdt != null ? fmtUsd(ce.data.paper_execution_b.net_pnl_usdt) : "—"} · fees ${(ce.data.paper_execution_b.fees_usdt ?? 0).toFixed(2)} (A net {ce.data.net_pnl_usdt != null ? fmtUsd(ce.data.net_pnl_usdt) : "—"}) · production TP unchanged · paper TP = structural/maker-first
                </div>
              </>
            )}
          </div>
        )}

        {/* Exchange-like position lifecycle (PART 3/4/5/6) — partial fills, moved/structural
            stops, price-scaled chart, execution timeline, blended R + $. */}
        {lcq.data?.available && <LifecyclePanel lc={lcq.data} />}

        <div className="label mb-1.5">Timeline</div>
        <div className="glass-soft p-3 mb-3">
          {tl.map((x, i) => (
            <div key={i} className="flex justify-between items-center py-1 text-[12px]">
              <span className="text-muted">{x.label}</span><span className="text-faint tnum">{rel(x.t)}</span>
            </div>
          ))}
          {protSteps.map((p, i) => (
            <div key={`p${i}`} className="flex justify-between items-center py-1 text-[12px]">
              <span className="text-accent">↳ {p}</span>
            </div>
          ))}
          {(s.duplicate_signal_ids?.length ?? 0) > 0 && (
            <div className="text-[11px] text-faint mt-2 pt-2 hairline">Collapsed {s.duplicate_signal_ids!.length} duplicate signal_id(s) for this one economic trade.</div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button className="btn" onClick={onChart}><i className="ti ti-chart-candle mr-1.5" />Chart</button>
          <button className="btn btn-accent" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ========================================================= TRADE DETAIL =====
export function TradeDetail({ signal, onBack, onManual }: { signal: Signal; onBack: () => void; onManual: (s: Signal) => void }) {
  const tf = signal.asset_class === "stocks" ? "15m" : "5m";
  const q = useChart(signal.symbol, tf);
  const ce = useChartEvents(signal.signal_id ?? null);
  const lcq = useLifecycle(signal.signal_id ?? null);
  const a = signal.actionability;
  const closed = isClosedTrade(signal);
  const canManual = a.actionable && a.status === "actionable";

  return (
    <Screen>
      <button className="btn !py-2 mb-3" onClick={onBack}><i className="ti ti-arrow-left mr-1" />Back</button>
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-[19px] font-semibold truncate">{signal.symbol} <span className={signal.direction === "short" ? "text-danger" : "text-profit"}>{signal.direction?.toUpperCase()}</span></div>
          <div className="text-[12px] text-faint truncate">{signal.asset_class} · {signal.mode} · Tier {signal.tier} · {Math.round(signal.score)} · {lcq.data?.regime?.label ?? "—"} · created {rel(signal.created_at)}</div>
          {(lcq.data as any)?.entry_mode?.entry_mode && (() => {
            const em: any = (lcq.data as any).entry_mode;
            const pull = em.entry_mode === "PULLBACK_LIMIT";
            const sd: any = (lcq.data as any).stock_direction;
            return (
              <div className="mt-1 flex flex-wrap gap-1.5">
                <Badge tone={pull ? "b-muted" : "b-accent"}>
                  entry: {String(em.entry_mode).replace(/_/g, " ").toLowerCase()}{em.entry_style ? ` · ${em.entry_style.replace(/_/g, " ")}` : ""}
                </Badge>
                {sd?.dir_label && (
                  <Badge tone={sd.dir_label === "MULTI_FACTOR_CONFLICT" ? "b-warn" : (sd.dir_label === "EMA_ONLY" ? "b-muted" : "b-accent")}>
                    dir: {String(sd.direction)} · {String(sd.dir_label).replace(/_/g, " ").toLowerCase()} ({sd.factors_used}f)
                  </Badge>
                )}
                {(() => {
                  const el: any = (lcq.data as any).entry_latency;
                  if (!el?.cause || el.cause === "FAST") return null;
                  const bug = el.cause === "DETECTION_LATENCY";
                  return (
                    <Badge tone={bug ? "b-danger" : "b-warn"} >
                      entry latency: {String(el.cause).replace(/_/g, " ").toLowerCase()}{el.recorded_latency_min != null ? ` · ${Math.round(el.recorded_latency_min)}m` : ""}
                    </Badge>
                  );
                })()}
              </div>
            );
          })()}
        </div>
        <ActionabilityBadge s={a.status} />
      </div>

      {/* CHART FIRST — candlestick with TRUE execution markers + price lines */}
      <div className="mt-3">
        {q.isLoading && <Skeleton h={300} />}
        {q.data && !q.data.candles_available && <EmptyState icon="▱" title="Chart data unavailable" sub="Not reconstructed — shown honestly, no fake precision." />}
        {q.data?.candles_available && <ChartPanel candles={q.data.candles} overlays={q.data.overlays ?? {}} markers={ce.data?.markers} lines={ce.data?.levels} />}
      </div>

      {/* compact PnL header */}
      {closed && (
        <div className="glass p-4 mt-3 flex items-center justify-between" style={{ background: (lcq.data?.blended_r ?? signal.paper_execution_r ?? 0) >= 0 ? "linear-gradient(150deg, rgba(39,209,139,0.12), rgba(255,255,255,0.02))" : "linear-gradient(150deg, rgba(255,93,108,0.12), rgba(255,255,255,0.02))" }}>
          <div>
            <div className={`text-[26px] font-semibold tnum ${(lcq.data?.blended_r ?? signal.paper_execution_r ?? 0) >= 0 ? "text-profit" : "text-danger"}`}>{lcq.data?.blended_r != null ? fmtR(lcq.data.blended_r) : fmtR(signal.paper_execution_r)} <span className="text-[12px] text-faint">blended</span></div>
            <div className="text-[12px] text-faint mt-0.5">{(lcq.data?.status ?? signal.operator_label ?? signal.display_status ?? signal.paper_execution_outcome ?? signal.final_outcome ?? "").toString().toUpperCase()} · net {lcq.data?.realized_pnl_usdt != null ? fmtUsd(lcq.data.realized_pnl_usdt) : "—"} · legacy touch {fmtR(signal.final_r)}</div>
          </div>
          <div className="text-right text-[12px]">
            <div className="text-profit">MFE {fmt(signal.mfe_r)}R</div>
            <div className="text-danger mt-1">MAE {fmt(signal.mae_r)}R</div>
          </div>
        </div>
      )}

      {/* price ladder outcome table + full lifecycle (chart hidden — candlestick is above) */}
      {lcq.data?.available && <div className="mt-3"><PriceLadderTable lc={lcq.data} /></div>}
      {lcq.data?.available && <LifecyclePanel lc={lcq.data} hideChart />}

      <div className="glass p-4 mt-3">
        <div className="label mb-2.5">Setup analysis</div>
        <Analysis k="Catalyst" v={signal.news_supported ? "catalyst-backed" : "technical-only"} ok={!!signal.news_supported} />
        <Analysis k="Funding / OI" v={signal.oi_context ?? "—"} ok={!(signal.oi_context ?? "").includes("squeeze")} />
        <Analysis k="Concentration" v={signal.concentration_status ?? "OK"} ok={!(signal.concentration_status ?? "").includes("shadow")} />
        <Analysis k="Freshness" v={a.freshness.label} ok={a.freshness.ok} />
        <Analysis k="RR (TP1)" v={signal.expected_rr_tp1 != null ? `${signal.expected_rr_tp1.toFixed(2)}R` : "—"} ok />
        <Analysis k="Invalidation" v={fmt(signal.invalidation ?? signal.stop_loss)} ok />
        <Analysis k="Manually actionable" v={a.actionable ? "yes" : `no — ${a.blocked_reason}`} ok={a.actionable} />
      </div>

      {/* Crypto Quality Overlay per-signal diagnostic (read-only) — crypto only */}
      {signal.asset_class === "crypto" && <CryptoOverlaySignalPanel signal={signal} />}

      {!closed && (
        canManual
          ? <button className="btn btn-accent w-full mt-3" onClick={() => onManual(signal)}>Manual Entry</button>
          : <button className="btn w-full mt-3" disabled>Not actionable — {a.blocked_reason}</button>
      )}
    </Screen>
  );
}
function Analysis({ k, v, ok }: { k: string; v: string; ok: boolean }) {
  return (
    <div className="flex justify-between items-center py-1.5 hairline last:border-0 text-[13px]">
      <span className="text-muted">{k}</span>
      <span className="flex items-center gap-1.5">{v}<i className={`ti ${ok ? "ti-check text-profit" : "ti-alert-triangle text-warn"} text-[14px]`} /></span>
    </div>
  );
}

// ============================================================== MARKET =====
export function Market() {
  const q = useMarket();
  const md = useMarketDashboard();
  const d = md.data;
  const fng = d?.crypto_fear_greed;
  const fngTone = fng == null ? "text-faint" : fng >= 75 ? "text-danger" : fng >= 55 ? "text-profit"
    : fng >= 45 ? "text-warn" : fng >= 25 ? "text-warn" : "text-danger";
  const fngLabel = fng == null ? "n/a" : fng >= 75 ? "Extreme greed" : fng >= 55 ? "Greed"
    : fng >= 45 ? "Neutral" : fng >= 25 ? "Fear" : "Extreme fear";
  return (
    <Screen>
      <H title="Market" sub="risk · regime · news now" />
      {d?.available ? (
        <>
          {d.stale_warning && (
            <div className="glass-soft p-2.5 mb-3 text-[11px] text-warn">
              ⚠ Market snapshot {d.stale ? "stale" : "aging"} ({d.age_hours}h old) — Opus routine updates ~every 4h.
            </div>
          )}
          {/* Header: modes */}
          <div className="grid grid-cols-2 gap-3">
            <MetricCard label="Crypto mode" value={cap(d.crypto_market_mode)} tone="text-text"
              sub={`regime ${cap(d.crypto_regime)} · conf ${pct(d.confidence)}`} />
            <MetricCard label="Stocks mode" value={cap(d.stocks_market_mode)} tone="text-text"
              sub={`regime ${cap(d.stocks_regime)} · upd ${d.timestamp ? rel(d.timestamp) : "—"}`} />
            <MetricCard label="Crypto Fear & Greed" value={fng != null ? `${fng}` : "—"} tone={fngTone} sub={fngLabel} />
            <MetricCard label="Volatility (VIX)" value={d.extras?.vix != null ? `${d.extras.vix}` : "n/a"}
              tone={d.extras?.vix == null ? "text-faint" : (d.extras.vix >= 25 ? "text-danger" : d.extras.vix >= 18 ? "text-warn" : "text-profit")}
              sub={d.extras?.vix == null ? "VIX unavailable" : `SPY ${d.extras?.spy_trend ?? "—"} · QQQ ${d.extras?.qqq_trend ?? "—"}`} />
          </div>
          {/* Risk now */}
          <div className="label mb-2 mt-3">Main risk now</div>
          <div className="glass p-3.5 mb-2 text-[12px]">
            <div className="text-faint mb-0.5">Crypto</div>
            <div className="text-muted mb-2">{d.crypto_main_risk || "—"}</div>
            <div className="text-faint mb-0.5">Stocks</div>
            <div className="text-muted">{d.stocks_main_risk || "—"}</div>
          </div>
          {/* Today news */}
          <div className="label mb-2 mt-3">Today — important news</div>
          {(d.today_news ?? []).length === 0 && <div className="glass-soft p-2.5 text-[12px] text-faint">No curated news for today.</div>}
          {(d.today_news ?? []).slice(0, 6).map((n, i) => (
            <div key={i} className="glass-soft p-2.5 mb-2 text-[12px]">
              <div className="flex justify-between items-center">
                <span className="font-medium">{n.title}</span>
                <Badge tone={(n.impact || "").includes("neg") ? "b-danger" : (n.impact || "").includes("pos") ? "b-profit" : "b-muted"}>{n.asset_or_sector || "—"}</Badge>
              </div>
              {n.why_it_matters && <div className="text-faint mt-1">{n.why_it_matters}</div>}
            </div>
          ))}
          {/* Long-term news */}
          <div className="label mb-2 mt-3">Long-term themes</div>
          {(d.long_term_news ?? []).length === 0 && <div className="glass-soft p-2.5 text-[12px] text-faint">No long-term themes.</div>}
          {(d.long_term_news ?? []).slice(0, 5).map((n, i) => (
            <div key={i} className="glass-soft p-2.5 mb-2 text-[12px]">
              <div className="flex justify-between items-center">
                <span className="font-medium">{n.title}</span>
                <Badge tone="b-muted">{n.asset_or_sector || "—"}</Badge>
              </div>
              {n.why_it_matters && <div className="text-faint mt-1">{n.why_it_matters}</div>}
            </div>
          ))}
          {/* Extras */}
          <div className="label mb-2 mt-3">Extras</div>
          <div className="glass p-3.5 mb-3 text-[12px] grid grid-cols-2 gap-2">
            <KV k="BTC dominance" v={d.extras?.btc_dominance != null ? `${d.extras.btc_dominance}%` : "—"} />
            <KV k="ETH/BTC" v={d.extras?.eth_btc != null ? `${d.extras.eth_btc}` : "—"} />
            <KV k="SPY trend" v={d.extras?.spy_trend ?? "—"} />
            <KV k="QQQ trend" v={d.extras?.qqq_trend ?? "—"} />
          </div>
          <div className="text-[11px] text-faint mb-3">Source: {d.source_summary || d.generated_by || "—"} · {d.note}</div>
        </>
      ) : (
        <div className="glass-soft p-3 mb-3 text-[12px] text-faint">
          Market dashboard not populated yet — the Opus enriched-review routine writes it (~every 4h). {d?.reason ? `(${d.reason})` : ""}
        </div>
      )}

      {/* Desk-derived signals (narratives + funding/OI) kept as secondary detail */}
      <div className="label mb-2 mt-3">Desk narratives</div>
      {q.isLoading && <SkeletonList n={2} h={56} />}
      {(q.data?.narratives ?? []).length === 0 && !q.isLoading && <div className="glass-soft p-2.5 text-[12px] text-faint">No active narratives.</div>}
      {(q.data?.narratives ?? []).slice(0, 5).map((n, i) => (
        <div key={i} className="glass-soft p-3 mb-2">
          <div className="flex justify-between items-center">
            <div className="font-semibold capitalize">{n.name}</div>
            <Badge tone={n.strength >= 70 ? "b-accent" : "b-muted"}>{n.strength}/100</Badge>
          </div>
          <div className="text-[11px] text-faint mt-1.5">{n.symbols.join(" · ")} · {n.count} signals</div>
        </div>
      ))}

      {/* Stocks Position Framework — SHADOW ONLY read-model (never actionable/live/Telegram). */}
      <StocksPositionShadow />
    </Screen>
  );
}

// ==================================================== STOCKS POSITION SHADOW =====
function StocksPositionShadow() {
  const sum = useStocksPositionSummary();
  const cand = useStocksPositionCandidates(10);
  const s = sum.data;
  const c = cand.data;

  return (
    <>
      <div className="flex items-center justify-between mb-2 mt-4">
        <div className="label">Stocks Position Shadow</div>
        <Badge tone="b-shadow">SHADOW ONLY</Badge>
      </div>
      <div className="text-[10.5px] text-faint mb-2">
        No live · no Telegram · no actionability · not in the paper book. USD net is authoritative.
      </div>

      {(sum.isLoading || cand.isLoading) && <SkeletonList n={2} h={70} />}
      {(sum.isError || cand.isError) && (
        <ErrorBanner msg="Could not load stocks position shadow data."
          onRetry={() => { sum.refetch(); cand.refetch(); }} />
      )}

      {s && c && !sum.isLoading && !cand.isLoading && (
        !s.available ? (
          <EmptyState icon="◑" title="No stored candidates"
            sub={s.reason || "No latest scan yet — run stocks-position-scan."} />
        ) : (
          <>
            <div className="glass p-3.5 mb-3 animate-rise">
              <div className="grid grid-cols-2 gap-3">
                <KV k="Open candidates" v={s.open_candidates} />
                <KV k="Latest scan" v={s.latest_scan ? rel(s.latest_scan) : "—"} tone="text-faint" />
                <KV k="Actionable" v={s.actionable ? "yes" : "no"} tone="text-faint" />
                <KV k="Outcomes" v={s.outcomes_available ? "engine ready" : "pending"} tone="text-faint" />
              </div>
            </div>
            {c.count === 0 ? (
              <div className="glass-soft p-2.5 text-[12px] text-faint">
                No open shadow candidates in the latest scan.
              </div>
            ) : (
              c.candidates.slice(0, 10).map((x) => (
                <div key={`${x.symbol}-${x.created_at}`} className="glass-soft p-3 mb-2 text-[12px]">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold">{x.symbol}</div>
                    <Badge tone={(x.score ?? 0) >= 70 ? "b-profit" : (x.score ?? 0) >= 50 ? "b-accent" : "b-muted"}>
                      {x.score ?? "—"}/100
                    </Badge>
                  </div>
                  <div className="text-faint text-[11px] mt-0.5">
                    {(x.sector || "—")} · {x.setup_variant || "—"}
                  </div>
                  {x.review_verdict && (
                    <div className="mt-1">
                      <Badge tone={
                        x.review_verdict === "approve_shadow" ? "b-profit"
                          : x.review_verdict === "wait_pullback" ? "b-warn"
                          : x.review_verdict.startsWith("reject") ? "b-danger" : "b-muted"}>
                        review: {x.review_verdict.replace(/_/g, " ")}
                        {x.review_confidence != null ? ` (${Math.round(x.review_confidence * 100)}%)` : ""}
                      </Badge>
                      {x.reviewed_at && <span className="text-[10px] text-faint ml-1">{rel(x.reviewed_at)}</span>}
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-2 mt-2 text-[11px]">
                    <KV k="Entry" v={fmt(x.entry_price)} />
                    <KV k="Stop" v={fmt(x.stop_price)} tone="text-danger" />
                    <KV k="TP1" v={`${fmt(x.tp1)} (${fmtR(x.tp1_r)})`} tone="text-profit" />
                  </div>
                </div>
              ))
            )}
          </>
        )
      )}
    </>
  );
}

function cap(s?: string | null): string {
  if (!s) return "—";
  return String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function pct(v?: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

// ================================================================ RISK =====
function EditMetric({ label, value, tone, sub, onClick }:
  { label: string; value: ReactNode; tone?: string; sub?: ReactNode; onClick: () => void }) {
  return (
    <button onClick={() => { haptic("light"); onClick(); }}
      className="glass-soft p-3.5 text-left animate-rise active:scale-[0.98] transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50">
      <div className="label flex items-center justify-between">{label}<i className="ti ti-pencil text-faint text-[12px]" /></div>
      <div className={`metric mt-1.5 ${tone || "text-text"}`}>{value}</div>
      {sub && <div className="text-[11px] text-faint mt-1">{sub}</div>}
    </button>
  );
}

export function Risk() {
  const q = useRisk();
  const audit = useAudit(40);
  const [edit, setEdit] = useState<EditTarget>(null);
  const r = q.data;
  const changes = (audit.data?.audit ?? []).filter((a) =>
    /^SET_|^ENABLE_|^DISABLE_|EMERGENCY|RESUME/.test(a.action_type)).slice(0, 6);
  return (
    <Screen>
      <H title="Risk" sub="exposure & limits — tap a value to change it" />
      {q.isLoading && <SkeletonList n={4} h={70} />}
      {r && (
        <>
          <div className="glass p-4">
            <div className="label mb-2">Trading mode</div>
            <div className="flex flex-wrap gap-2">
              {["disabled", "paper"].map((m) => <Badge key={m} tone={r.trading_mode === m ? "b-accent" : "b-muted"}>{m}</Badge>)}
              <Badge tone="b-danger"><i className="ti ti-lock text-[11px] mr-0.5" />manual_live</Badge>
              <Badge tone="b-danger"><i className="ti ti-lock text-[11px] mr-0.5" />auto_live</Badge>
            </div>
            <div className="text-[11px] text-faint mt-2">Live &amp; auto-live are locked — require a 30-day forward-validation readiness audit.</div>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-3">
            <EditMetric label="Paper balance" value={`$${r.paper_balance.toLocaleString()}`}
              onClick={() => setEdit({ kind: "num", field: "paper_balance", current: r.paper_balance })} />
            <EditMetric label="Risk / trade" value={`${(r.risk_per_trade * 100).toFixed(2)}%`} tone="text-accent"
              onClick={() => setEdit({ kind: "num", field: "risk_per_trade", current: r.risk_per_trade })} />
            <EditMetric label="Daily loss cap" value={`${(r.daily_loss_limit * 100).toFixed(1)}%`} tone="text-warn"
              onClick={() => setEdit({ kind: "num", field: "daily_loss_limit", current: r.daily_loss_limit })} />
            <EditMetric label="Weekly loss cap" value={`${(r.weekly_loss_limit * 100).toFixed(1)}%`} tone="text-warn"
              onClick={() => setEdit({ kind: "num", field: "weekly_loss_limit", current: r.weekly_loss_limit })} />
            <EditMetric label="Max positions" value={r.max_positions}
              onClick={() => setEdit({ kind: "num", field: "max_positions", current: r.max_positions })} />
            <MetricCard label="Max sector exposure" value={r.max_sector_exposure} sub="concentration guard" />
          </div>

          <div className="glass p-4 mt-3">
            <div className="label mb-2">Allowed modes (paper)</div>
            {Object.entries(r.allowed_modes).map(([k, v]) => {
              const locked = k.includes("scalp");
              const row = (
                <div className="flex justify-between items-center w-full text-[13px]">
                  <span className="capitalize">{k.replace(/_/g, " ")}</span>
                  {locked
                    ? <Badge tone="b-danger"><i className="ti ti-lock text-[11px] mr-0.5" />research only</Badge>
                    : <Badge tone={v ? "b-profit" : "b-muted"}>{v ? "enabled" : "paused"}</Badge>}
                </div>
              );
              return locked ? (
                <div key={k} className="py-2 hairline last:border-0">{row}</div>
              ) : (
                <button key={k} onClick={() => { haptic("light"); setEdit({ kind: "mode", mode: k, enabled: !!v }); }}
                  className="w-full py-2 hairline last:border-0 active:scale-[0.99] transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent/40 rounded">
                  {row}
                </button>
              );
            })}
          </div>

          <div className="glass p-4 mt-3">
            <div className="label mb-2">Recent risk changes</div>
            {changes.length === 0 && <div className="text-faint text-[12px]">No changes yet.</div>}
            {changes.map((a) => (
              <div key={a.id} className="flex justify-between items-center py-1.5 hairline last:border-0 text-[12px]">
                <span className="truncate"><span className="text-muted">{a.action_type}</span></span>
                <span className="flex items-center gap-2">
                  <Badge tone={a.result === "applied" || a.result === "paused" ? "b-profit" : a.result === "rejected" ? "b-danger" : "b-muted"}>{a.result ?? "—"}</Badge>
                  <span className="text-faint tnum">{rel(a.ts)}</span>
                </span>
              </div>
            ))}
          </div>

          <div className="text-[11px] text-faint mt-3 leading-relaxed">
            Every change is confirmed, audited, applied via the command queue, and reversible.
            Settings are runtime overrides in the control DB — the trading YAML is never edited.
            Live &amp; scalp are enforced server-side.
          </div>
        </>
      )}
      {edit && <RiskEditModal target={edit} onClose={() => setEdit(null)} />}
    </Screen>
  );
}

// ============================================================== SYSTEM =====
function ShadowAB() {
  const [d, setD] = useState<any>(null);
  const [fwd, setFwd] = useState<any>(null);
  const [tr, setTr] = useState<any>(null);
  const [fees, setFees] = useState<any>(null);
  const [brk, setBrk] = useState<any>(null);
  const [dim, setDim] = useState<string>("mode");
  const [showBackfill, setShowBackfill] = useState<boolean>(false);
  const [filter, setFilter] = useState<string>("all");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { let on = true;
    api.paperShadowSummary().then(r => { if (on) setD(r); }).catch(() => {});
    api.paperShadowForward().then(r => { if (on) setFwd(r); }).catch(() => {});
    api.paperShadowTrades(80).then(r => { if (on) setTr(r); }).catch(() => {});
    api.paperShadowFees().then(r => { if (on) setFees(r); }).catch(() => {});
    api.paperShadowBreakdown().then(r => { if (on) setBrk(r); }).catch(() => {});
    return () => { on = false; }; }, []);
  if (!d) return null;
  if (!d.available) return (
    <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="shadow-ab">
      <div className="label mb-1">Paper Shadow A/B</div>
      <div className="text-faint">{d.reason ?? "not yet populated"} · forward evidence accumulates from activation.</div>
    </div>
  );
  const Win = ({ title, w }: { title: string; w: any }) => {
    const f = w.forward_since_activation, b = w.historical_backfill;
    const row = (label: string, g: any, warn?: boolean) => (
      <div className="grid gap-1 mb-1" style={{ gridTemplateColumns: "1.2fr 1fr 1fr 1fr" }}>
        <div className={`text-faint ${warn ? "text-warn" : ""}`}>{label}</div>
        <div className="text-right tnum">A {g.A.trades}t · <span className={g.A.net_r >= 0 ? "text-profit" : "text-danger"}>{g.A.net_r >= 0 ? "+" : ""}{g.A.net_r}R</span></div>
        <div className="text-right tnum">B {g.B.trades}t · <span className={g.B.net_r >= 0 ? "text-profit" : "text-danger"}>{g.B.net_r >= 0 ? "+" : ""}{g.B.net_r}R</span></div>
        <div className={`text-right tnum ${g.delta.net_r >= 0 ? "text-profit" : "text-danger"}`}>Δ{g.delta.net_r >= 0 ? "+" : ""}{g.delta.net_r}R</div>
      </div>
    );
    return (<>
      {row("FORWARD (valid)", f)}
      {row("backfill (look-ahead)", b, true)}
    </>);
  };
  const bd = d.forward_since_activation.B_detail;
  const bd2 = d.historical_backfill.B_detail;
  return (
    <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="shadow-ab">
      <div className="flex items-center justify-between mb-1.5">
        <span className="label">Paper Shadow A/B</span>
        <Badge tone="b-warn">PAPER · LIVE LOCKED</Badge>
      </div>
      <Win title="A/B" w={d} />
      {fwd?.available && fwd.gate && (
        <div className="text-[11px] mt-1.5 flex items-center gap-2" data-testid="shadow-gate">
          <Badge tone={fwd.gate.verdict === "READY" ? "b-profit" : "b-muted"}>
            promotion gate: {fwd.gate.verdict}
          </Badge>
          <span className="text-faint">
            {(fwd.gate.criteria || []).filter((c: any) => c.ok).length}/{(fwd.gate.criteria || []).length} criteria · evaluation-only (no auto-promote)
          </span>
        </div>
      )}
      <div className="text-[11px] text-faint mt-1">
        activated {d.activated_at ? rel(d.activated_at) : "—"} · fwd rows {d.counts.forward_rows} · backfill rows {d.counts.backfill_rows}.
        B: missed {bd.missed + bd2.missed} · no-chase {bd.skipped_no_chase + bd2.skipped_no_chase} · dir-flips {bd.direction_flips + bd2.direction_flips} · structural-TP {bd.structural_tp + bd2.structural_tp}.
      </div>
      {/* PART 8 — DATA_GAP_LATE cohort is dirty (stock-intraday coverage gaps) → excluded from the forward edge */}
      {fwd?.available && (fwd.data_gap_late_excluded ?? 0) > 0 && (
        <div className="text-[11px] text-warn mt-1" data-testid="shadow-datagap">
          ⚠ {fwd.data_gap_late_excluded} DATA_GAP_LATE signal(s) excluded from forward edge — {fwd.primary_cohort ?? "clean cohort"}
        </div>
      )}
      {/* PART 3 — maker fill realism */}
      {fwd?.available && fwd.maker && fwd.maker.posted > 0 && (() => {
        const m = fwd.maker; const low = (m.fill_rate_pct ?? 100) < 50;
        return (
          <div className="text-[11px] mt-1.5" data-testid="shadow-maker">
            <span className="label">Maker realism</span> · posted {m.posted} · filled {m.filled} ·
            missed {m.missed} · taker-fallback {m.taker_fallback} ·
            <span className={low ? "text-warn" : "text-faint"}> fill-rate {m.fill_rate_pct ?? "—"}%</span>
            {low && <span className="text-warn"> ⚠ many limits missed — B edge may lean on optimistic fills</span>}
          </div>
        );
      })()}
      {/* PART 2 — fee assumptions card */}
      {fees && (
        <div className="glass p-2 mt-2 text-[11px]" data-testid="shadow-fees">
          <div className="flex items-center justify-between">
            <span className="label">Fee assumptions</span>
            <Badge tone="b-muted">{fees.active_profile}</Badge>
          </div>
          <div className="text-faint mt-1">
            maker {(fees.maker_fee * 100).toFixed(3)}% · taker {(fees.taker_fee * 100).toFixed(3)}% ·
            slippage {(fees.slippage_estimate * 100).toFixed(2)}% · custom override {fees.custom_account_override ? "on" : "off"}.
            All A/B numbers are <span className="text-text">after fees</span>.
          </div>
          {fees.fee_fragile_warning && <div className="text-warn mt-0.5">⚠ B wins gross but not net — fee-fragile</div>}
        </div>
      )}
      {/* By-mode A/B breakdown */}
      {brk?.available && brk.dimensions?.[dim] && (() => {
        const dims = [["mode", "mode"], ["entry_mode", "entry"], ["order_type", "maker/taker"],
          ["regime", "regime"], ["symbol", "symbol"], ["sector", "sector"], ["tp_set", "TP"]];
        const win = showBackfill ? "backfill" : "forward";
        const rows = (brk.dimensions[dim] || [])
          .map((g: any) => ({ key: g.key, w: g[win] }))
          .filter((x: any) => x.w && (x.w.A.trades + x.w.B.trades) > 0)
          .slice(0, 12);
        return (
          <div className="mt-2" data-testid="shadow-bymode">
            <div className="flex items-center justify-between mb-1">
              <span className="label">By {dim} {showBackfill ? "· backfill (look-ahead)" : "· forward (valid)"}</span>
              <button onClick={() => setShowBackfill(v => !v)}
                className={`px-2 py-0.5 rounded-full text-[10px] ${showBackfill ? "bg-warn/20 text-warn" : "text-faint glass-soft"}`}>
                {showBackfill ? "backfill" : "forward"}
              </button>
            </div>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {dims.map(([k, lbl]) => (
                <button key={k} onClick={() => setDim(k)}
                  className={`px-2 py-0.5 rounded-full text-[10px] ${dim === k ? "bg-accent/30 text-text" : "text-faint glass-soft"}`}>{lbl}</button>
              ))}
            </div>
            {rows.length === 0 ? <div className="text-[11px] text-faint">no {win} rows for this split yet.</div> :
              rows.map((x: any) => (
                <div key={x.key} className="grid gap-1 text-[10.5px] py-0.5 border-b border-white/5"
                  style={{ gridTemplateColumns: "1.5fr 1fr 1fr 0.8fr 0.7fr" }}>
                  <div className="truncate text-faint">{x.key}</div>
                  <div className="text-right tnum">A {x.w.A.trades}·<span className={x.w.A.net_r >= 0 ? "text-profit" : "text-danger"}>{x.w.A.net_r >= 0 ? "+" : ""}{x.w.A.net_r}R</span></div>
                  <div className="text-right tnum">B {x.w.B.trades}·<span className={x.w.B.net_r >= 0 ? "text-profit" : "text-danger"}>{x.w.B.net_r >= 0 ? "+" : ""}{x.w.B.net_r}R</span></div>
                  <div className={`text-right tnum ${x.w.delta_r >= 0 ? "text-profit" : "text-danger"}`}>Δ{x.w.delta_r >= 0 ? "+" : ""}{x.w.delta_r}</div>
                  <div className="text-right text-faint">{x.w.B.maker_fill_rate != null ? `mk${x.w.B.maker_fill_rate}%` : x.w.data_gap_excluded ? `gap${x.w.data_gap_excluded}` : `w${x.w.B.win_rate}%`}</div>
                </div>
              ))}
            <div className="text-[10px] text-faint mt-1">forward = valid evidence · backfill = look-ahead hypothesis, not proof.</div>
          </div>
        );
      })()}
      {/* B composition / statistics (forward) — answers "is B momentum or still many expired" */}
      {brk?.available && brk.dimensions?.entry_mode && (() => {
        const IMMEDIATE = ["MOMENTUM_TAKER_NOW", "BREAKOUT_CONTINUATION"];
        const FALLBACK = ["LIMIT_THEN_TAKER_TIMEOUT"];
        const SKIP = ["NO_CHASE_SKIP"];
        const rows = (brk.dimensions.entry_mode || [])
          .map((g: any) => ({ mode: g.key, w: g.forward }))
          .filter((x: any) => x.w && (x.w.A.trades + x.w.B.trades + x.w.B.missed_entries + x.w.B.no_chase) > 0);
        const B = (m: any) => m.w.B;
        const tot = rows.reduce((a: any, x: any) => {
          a.trades += B(x).trades; a.net_r += B(x).net_r; a.wins += Math.round(B(x).win_rate * B(x).trades / 100);
          a.skip += B(x).no_chase; a.missed += B(x).missed_entries;
          if (IMMEDIATE.includes(x.mode)) a.immediate += B(x).trades;
          else if (FALLBACK.includes(x.mode)) a.fallback += B(x).trades;
          else if (SKIP.includes(x.mode)) a.skipMode += B(x).trades + B(x).no_chase;
          else a.pullback += B(x).trades;
          return a;
        }, { trades: 0, net_r: 0, wins: 0, skip: 0, missed: 0, immediate: 0, fallback: 0, pullback: 0, skipMode: 0 });
        const winRate = tot.trades ? Math.round(100 * tot.wins / tot.trades) : 0;
        return (
          <div className="mt-3" data-testid="shadow-bstats">
            <div className="label mb-1">B statistics — new-logic (forward, valid)</div>
            <div className="glass-soft p-2 text-[11px]">
              <div className="flex justify-between"><span className="text-faint">filled trades</span><span className="tnum">{tot.trades}</span></div>
              <div className="flex justify-between"><span className="text-faint">net R</span><span className={`tnum ${tot.net_r >= 0 ? "text-profit" : "text-danger"}`}>{tot.net_r >= 0 ? "+" : ""}{Math.round(tot.net_r * 100) / 100}R</span></div>
              <div className="flex justify-between"><span className="text-faint">win rate</span><span className="tnum">{winRate}%</span></div>
              <div className="flex justify-between"><span className="text-faint">no-chase skips · missed</span><span className="tnum">{tot.skip + tot.skipMode} · {tot.missed}</span></div>
              <div className="mt-1.5 pt-1.5 border-t border-white/10">
                <div className="text-[10px] text-faint mb-1">entry style mix (why fewer expired than A's pullback-only)</div>
                <div className="flex flex-wrap gap-1">
                  <span className="badge b-profit">immediate (mom/breakout) {tot.immediate}</span>
                  <span className="badge b-accent">limit→taker fallback {tot.fallback}</span>
                  <span className="badge b-muted">pullback {tot.pullback}</span>
                  <span className="badge b-warn">no-chase skip {tot.skipMode + tot.skip}</span>
                </div>
              </div>
              <div className="mt-1.5 pt-1.5 border-t border-white/10">
                {rows.map((x: any) => (
                  <div key={x.mode} className="flex items-center justify-between text-[10.5px] py-0.5">
                    <span className="truncate text-faint">{x.mode}</span>
                    <span className="tnum">{B(x).trades}t · <span className={B(x).net_r >= 0 ? "text-profit" : "text-danger"}>{B(x).net_r >= 0 ? "+" : ""}{B(x).net_r}R</span> · w{B(x).win_rate}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })()}
      {/* PART 1 — per-trade A/B detail with filters */}
      {tr?.available && tr.trades?.length > 0 && (() => {
        const f = (t: any) => filter === "all" ? true :
          filter === "fwd" ? t.valid_forward :
          filter === "B_better" ? t.highlight === "B_outperforms" :
          filter === "B_worse" ? t.highlight === "A_outperforms" :
          filter === "A_missed" ? t.highlight === "B_traded_A_missed" :
          filter === "B_skipped" ? t.highlight === "A_traded_B_skipped" :
          filter === "flip" ? t.highlight === "direction_flip" :
          filter === "datagap" ? t.data_gap : true;
        const rows = tr.trades.filter(f).slice(0, 25);
        const chips = [["all", "all"], ["fwd", "fwd only"], ["B_better", "B better"], ["B_worse", "B worse"],
          ["A_missed", "A missed"], ["B_skipped", "B skipped"], ["flip", "dir flip"], ["datagap", "data gap"]];
        return (
          <div className="mt-2" data-testid="shadow-trades">
            <div className="label mb-1">Per-trade A/B ({rows.length})</div>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {chips.map(([k, lbl]) => (
                <button key={k} onClick={() => setFilter(k)}
                  className={`px-2 py-0.5 rounded-full text-[10px] ${filter === k ? "bg-accent/30 text-text" : "text-faint glass-soft"}`}>{lbl}</button>
              ))}
            </div>
            {rows.map((t: any) => {
              const a = t.A || {}, b = t.B || {};
              const isOpen = open === t.signal_id;
              const dR = t.delta?.net_r ?? 0;
              return (
                <div key={t.signal_id} className="glass-soft p-2 mb-1 text-[11px]">
                  <button className="w-full flex items-center justify-between" onClick={() => setOpen(isOpen ? null : t.signal_id)}>
                    <span className="truncate">{t.symbol} <span className="text-faint">{t.valid_forward ? "· fwd" : "· backfill"}</span>{t.data_gap ? " · ⚠gap" : ""}</span>
                    <span className={`tnum ${dR >= 0 ? "text-profit" : "text-danger"}`}>Δ{dR >= 0 ? "+" : ""}{dR}R</span>
                  </button>
                  {isOpen && (
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {[["A (old)", a], ["B (new)", b]].map(([title, x]: any) => (
                        <div key={title} className="text-[10px]">
                          <div className="text-text mb-0.5">{title}</div>
                          <div className="text-faint">side {x.side ?? "—"}{x.direction_changed ? ` (flip ${x.old_side}→${x.side})` : ""}</div>
                          <div className="text-faint">mode {x.entry_mode ?? "—"} · {x.entry_order_type ?? "—"}</div>
                          <div className="text-faint">fill {x.fill_status ?? "—"}{x.skipped_reason ? ` (${x.skipped_reason})` : x.missed_reason ? ` (${x.missed_reason})` : ""}</div>
                          <div className="text-faint">TP {x.tp_set ?? "—"} · stop {x.structural_stop_used ? "struct" : "BE/lock"}</div>
                          <div className="text-faint">gross {x.gross_r ?? "—"}R · <span className={(x.net_r ?? 0) >= 0 ? "text-profit" : "text-danger"}>net {x.net_r ?? "—"}R</span> · fee ${x.fees_usd ?? "—"}</div>
                          {title.startsWith("B") && x.maker_posted ? <div className="text-faint">maker {x.maker_filled}/{x.maker_posted}{x.taker_fallback ? " · taker-fb" : ""}</div> : null}
                        </div>
                      ))}
                      <div className="col-span-2 text-faint">{t.why} · {t.valid_forward ? "valid forward" : "backfill (look-ahead, not proof)"}</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })()}
      <div className="text-[11px] text-warn mt-1">{d.note}</div>
    </div>
  );
}

function NewsSourceHealthCard() {
  const q = useNewsSourceHealth();
  const h = q.data;
  if (q.isLoading) return <SkeletonList n={1} h={64} />;
  if (!h) return null;
  if (!h.available) {
    return (
      <div className="glass-soft p-3 mb-3 text-[12px]">
        <div className="flex items-center justify-between">
          <span className="label">News source health</span>
          <Badge tone="b-muted">n/a</Badge>
        </div>
        <div className="text-[11px] text-faint mt-1">{h.reason ?? "artifact not found — run news-source-health on the desk"}</div>
      </div>
    );
  }
  const s = h.summary ?? {};
  const deadPrimary = s.dead_primary ?? [];
  const problems = (h.sources ?? [])
    .filter((r) => r.stale_status === "DEAD" || r.stale_status === "STALE")
    .slice(0, 8);
  const lowMatch = (h.sources ?? []).filter(
    (r) => r.symbol_match_rate_24h != null && r.symbol_match_rate_24h < 0.15 && r.rows_24h >= 10,
  );
  return (
    <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="news-source-health">
      <div className="flex items-center justify-between">
        <span className="label">News source health</span>
        <Badge tone="b-warn">read-only · live locked</Badge>
      </div>
      <div className="flex gap-2 mt-2 flex-wrap">
        <Badge tone="b-profit">OK {s.ok ?? 0}</Badge>
        <Badge tone="b-warn">STALE {s.stale ?? 0}</Badge>
        <Badge tone="b-danger">DEAD {s.dead ?? 0}</Badge>
        {(s.configured ?? 0) > 0 && <Badge tone="b-muted">CONFIGURED {s.configured}</Badge>}
        <Badge tone="b-muted">DISABLED {s.disabled ?? 0}</Badge>
      </div>
      {deadPrimary.length > 0 && (
        <div className="text-[11px] text-danger mt-2">Dead PRIMARY: {deadPrimary.join(", ")}</div>
      )}
      {lowMatch.length > 0 && (
        <div className="text-[11px] text-faint mt-1">
          Low symbol match: {lowMatch.slice(0, 4).map((r) => r.source).join(", ")}
        </div>
      )}
      {problems.length > 0 && (
        <div className="mt-2 grid grid-cols-1 gap-1">
          {problems.map((r, i) => (
            <div key={i} className="flex items-center justify-between text-[11px]">
              <span className="truncate">{r.source} <span className="text-faint">({r.source_type})</span></span>
              <Badge tone={r.stale_status === "DEAD" ? "b-danger" : "b-warn"}>{r.stale_status}</Badge>
            </div>
          ))}
        </div>
      )}
      <div className="text-[10px] text-faint mt-2">
        {h.generated_at ? `generated ${new Date(h.generated_at).toLocaleString()}` : ""}
      </div>
    </div>
  );
}

function NewsEntityHealthCard() {
  const q = useNewsEntityHealth();
  const h = q.data;
  if (q.isLoading) return <SkeletonList n={1} h={58} />;
  if (!h) return null;
  if (!h.available) {
    return (
      <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="news-entity-health">
        <div className="flex items-center justify-between">
          <span className="label">Entity resolver health</span>
          <Badge tone="b-muted">n/a</Badge>
        </div>
        <div className="text-[11px] text-faint mt-1">{h.reason ?? "artifact not found - run news-entity-health on the desk"}</div>
      </div>
    );
  }
  const w24 = h.windows?.["24h"] ?? {};
  const w72 = h.windows?.["72h"] ?? {};
  const sev = h.severity ?? "UNKNOWN";
  const tone = sev === "OK" ? "b-profit" : sev === "CRITICAL" ? "b-danger" : "b-warn";
  const resolvedPct = w24.resolved_pct == null ? "n/a" : `${Math.round((w24.resolved_pct ?? 0) * 100)}%`;
  const unresolved = w24.unresolved_symbol_tagged ?? 0;
  const maxAge = h.max_unresolved_age_minutes ?? 0;
  return (
    <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="news-entity-health">
      <div className="flex items-center justify-between">
        <span className="label">Entity resolver health</span>
        <Badge tone={tone}>{sev}</Badge>
      </div>
      <div className="grid grid-cols-2 gap-1.5 mt-2">
        <KV k="24h resolved" v={resolvedPct} />
        <KV k="unresolved tags" v={String(unresolved)} />
        <KV k="trusted 24h" v={String(w24.trusted_symbol_tagged ?? 0)} />
        <KV k="preexisting unverified" v={String(w24.preexisting_unverified ?? 0)} />
        <KV k="max unresolved age" v={`${Math.round(maxAge)}m`} />
        <KV k="72h unresolved" v={String(w72.unresolved_symbol_tagged ?? 0)} />
      </div>
      <div className="text-[10px] text-faint mt-2">
        {h.severity_reason}
        {h.resolver_last_run_at ? ` · resolver ${rel(h.resolver_last_run_at)}` : ""}
      </div>
    </div>
  );
}


function NewsCatalystsCard() {
  const q = useNewsCatalysts();
  const c = q.data;
  if (q.isLoading) return <SkeletonList n={1} h={64} />;
  if (!c) return null;
  if (!c.available) {
    return (
      <div className="glass-soft p-3 mb-3 text-[12px]">
        <div className="flex items-center justify-between">
          <span className="label">News catalysts / risk</span>
          <Badge tone="b-muted">n/a</Badge>
        </div>
        <div className="text-[11px] text-faint mt-1">{c.reason ?? "artifact not found — run news-risk on the desk"}</div>
      </div>
    );
  }
  const review = c.symbols_requiring_operator_review ?? [];
  const ev = c.events_summary ?? { available: false };
  const conflicting = ev.conflicting_symbols ?? [];
  // Group warnings by symbol → distinct effects (skip the operator-review ones already surfaced above).
  const rows = (c.warnings ?? []).filter((w) => w.effect !== "block_requires_operator_review").slice(0, 8);
  return (
    <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="news-catalysts">
      <div className="flex items-center justify-between">
        <span className="label">News catalysts / risk (risk-only)</span>
        <Badge tone="b-warn">read-only · live locked</Badge>
      </div>
      {ev.available && (
        <div className="flex gap-2 mt-2 flex-wrap">
          <Badge tone="b-muted">events {ev.count ?? 0}</Badge>
          {conflicting.length > 0 && <Badge tone="b-warn">conflicting {conflicting.length}</Badge>}
        </div>
      )}
      {review.length > 0 && (
        <div className="text-[11px] text-danger mt-2">⚠ Operator-review warning (advisory — does not gate routing): {review.slice(0, 12).join(", ")}</div>
      )}
      {conflicting.length > 0 && (
        <div className="text-[11px] text-faint mt-1">Conflicting news (no clean read): {conflicting.slice(0, 8).join(", ")}</div>
      )}
      {rows.length > 0 && (
        <div className="mt-2 grid grid-cols-1 gap-1">
          {rows.map((w, i) => (
            <div key={i} className="flex items-center justify-between text-[11px]">
              <span className="truncate">{w.symbol} <span className="text-faint">{w.reason ?? w.event_type}</span></span>
              <Badge tone="b-warn">{w.effect}</Badge>
            </div>
          ))}
        </div>
      )}
      {review.length === 0 && rows.length === 0 && (
        <div className="text-[11px] text-faint mt-2">No strong risk events (SEC/legal/hack/delisting/unlock/earnings) in window.</div>
      )}
      <div className="text-[10px] text-faint mt-2">
        Risk-only: never a buy/sell, never a score/tier change, never unlocks live.
        {c.as_of ? ` · as of ${c.as_of}` : ""}
      </div>
    </div>
  );
}


// ---- Crypto Quality Overlay (read-only diagnostics) ------------------------
const CQO_SIZE: Record<string, number> = { FULL_SIZE: 1, HALF_SIZE: 0.5, SHADOW_ONLY: 0, BLOCK: 0 };
function cqoActionTone(a?: string | null): string {
  if (a === "FULL_SIZE") return "b-profit";
  if (a === "HALF_SIZE") return "b-warn";
  if (a === "SHADOW_ONLY") return "b-shadow";
  if (a === "BLOCK") return "b-danger";
  return "b-muted";
}
function cqoActionLabel(a?: string | null): string {
  if (!a) return "—";
  return a.replace("_SIZE", "").replace("_ONLY", ""); // FULL / HALF / SHADOW / BLOCK
}
function pfShort(v?: number | null): string { return v == null ? "—" : v.toFixed(2); }

function CryptoQualityOverlayCard() {
  const q = useCryptoOverlayReport();
  const d = q.data;
  if (q.isLoading) return <SkeletonList n={1} h={64} />;
  if (!d) return null;
  if (!d.available) {
    return (
      <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="crypto-quality-overlay">
        <div className="flex items-center justify-between">
          <span className="label">Crypto Quality Overlay</span>
          <Badge tone="b-muted">n/a</Badge>
        </div>
        <div className="text-[11px] text-faint mt-1">{d.reason ?? "overlay not refreshed yet — run crypto-overlay-report on the desk"}</div>
      </div>
    );
  }
  const mix = d.action_mix ?? {};
  const cf = d.counterfactual ?? {};
  const cfAll = cf.all;
  const sessions = d.active_session_cooldowns ?? [];
  const symbols = d.active_symbol_cooldowns ?? [];
  const worst = d.worst_symbols ?? [];
  const reasons = d.top_reasons ?? [];
  const windows: { key: "d2" | "d7" | "d14" | "all"; label: string }[] = [
    { key: "d2", label: "48h" }, { key: "d7", label: "7d" }, { key: "d14", label: "14d" }, { key: "all", label: "all" },
  ];
  const cols = "0.6fr 1fr 1.1fr 0.9fr 0.7fr";
  return (
    <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="crypto-quality-overlay">
      <div className="flex items-center justify-between">
        <span className="label">Crypto Quality Overlay</span>
        <Badge tone="b-warn">read-only · live locked</Badge>
      </div>
      <div className="text-[10.5px] text-faint mt-1">
        Soft PAPER sizing/routing breaker — only ever downgrades. Never triggers a trade or config change.
      </div>

      {/* Decision mix */}
      <div className="flex gap-2 mt-2 flex-wrap">
        <Badge tone="b-profit">FULL {mix.FULL_SIZE ?? 0}</Badge>
        <Badge tone="b-warn">HALF {mix.HALF_SIZE ?? 0}</Badge>
        <Badge tone="b-shadow">SHADOW {mix.SHADOW_ONLY ?? 0}</Badge>
        <Badge tone="b-danger">BLOCK {mix.BLOCK ?? 0}</Badge>
      </div>

      {/* Why reduced / shadowed */}
      {reasons.length > 0 && (
        <div className="mt-3">
          <div className="label mb-1">Why reduced / shadowed</div>
          <div className="grid grid-cols-1 gap-1">
            {reasons.slice(0, 6).map((r, i) => (
              <div key={i} className="flex items-center justify-between text-[11px]">
                <span className="truncate text-muted">{r.reason.replace(/_/g, " ")}</span>
                <span className="tnum text-faint ml-2">{r.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Counterfactual — avoided loss vs missed profit */}
      {cfAll && (
        <div className="mt-3">
          <div className="label mb-1">Avoided loss vs missed profit (counterfactual)</div>
          <div className="grid grid-cols-2 gap-2 mb-1.5">
            <KV k="Avoided loss (all)" v={fmtUsd(cfAll.avoided_loss_usd)} tone="text-profit" />
            <KV k="Missed profit (all)" v={fmtUsd(-Math.abs(cfAll.missed_profit_usd))} tone="text-danger" />
          </div>
          <div className="scroll-x">
            <div className="min-w-[300px]">
              <div className="grid gap-1 text-[10px] text-faint pb-0.5 hairline" style={{ gridTemplateColumns: cols }}>
                <div>win</div><div className="text-right">net Δ$</div><div className="text-right">PF b→o</div><div className="text-right">runners</div><div className="text-right">trade Δ</div>
              </div>
              {windows.map((w) => {
                const s = cf[w.key];
                if (!s) return null;
                return (
                  <div key={w.key} className="grid gap-1 text-[11px] py-0.5" style={{ gridTemplateColumns: cols }}>
                    <div className="text-muted">{w.label}</div>
                    <div className={`text-right tnum ${s.net_overlay_delta_usd >= 0 ? "text-profit" : "text-danger"}`}>{fmtUsd(s.net_overlay_delta_usd)}</div>
                    <div className="text-right tnum">{pfShort(s.baseline_pf)}→<span className={s.overlay_pf != null && s.baseline_pf != null && s.overlay_pf >= s.baseline_pf ? "text-profit" : ""}>{pfShort(s.overlay_pf)}</span></div>
                    <div className={`text-right tnum ${s.missed_tp3_runners > 0 ? "text-danger" : "text-faint"}`}>{s.missed_tp3_runners}/{s.total_tp3_runners}</div>
                    <div className="text-right tnum text-faint">{s.trade_count_delta}</div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="text-[10px] text-faint mt-1">runners = missed TP3 runners (0 = runner-safe) · net Δ$ = overlay − baseline paper USD · PF b→o = profit factor base→overlay</div>
        </div>
      )}

      {/* Current weak sessions */}
      {sessions.length > 0 && (
        <div className="mt-3">
          <div className="label mb-1">Current weak sessions ({sessions.length})</div>
          {sessions.slice(0, 6).map((c, i) => (
            <div key={i} className="flex items-center justify-between text-[11px] py-0.5">
              <span className="truncate">{(c.mode ?? "—")}{c.session_bucket ? ` · ${c.session_bucket}` : ""} <span className="text-faint">({(c.reason ?? "").replace(/_/g, " ")})</span></span>
              <span className="tnum text-danger ml-2">{c.recent_net_pnl_usd != null ? fmtUsd(c.recent_net_pnl_usd) : ""}</span>
            </div>
          ))}
        </div>
      )}

      {/* Worst current symbols */}
      {worst.length > 0 && (
        <div className="mt-3">
          <div className="label mb-1">Worst current symbols ({symbols.length} on cooldown)</div>
          {worst.slice(0, 8).map((c, i) => (
            <div key={i} className="flex items-center justify-between text-[11px] py-0.5">
              <span className="truncate">{c.symbol} <span className="text-faint">{c.mode}</span></span>
              <span className="flex items-center gap-2 tnum">
                <span className="text-faint">{c.recent_original_stop_count ?? 0} stops</span>
                <span className={c.recent_net_pnl_usd != null && c.recent_net_pnl_usd < 0 ? "text-danger" : "text-faint"}>{c.recent_net_pnl_usd != null ? fmtUsd(c.recent_net_pnl_usd) : "—"}</span>
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="text-[10px] text-faint mt-2">
        {d.overlay_version}{d.generated_at ? ` · generated ${new Date(d.generated_at).toLocaleString()}` : ""}
      </div>
    </div>
  );
}

// Per-signal overlay diagnostic (read-only). Prefers the authoritative decisions-table row from
// /api/crypto-overlay/signal/{id}; falls back to the cqo_* fields carried on the signal payload.
function CryptoOverlaySignalPanel({ signal }: { signal: Signal }) {
  const q = useCryptoOverlaySignal(signal.signal_id ?? null);
  const d = q.data;
  const live = d?.available ? d : null;
  const action = live ? live.quality_action : signal.cqo_quality_action;
  const would = live ? live.would_have_been_action_without_overlay : signal.cqo_would_have_been_action_without_overlay;
  const verdict = live ? live.crypto_quality_verdict : signal.cqo_crypto_quality_verdict;
  const score = live ? live.crypto_quality_score : signal.cqo_crypto_quality_score;
  const reasons = (live ? live.quality_reasons : signal.cqo_reasons) ?? [];
  const btc = live ? live.btc_regime_state : signal.cqo_btc_regime_state;
  const session = live ? live.session_bucket_utc : signal.cqo_session_bucket_utc;
  const sessQual = live ? live.session_quality_state : signal.cqo_session_quality_state;
  const symCd = live ? live.symbol_cooldown_state : signal.cqo_symbol_cooldown_state;
  const modeCd = live ? live.mode_session_cooldown_state : signal.cqo_mode_session_cooldown_state;
  if (!action && !live) return null; // no overlay decision for this signal — render nothing
  const changedAction = live?.overlay_changed_action ?? (action != null && would != null && action !== would);
  const changedSize = live?.overlay_changed_size
    ?? (action != null && would != null && CQO_SIZE[action] !== CQO_SIZE[would]);
  return (
    <div className="glass p-4 mt-3" data-testid="cqo-signal-panel">
      <div className="flex items-center justify-between mb-2.5">
        <div className="label">Crypto Quality Overlay</div>
        <Badge tone="b-warn">read-only</Badge>
      </div>
      <div className="flex flex-wrap gap-1.5 mb-2.5">
        <Badge tone={cqoActionTone(action)}>{cqoActionLabel(action)}{score != null ? ` · ${Math.round(score)}` : ""}</Badge>
        {verdict && <Badge tone="b-muted">{String(verdict).replace(/_/g, " ").toLowerCase()}</Badge>}
        {changedSize
          ? <Badge tone="b-warn">size cut — was {cqoActionLabel(would)}</Badge>
          : changedAction
            ? <Badge tone="b-accent">action changed — was {cqoActionLabel(would)}</Badge>
            : <Badge tone="b-profit">no change — kept {cqoActionLabel(would ?? action)}</Badge>}
      </div>
      <Analysis k="BTC regime" v={cap(btc)} ok={!/down|risk_off/.test(String(btc ?? ""))} />
      <Analysis k="Session bucket" v={`${session ?? "—"}${sessQual ? ` · ${sessQual}` : ""}`} ok={sessQual !== "weak"} />
      <Analysis k="Symbol cooldown" v={cap(symCd)} ok={symCd !== "on_cooldown"} />
      <Analysis k="Mode/session cooldown" v={cap(modeCd)} ok={modeCd !== "on_cooldown"} />
      {reasons.length > 0 && (
        <div className="text-[11px] text-faint mt-2 leading-relaxed">{reasons.map((r) => r.replace(/_/g, " ")).join(" · ")}</div>
      )}
      <div className="text-[10px] text-faint mt-2">Only ever downgrades — never triggers a trade or size-up. Signal tier / score / TP-SL untouched.</div>
    </div>
  );
}

export function System({ onPause }: { onPause: () => void }) {
  const q = useHealth();
  const cmds = useCommands(12);
  const [sanity, setSanity] = useState<{ ok: boolean; passed: number; total: number; checks: { name: string; ok: boolean; detail: string }[] } | null>(null);
  const [sanityBusy, setSanityBusy] = useState(false);
  const [note, setNote] = useState("");
  const [noteMsg, setNoteMsg] = useState("");

  async function runSanity() {
    setSanityBusy(true); haptic("medium");
    try { setSanity(await api.sanityCheck()); hapticNotify("success"); }
    catch { hapticNotify("error"); }
    finally { setSanityBusy(false); }
  }
  async function saveNote() {
    const t = note.trim(); if (!t) return;
    haptic();
    const r = await api.addNote(t);
    if (r?.status === "applied") { setNote(""); setNoteMsg("Note saved"); queryClient.invalidateQueries({ queryKey: ["commands"] }); }
    else setNoteMsg(`Failed: ${r?.error ?? "error"}`);
    setTimeout(() => setNoteMsg(""), 2500);
  }

  const h = q.data as any;
  const served = h?.ui_build_id as string | undefined;
  const fresh = !served || served === __BUILD_ID__;
  return (
    <Screen>
      <H title="System" sub="desk health console" />
      {/* PART 0 — build stamp: prove the live UI bundle is fresh (no stale frontend) */}
      <div className="glass-soft p-3 mb-3 text-[12px]" data-testid="build-stamp">
        <div className="flex items-center justify-between">
          <span className="label">Build</span>
          <Badge tone={fresh ? "b-profit" : "b-danger"}>{fresh ? "fresh" : "STALE UI"}</Badge>
        </div>
        <div className="grid grid-cols-2 gap-1.5 mt-2">
          <KV k="UI build" v={<span data-testid="ui-build-id">{__BUILD_ID__}</span>} />
          <KV k="UI served (backend)" v={served ?? "—"} />
          <KV k="Built" v={new Date(__BUILD_TIME__).toLocaleString()} />
          <KV k="Backend up" v={h?.backend_start_time ? rel(h.backend_start_time) : "—"} />
          <KV k="Keeper restart" v={h?.keeper_last_restart_reason ? `${h.keeper_last_restart_reason}${h.keeper_last_restart_at ? " · " + rel(h.keeper_last_restart_at) : ""}` : "—"} />
        </div>
        <div className="text-[11px] mt-2" data-testid="live-lock">
          <Badge tone={h?.live_locked !== false ? "b-warn" : "b-danger"}>
            {h?.live_locked !== false ? "PAPER · LIVE LOCKED" : "⚠ LIVE UNLOCKED"}
          </Badge>
          {!fresh && <span className="text-danger ml-2">served bundle ≠ this build — hard-refresh / redeploy</span>}
        </div>
      </div>
      {/* NEXT STEP — paper-shadow A/B (old paper vs new-logic shadow) */}
      <ShadowAB />
      {/* News source health — read-only diagnostics (live locked) */}
      <NewsSourceHealthCard />
      {/* News entity resolver health — trusted-symbol freshness (read-only, live locked) */}
      <NewsEntityHealthCard />
      {/* News catalysts / risk-only warnings — read-only, live locked */}
      <NewsCatalystsCard />
      {/* Crypto Quality Overlay — read-only diagnostics (soft PAPER sizing/routing breaker) */}
      <CryptoQualityOverlayCard />
      {q.isLoading && <SkeletonList n={4} h={64} />}
      {q.data?.schema_ok === false && (
        <div className="glass p-3.5 mb-2.5" style={{ borderColor: "rgba(255,93,108,0.4)" }}>
          <div className="text-danger text-[13px] font-medium">Trading DB problem</div>
          <div className="text-[12px] text-faint mt-1">{q.data.schema_error}</div>
        </div>
      )}
      {(q.data?.components ?? []).map((c, i) => (
        <div key={i} className="glass p-3.5 mb-2.5 flex items-center justify-between animate-rise">
          <div className="flex items-center gap-2.5">
            <StatusDot ok={c.ok} />
            <div>
              <div className="text-[14px] font-medium">{c.name}</div>
              <div className="text-[11px] text-faint">{c.detail}</div>
            </div>
          </div>
          <Badge tone={c.ok ? "b-profit" : "b-warn"}>{c.ok ? "OK" : "CHECK"}</Badge>
        </div>
      ))}

      <div className="label mt-3 mb-2">Errors (24h)</div>
      <div className="glass p-3.5">
        {(q.data?.errors ?? []).length === 0 && <div className="text-faint text-[12px]">No errors. All clear.</div>}
        {(q.data?.errors ?? []).map((e, i) => (
          <div key={i} className="flex justify-between items-center py-1.5 hairline last:border-0 text-[12px]">
            <span className="text-warn"><i className="ti ti-alert-triangle mr-1.5" />{e.type}</span>
            <span className="tnum">{e.count}</span>
          </div>
        ))}
      </div>

      {/* sanity check */}
      <button className="btn w-full mt-3" onClick={runSanity} disabled={sanityBusy}>
        <i className="ti ti-checkup-list mr-1.5" />{sanityBusy ? "Running…" : "Run Sanity Check"}
      </button>
      {sanity && (
        <div className="glass p-3.5 mt-2">
          <div className="flex items-center justify-between mb-1.5">
            <div className="label">Sanity check</div>
            <Badge tone={sanity.ok ? "b-profit" : "b-warn"}>{sanity.passed}/{sanity.total} ok</Badge>
          </div>
          {sanity.checks.map((c, i) => (
            <div key={i} className="flex justify-between items-center py-1 text-[12px]">
              <span className="flex items-center gap-1.5">
                <i className={`ti ${c.ok ? "ti-check text-profit" : "ti-alert-triangle text-warn"} text-[13px]`} />{c.name}
              </span>
              <span className="text-faint truncate ml-2">{c.detail}</span>
            </div>
          ))}
        </div>
      )}

      {/* recent commands */}
      <div className="label mt-4 mb-2">Recent commands</div>
      <div className="glass p-3.5">
        {(cmds.data?.commands ?? []).length === 0 && <div className="text-faint text-[12px]">No commands yet.</div>}
        {(cmds.data?.commands ?? []).slice(0, 10).map((c) => (
          <div key={c.command_id} className="flex justify-between items-center py-1.5 hairline last:border-0 text-[12px]">
            <span className="truncate text-muted">{c.type}</span>
            <span className="flex items-center gap-2">
              <Badge tone={c.status === "applied" ? "b-profit" : c.status === "rejected" || c.status === "failed" ? "b-danger" : "b-muted"}>{c.status}</Badge>
              <span className="text-faint tnum">{rel(c.created_at)}</span>
            </span>
          </div>
        ))}
      </div>

      {/* quick note */}
      <div className="label mt-4 mb-2">Add note</div>
      <div className="flex gap-2">
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="log an observation…"
          className="flex-1 bg-white/5 border border-line rounded-xl px-3 py-2.5 text-[13px]" />
        <button className="btn btn-accent" onClick={saveNote} disabled={!note.trim()}>Save</button>
      </div>
      {noteMsg && <div className="text-[11px] text-faint mt-1.5">{noteMsg}</div>}

      <button className="btn btn-danger w-full mt-4" onClick={() => { haptic("heavy"); onPause(); }}><i className="ti ti-player-pause mr-1.5" />Emergency Pause</button>
      <div className="text-[11px] text-faint mt-2 text-center">No destructive restart in v1. Pause writes a command + audit row — no process is killed.</div>
    </Screen>
  );
}

// ---- layout helpers --------------------------------------------------------
function Screen({ children }: { children: ReactNode }) {
  // Bottom padding clears BOTH the bottom nav (~safe-b + 60px) AND the floating
  // "+ Manual" FAB (sits at safe-b + 84px, ~48px tall → top ≈ safe-b + 132px), so the
  // last row can always scroll above the FAB on long screens (Home/Signals/Risk/…).
  return <div className="px-4 pt-3" style={{ paddingBottom: "calc(var(--safe-b) + 150px)" }}>{children}</div>;
}
function H({ title, sub }: { title: string; sub?: string }) {
  return <div className="mb-3"><div className="text-[20px] font-semibold tracking-tight">{title}</div>{sub && <div className="text-[12px] text-faint">{sub}</div>}</div>;
}
function Seg({ options, value, onChange, cap }: { options: string[]; value: string; onChange: (v: string) => void; cap?: boolean }) {
  return (
    <div className="seg scroll-x">
      {options.map((o) => (
        <button key={o} data-on={value === o} onClick={() => { haptic("light"); onChange(o); }} className={cap ? "capitalize" : ""}>{o}</button>
      ))}
    </div>
  );
}
