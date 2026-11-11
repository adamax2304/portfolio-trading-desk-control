// TanStack Query data layer — typed hooks with polling. Backend is the source of truth.
import { QueryClient, useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 8_000, retry: 1, refetchOnWindowFocus: true } },
});

const POLL = 15_000; // 15s polling for MVP (SSE/WebSocket is a future upgrade)

export const useStatus = () => useQuery({ queryKey: ["status"], queryFn: api.status, refetchInterval: POLL });
export const useSignals = () => useQuery({ queryKey: ["signals"], queryFn: api.signals, refetchInterval: POLL });
export const useTrades = (bucket: string) =>
  useQuery({ queryKey: ["trades", bucket], queryFn: () => api.trades(bucket), refetchInterval: POLL });
export const useDashboard = () =>
  useQuery({ queryKey: ["dashboard"], queryFn: api.dashboardSummary, refetchInterval: POLL });
export const usePaperFeatures = () =>
  useQuery({ queryKey: ["paperFeatures"], queryFn: api.paperFeatures, refetchInterval: POLL });
export const usePortfolio = () =>
  useQuery({ queryKey: ["portfolio"], queryFn: api.portfolio, refetchInterval: POLL });
export const usePortfolioCompare = () =>
  useQuery({ queryKey: ["portfolioCompare"], queryFn: api.portfolioCompare, refetchInterval: POLL });
export const usePortfolioByAsset = () =>
  useQuery({ queryKey: ["portfolioByAsset"], queryFn: api.portfolioByAsset, refetchInterval: POLL });
export const useChartEvents = (signalId: string | null) =>
  useQuery({ queryKey: ["chartEvents", signalId], queryFn: () => api.chartEvents(signalId as string),
             enabled: !!signalId });
export const useLifecycle = (signalId: string | null) =>
  useQuery({ queryKey: ["lifecycle", signalId], queryFn: () => api.lifecycle(signalId as string),
             enabled: !!signalId });
export const useMarketDashboard = () =>
  useQuery({ queryKey: ["marketDashboard"], queryFn: api.marketDashboard, refetchInterval: POLL });
export const useClosed = (book: string, hours?: number) =>
  useQuery({ queryKey: ["closed", book, hours ?? 0], queryFn: () => api.closed(book, hours), refetchInterval: POLL });
export const useClosedAnalytics = (book: string, hours?: number) =>
  useQuery({ queryKey: ["closedAnalytics", book, hours ?? 0], queryFn: () => api.closedAnalytics(book, hours), refetchInterval: POLL });
export const useNearWinners = (book = "operator", hours = 168) =>
  useQuery({ queryKey: ["nearWinners", book, hours], queryFn: () => api.nearWinners(book, hours), refetchInterval: 30_000 });
export const useChart = (symbol: string, tf: string) =>
  useQuery({ queryKey: ["chart", symbol, tf], queryFn: () => api.chart(symbol, tf) });
export const useMarket = () => useQuery({ queryKey: ["market"], queryFn: api.market, refetchInterval: 30_000 });
export const useRisk = () => useQuery({ queryKey: ["risk"], queryFn: api.risk, refetchInterval: POLL });
export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: POLL });
export const useNewsSourceHealth = () =>
  useQuery({ queryKey: ["newsSourceHealth"], queryFn: api.newsSourceHealth, refetchInterval: 120_000 });
export const useNewsEntityHealth = () =>
  useQuery({ queryKey: ["newsEntityHealth"], queryFn: api.newsEntityHealth, refetchInterval: 120_000 });
export const useNewsCatalysts = () =>
  useQuery({ queryKey: ["newsCatalysts"], queryFn: api.newsCatalysts, refetchInterval: 120_000 });
export const useCryptoOverlayReport = () =>
  useQuery({ queryKey: ["cryptoOverlayReport"], queryFn: api.cryptoOverlayReport, refetchInterval: 60_000 });
export const useCryptoOverlaySignal = (signalId: string | null) =>
  useQuery({ queryKey: ["cryptoOverlaySignal", signalId], queryFn: () => api.cryptoOverlaySignal(signalId as string),
             enabled: !!signalId });
export const useCommands = (n = 30) =>
  useQuery({ queryKey: ["commands", n], queryFn: () => api.commandsRecent(n), refetchInterval: POLL });
export const useAudit = (n = 30) =>
  useQuery({ queryKey: ["audit", n], queryFn: () => api.auditRecent(n), refetchInterval: POLL });
export const useSystemErrors = () =>
  useQuery({ queryKey: ["sysErrors"], queryFn: api.systemErrors, refetchInterval: POLL });
export const useStocksPositionSummary = () =>
  useQuery({ queryKey: ["stocksPositionSummary"], queryFn: api.stocksPositionSummary, refetchInterval: 30_000 });
export const useStocksPositionCandidates = (n = 25) =>
  useQuery({ queryKey: ["stocksPositionCandidates", n], queryFn: () => api.stocksPositionCandidates(n), refetchInterval: 30_000 });
