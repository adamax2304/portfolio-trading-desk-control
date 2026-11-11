// Telegram WebApp bootstrap + typed, authenticated API client.
// The raw initData string is sent in a header and verified server-side; initDataUnsafe is
// never trusted for authorization.
import type {
  AuditRow, ChartData, CommandRow, DashboardSummary, Health, ManualOrder, Market,
  ChartEvents, NearWinners, PaperFeaturesSummary, PortfolioSummary, PortfolioCompare, PortfolioByAsset, RiskConfig, SanityReport, Signal, Status, SystemErrors,
  TradeLifecycle, MarketDashboard, StocksPositionSummary, StocksPositionCandidates, NewsSourceHealth,
  NewsEntityHealth, NewsCatalysts, CryptoOverlayReport, CryptoOverlaySignal,
  TradePnlAnalytics,
} from "./types";

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "";
export const tg = (window as any).Telegram?.WebApp;

export function initTelegram() {
  try {
    tg?.ready(); tg?.expand();
    tg?.setHeaderColor?.("#05070D"); tg?.setBackgroundColor?.("#05070D");
  } catch { /* running outside Telegram (dev) */ }
}

export function haptic(kind: "light" | "medium" | "heavy" | "rigid" | "soft" = "light") {
  try { tg?.HapticFeedback?.impactOccurred?.(kind); } catch { /* no-op */ }
}
export function hapticNotify(kind: "error" | "success" | "warning" = "success") {
  try { tg?.HapticFeedback?.notificationOccurred?.(kind); } catch { /* no-op */ }
}

function headers(): HeadersInit {
  return { "Content-Type": "application/json", "X-Telegram-Init-Data": tg?.initData ?? "" };
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { headers: headers() });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json() as Promise<T>;
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  return r.json() as Promise<T>;
}

export const api = {
  status: () => get<Status>("/api/status"),
  signals: () => get<{ signals: Signal[] }>("/api/signals"),
  signal: (id: string) => get<Signal>(`/api/signals/${id}`),
  trades: (bucket: string) => get<{ bucket: string; trades: Signal[] }>(`/api/trades/${bucket}`),
  dashboardSummary: () => get<DashboardSummary>("/api/dashboard/summary"),
  paperFeatures: () => get<PaperFeaturesSummary>("/api/paper-features"),
  portfolio: () => get<PortfolioSummary>("/api/portfolio"),
  portfolioCompare: () => get<PortfolioCompare>("/api/portfolio/compare"),
  portfolioByAsset: () => get<PortfolioByAsset>("/api/portfolio/by-asset"),
  chartEvents: (signalId: string) => get<ChartEvents>(`/api/trades/${encodeURIComponent(signalId)}/chart-events`),
  lifecycle: (signalId: string) => get<TradeLifecycle>(`/api/trades/${encodeURIComponent(signalId)}/lifecycle`),
  marketDashboard: () => get<MarketDashboard>("/api/market-dashboard"),
  paperShadowSummary: () => get<any>("/api/paper-shadow/summary"),
  paperShadowTrades: (n = 60) => get<any>(`/api/paper-shadow/trades?limit=${n}`),
  paperShadowForward: () => get<any>("/api/paper-shadow/forward"),
  paperShadowFees: () => get<any>("/api/paper-shadow/fees"),
  paperShadowBreakdown: () => get<any>("/api/paper-shadow/breakdown"),
  newsSourceHealth: () => get<NewsSourceHealth>("/api/news-source-health"),
  newsEntityHealth: () => get<NewsEntityHealth>("/api/news-entity-health"),
  newsCatalysts: () => get<NewsCatalysts>("/api/news-catalysts"),
  // Crypto Quality Overlay — READ-ONLY diagnostics (soft PAPER sizing/routing breaker read-model).
  cryptoOverlayReport: () => get<CryptoOverlayReport>("/api/crypto-overlay/report"),
  cryptoOverlaySignal: (id: string) =>
    get<CryptoOverlaySignal>(`/api/crypto-overlay/signal/${encodeURIComponent(id)}`),
  // Stocks Position Framework — SHADOW ONLY read-model (never actionable/live).
  stocksPositionSummary: () => get<StocksPositionSummary>("/api/stocks-position/summary"),
  stocksPositionCandidates: (n = 25) =>
    get<StocksPositionCandidates>(`/api/stocks-position/candidates?limit=${n}`),
  closed: (book: string, hours?: number) =>
    get<{ book: string; hours: number | null; trades: Signal[] }>(
      `/api/closed/${book}${hours ? `?hours=${hours}` : ""}`),
  closedAnalytics: (book: string, hours?: number) =>
    get<TradePnlAnalytics>(
      `/api/closed/${book}/analytics${hours ? `?hours=${hours}` : ""}`),
  nearWinners: (book = "operator", hours = 168) =>
    get<NearWinners>(`/api/near-winners?book=${book}&hours=${hours}`),
  chart: (symbol: string, tf = "5m") => get<ChartData>(`/api/chart/${encodeURIComponent(symbol)}?tf=${tf}`),
  market: () => get<Market>("/api/market/summary"),
  risk: () => get<RiskConfig>("/api/risk/config"),
  health: () => get<Health>("/api/system/health"),
  systemErrors: () => get<SystemErrors>("/api/system/errors"),
  sanityCheck: () => get<SanityReport>("/api/system/sanity-check"),
  commandsRecent: (n = 30) => get<{ commands: CommandRow[] }>(`/api/commands/recent?limit=${n}`),
  auditRecent: (n = 30) => get<{ audit: AuditRow[] }>(`/api/audit/recent?limit=${n}`),
  ordersRecent: (n = 50) => get<{ orders: ManualOrder[] }>(`/api/orders/recent?limit=${n}`),
  command: (type: string, payload: Record<string, unknown>, confirm_token = "confirm") =>
    post<any>("/api/command", { type, payload, confirm_token }),
  // notes / acks are always-safe (no confirm token needed server-side)
  addNote: (text: string, ref?: string) => post<any>("/api/command", { type: "ADD_TRADE_NOTE", payload: { text, ref } }),
  ackAlert: (notification_id: number) => post<any>("/api/command", { type: "ACKNOWLEDGE_ALERT", payload: { notification_id } }),
  runSanity: () => post<any>("/api/command", { type: "RUN_SANITY_CHECK", payload: {} }),
  emergencyPause: () => post<any>("/api/emergency-pause", {}),
};
