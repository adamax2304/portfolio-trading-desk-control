export type ActStatus = "actionable" | "shadow" | "late" | "blocked" | "closed";

export type Actionability = {
  actionable: boolean;
  status: ActStatus;
  blocked_reason: string | null;
  reasons: string[];
  badges: string[];
  freshness: { label: string; age_min: number | null; ok: boolean };
};

// Stocks Position Framework — SHADOW ONLY read-model (no live / no Telegram / no actionability).
export type StocksPositionCandidate = {
  symbol: string;
  setup_variant: string | null;
  score: number | null;
  data_confidence: number | null;
  sector: string | null;
  sector_etf: string | null;
  entry_price: number | null;
  entry_low: number | null;
  entry_high: number | null;
  stop_price: number | null;
  stop_reason: string | null;
  risk_usd: number | null;
  tp1: number | null;
  tp1_r: number | null;
  tp2: number | null;
  tp2_r: number | null;
  rs_spy: number | null;
  near_high_pct: number | null;
  volume_ratio: number | null;
  market_regime: string | null;
  earnings_risk: string | null;
  created_at: string | null;
  status: string | null;
  reasons: string[];
  thesis: string | null;
  counter_thesis: string | null;
  review_verdict?: string | null;
  review_confidence?: number | null;
  reviewed_at?: string | null;
};

export type StocksPositionSummary = {
  shadow_only: boolean;
  live_locked: boolean;
  actionable: boolean;
  playbook: string;
  note: string;
  available: boolean;
  reason?: string;
  latest_scan: string | null;
  open_candidates: number;
  top: StocksPositionCandidate[];
  outcomes_available: boolean;
};

export type StocksPositionCandidates = {
  shadow_only: boolean;
  live_locked: boolean;
  actionable: boolean;
  playbook: string;
  note: string;
  available: boolean;
  reason?: string;
  latest_scan: string | null;
  count: number;
  candidates: StocksPositionCandidate[];
};

export type Signal = {
  signal_id: string;
  symbol: string;
  asset_class: "crypto" | "stocks" | string;
  mode: string;
  tier: string;
  score: number;
  direction: string;
  status: string;
  created_at: string;
  entry_low?: number; entry_high?: number; entry_trigger?: number;
  stop_loss?: number; invalidation?: number;
  tp1?: number; tp2?: number; tp3?: number;
  expected_rr_tp1?: number;
  setup_type?: string;
  news_supported?: number;
  funding_context?: string; oi_context?: string;
  narrative?: string; thesis?: string;
  entry_triggered_at?: string;
  final_outcome?: string; final_r?: number; mfe_r?: number; mae_r?: number;
  // Authoritative execution state from crypto-ai-desk.paper_execution_outcomes.
  // It takes precedence over legacy signal_outcomes.final_outcome for Paper trades.
  paper_lifecycle_state?: string; paper_execution_outcome?: string;
  paper_close_reason?: string; paper_exit_at?: string;
  concentration_status?: string; concentration_reason?: string; size_weight?: number;
  // Add-only risk-guard diagnostics (read-only; all optional). Producer:
  // crypto-ai-desk paper-entry payload. Display only — never gate commands.
  circuit_breaker_state?: string; day_realized_r?: number; stops_today?: number;
  consecutive_stops?: number; crypto_long_streak_count?: number;
  btc_intraday_risk_off?: boolean; regime_context?: string;
  lifecycle_label?: string; held_hours?: number;
  next_day_revalidation_required?: boolean; carryover_warning?: boolean;
  would_bind_sector_cap?: string; would_sector_rank?: number;
  profit_protection_hint?: string; catalyst_integrity_status?: string;
  direct_news_items_checked?: boolean; catalyst_mapping_confidence?: string;
  // Shadow Intelligence Layer (read-only diagnostic; all optional)
  intelligence_layer_status?: string; squeeze_phase?: string;
  squeeze_phase_confidence?: string; no_chase_warning?: boolean;
  distribution_risk_score?: number; derivatives_context?: string;
  funding_turning_down?: boolean; thesis_summary_compact?: string;
  thesis_invalidation?: string; onchain_risk_status?: string;
  timeline_confidence?: string; timeline_recent_outcome_bias?: string;
  // Crypto Quality Overlay per-signal diagnostic (read-only; all optional). Carried on the
  // paper_entry payload; the authoritative row lives in crypto_quality_overlay_decisions.
  cqo_quality_action?: string; cqo_crypto_quality_verdict?: string; cqo_crypto_quality_score?: number;
  cqo_btc_regime_state?: string; cqo_session_bucket_utc?: string; cqo_session_quality_state?: string;
  cqo_symbol_cooldown_state?: string; cqo_mode_session_cooldown_state?: string;
  cqo_would_have_been_action_without_overlay?: string; cqo_reasons?: string[];
  // Display-status semantics (read-only; all optional). Lifecycle-aware labels so
  // the UI can show OPEN/WAITING/ENTERED-UNRESOLVED/REVIEW-SHADOW/NO-ENTRY instead
  // of a bare `expired` or context-free `+0R`. Never affects actionability/commands.
  display_status?: string; display_group?: string; display_reason?: string;
  display_r_source?: string; paper_outcome_authoritative?: boolean;
  operator_label?: string; entry_touched?: boolean;
  is_shadow_or_review?: boolean; is_active_for_operator?: boolean;
  r_display_policy?: string;
  // Canonical book read-model (read-only; from books.py via desk_adapter). Lets the
  // UI separate Operator/Paper/Shadow, show honest close reasons + delivery + dedup.
  telegram_supported?: number; derivatives_supported?: number;
  market_regime?: string; validity_window_hours?: number; expires_at?: string;
  entry_triggered?: number; stop_hit?: number; tp1_hit?: number; tp2_hit?: number; tp3_hit?: number; checked_at?: string;
  entry_alert_status?: string; entry_alert_sent?: boolean; entry_alert_at?: string;
  close_alert_type?: string; close_alert_status?: string; close_alert_sent?: boolean; close_alert_at?: string;
  catalyst_freshness?: string; catalyst_strength?: string; catalyst_headline?: string;
  catalyst_symbol_mapping?: string; catalyst_label_computed_at?: string;
  catalyst_supported?: "supported" | "unsupported" | "unknown";
  // enriched-only (closed_trades_book / near_winners output)
  book?: "operator" | "paper" | "shadow";
  book_delivered?: boolean; delivery_state?: string;
  outcome_class?: string; close_reason?: string; close_explanation?: string;
  close_time?: string;
  // Paper execution accounting (Model F) — authoritative paper R (USD net is the authoritative
  // PnL). legacy_touch_r = old touch-based final_r: optimistic, NOT PnL, never a headline result.
  legacy_touch_r?: number | null; paper_execution_r?: number | null; risk_model?: string;
  protection_armed?: boolean; protection_level_r?: number | null;
  lock_armed?: boolean; lock_level_r?: number | null;
  stop_moved?: boolean; giveback?: boolean; highest_tp_touched?: number;
  original_stop_avoided?: boolean; paper_execution_available?: boolean;
  cohort_warning?: boolean; paper_feature_tags?: string[];
  duplicates_collapsed_count?: number; duplicate_signal_ids?: string[]; economic_trade_key?: string;
  actionability: Actionability;
};

export type BookWindow = {
  // authoritative paper R (Model F); USD net is the authoritative PnL
  paper_execution_r: number; paper_resolved_n: number;
  // LEGACY touch metric (optimistic, NOT PnL) + the touch-vs-paper diagnostic
  legacy_touch_r: number; resolved_n: number;
  touch_minus_paper_r: number;
  giveback_n: number; be_scratch_n: number; protected_n: number;
  original_stops_avoided_n: number; paper_unavailable_n: number;
  win: number; loss: number; flat: number;
  expired_unresolved: number; no_entry: number; needs_review: number; trades_n: number;
};
export type BookBlock = {
  book: string; today: BookWindow; h48: BookWindow; d7: BookWindow;
  open_now: number; waiting_now: number; duplicates_collapsed: number;
};
export type DashboardSummary = {
  headline: {
    today_paper_execution_r: number; h48_paper_execution_r: number; d7_paper_execution_r: number;
    risk_model: string; authoritative_metric?: string;
    today_legacy_touch_r: number; h48_legacy_touch_r: number; today_touch_minus_paper_r?: number;
    today_operator_r: number; h48_operator_r: number; today_paper_unavailable_n: number;
    label: string;
  };
  operator: BookBlock; paper: BookBlock; shadow: BookBlock;
  delivery_gaps: number; generated_at: string;
};
export type NearWinners = { note: string; count: number; items: Signal[] };

export type TradePnlPoint = {
  ts: string; signal_id: string; symbol?: string | null; asset_class?: string | null;
  mode?: string | null; direction?: string | null; outcome_class?: string | null;
  trade_pnl_usd?: number | null; trade_r?: number | null;
  cumulative_usd: number; cumulative_r: number;
};
export type TradeCalendarDay = {
  date: string; trades: number; net_pnl_usd: number; net_r: number;
  wins: number; losses: number; flat: number; missing_usd: number; trade_ids: string[];
};
export type TradePnlAnalytics = {
  available: boolean; book: string; hours?: number | null;
  metric: "usd_net" | "paper_execution_r" | string;
  pnl_usd_available: boolean; trades: number; usd_trades: number; missing_usd_trades: number;
  total_pnl_usd: number; total_r: number; max_drawdown_usd: number; max_drawdown_r: number;
  series: TradePnlPoint[]; days: TradeCalendarDay[]; note?: string;
};

export type PortfolioSummary = {
  available: boolean; reason?: string; fee_profile?: string;
  initial_equity_usdt: number; equity_usdt?: number; risk_per_trade_pct: number;
  net_pnl_usdt_total?: number; return_pct?: number;
  today_net_pnl_usdt?: number; today_net_r?: number;
  d7_net_pnl_usdt?: number; d7_net_r?: number;
  max_drawdown_pct?: number; fees_paid_usdt?: number; trades?: number;
  // PART 1: execution costs kept SEPARATE — exchange fees ≠ slippage ≠ funding.
  exchange_fees_usdt?: number; slippage_usdt?: number;
  funding_usdt?: number; funding_known?: boolean; total_execution_cost_usdt?: number;
  wins?: number; losses?: number; breakeven?: number;
  open_positions?: number; open_risk_usdt?: number; margin_used_usdt?: number;
  avg_leverage?: number; max_leverage?: number; risk_capped_trades?: number;
  fee_profiles_available?: string[]; fee_estimated_any?: boolean;
  note?: string; live_locked: boolean; auto_live_locked: boolean;
};

// PART 3: crypto-only vs stocks-only P&L contribution (separate cost models).
export type PortfolioAssetBook = {
  asset_class: string; trades: number; net_pnl_usdt: number; gross_pnl_usdt: number;
  exchange_fees_usdt: number; slippage_usdt: number; funding_usdt: number;
  total_execution_cost_usdt: number; win_rate: number; fee_profile_used: string;
  cost_model_appropriate: boolean; cost_model_note?: string | null;
};
export type PortfolioByAsset = {
  available: boolean; reason?: string; fee_profile?: string;
  crypto?: PortfolioAssetBook; stocks?: PortfolioAssetBook;
  unknown_asset_trades?: number; note?: string;
  live_locked: boolean; auto_live_locked: boolean;
};

export type PortfolioBookSide = {
  fee_profile: string; equity_usdt?: number; return_pct?: number;
  fees_paid_usdt?: number; max_drawdown_pct?: number; avg_leverage?: number; max_leverage?: number;
};
export type ComparisonIntegrity = {
  comparable: boolean; common_trades: number;
  A: { trades: number; latest_ts?: string | null };
  B: { trades: number; latest_ts?: string | null };
  warnings: string[];
};
export type PortfolioCompare = {
  available: boolean; reason?: string;
  production_tp_unchanged?: boolean; paper_tp?: string; leverage_policy?: string;
  comparison_integrity?: ComparisonIntegrity;
  mechanical_taker?: PortfolioBookSide; structural_maker_first?: PortfolioBookSide;
  delta_return_pct?: number; fees_saved_usdt?: number;
  maker_entries?: number; taker_entries?: number; maker_exits?: number;
  structural_tp_trades?: number; atr_fallback_tp_trades?: number;
  note?: string; live_locked: boolean; auto_live_locked: boolean;
};

export type ChartMarker = {
  marker_type: string; timestamp?: string | null; price?: number | null;
  label: string; status: string; reason?: string;
  r_at_marker?: number | null; pnl_usdt_at_marker?: number | null;
};
export type ChartEvents = {
  available: boolean; signal_id: string; symbol?: string; direction?: string;
  levels: { label: string; price: number; kind: string; r_multiple?: number | null }[];
  markers: ChartMarker[];
  tp_r_exact?: { tp1?: number | null; tp2?: number | null; tp3?: number | null };
  mfe_r?: number | null; mae_r?: number | null; paper_execution_r?: number | null;
  // legacy touch = old final_r / highest-TP-touched: optimistic, NOT PnL (diagnostic only)
  legacy_touch_r?: number | null; stop_current_r?: number | null; close_reason?: string;
  exit_price?: number | null; expiry_close_price?: number | null; expiry_close_price_source?: string | null;
  net_pnl_usdt?: number | null; leverage_used?: number | null;
  position_notional_usdt?: number | null; margin_used_usdt?: number | null; risk_usdt?: number | null;
  tp_quality?: { label: string; volume_profile_supported: string; note: string };
  paper_execution_b?: {
    fee_profile?: string; entry_order_type?: string | null; exit_order_type?: string | null;
    stop_order_type?: string; tp_set_label?: string | null;
    net_pnl_usdt?: number | null; fees_usdt?: number | null; slippage_usdt?: number | null;
    leverage_used?: number | null; position_notional_usdt?: number | null;
    margin_used_usdt?: number | null; risk_usdt?: number | null; paper_execution_r?: number | null;
  } | null;
};

export type LifecycleEvent = {
  event: string; timestamp?: string | null; price?: number | null;
  qty?: number | null; remaining_qty?: number | null; realized_pnl_usdt?: number | null;
  realized_r?: number | null; fees_usdt?: number | null; order_type?: string | null;
  reason?: string; source?: string;
};
export type TradeLifecycle = {
  available: boolean; signal_id: string; reason?: string;
  symbol?: string; direction?: string; asset_class?: string; mode?: string; tier?: string;
  playbook?: string; status?: string;
  regime?: { regime: string; label: string; source: string; confidence: number; reason?: string };
  position?: {
    equity_at_entry_usdt: number; risk_usdt: number; risk_pct: number; notional_usdt: number;
    qty: number; margin_usdt: number; leverage: number; leverage_reason: string;
    liquidation_price?: number | null; liq_distance_pct?: number; stop_distance_pct?: number;
    liquidation_buffer_ok?: boolean; risk_capped?: boolean; fee_profile?: string;
  };
  price_ladder?: {
    entry: number; initial_stop: number; current_stop?: number; current_stop_r?: number | null;
    tps: { label: string; price?: number | null; r?: number | null; pct_closed?: number; pnl_if_filled_usdt?: number | null }[];
    max_loss_at_stop_usdt?: number;
  };
  partials?: { tp: string; price: number; pct: number; r: number; qty_closed: number; pnl_usdt: number; fee_usdt: number }[];
  events?: LifecycleEvent[];
  remaining_qty?: number; realized_pnl_usdt?: number; realized_r?: number; blended_r?: number;
  audit?: { touch_final_r?: number | null; mfe_r?: number | null; mae_r?: number | null; outcome?: string | null; entry_triggered_at?: string | null; note?: string };
  live_locked: boolean; auto_live_locked: boolean;
};

export type MarketNews = { title?: string; asset_or_sector?: string; impact?: string; horizon?: string; confidence?: number; why_it_matters?: string };
export type MarketDashboard = {
  available: boolean; reason?: string; live_locked: boolean; auto_live_locked: boolean;
  timestamp?: string; age_hours?: number | null; stale?: boolean; stale_warning?: boolean;
  generated_by?: string; confidence?: number | null; source_summary?: string;
  crypto_fear_greed?: number | null; crypto_market_mode?: string; stocks_market_mode?: string;
  crypto_main_risk?: string; stocks_main_risk?: string; crypto_regime?: string; stocks_regime?: string;
  today_news?: MarketNews[]; long_term_news?: MarketNews[];
  extras?: { btc_dominance?: number | null; eth_btc?: number | null; vix?: number | null; spy_trend?: string | null; qqq_trend?: string | null };
  note?: string;
};

export type PaperFeature = {
  key: string; label: string; state: string; affects_trades: boolean;
  evidence: string; decision_date: string; mode?: string;
};
export type PaperFeaturesSummary = {
  risk_model: string; live_locked: boolean; auto_live_locked: boolean;
  active: PaperFeature[]; shadow_or_measuring: PaperFeature[];
  archived: PaperFeature[]; dangerous_locked: PaperFeature[];
  counts: { active: number; shadow: number; archived: number; dangerous: number };
  note: string;
};

export type Status = {
  engine_online: boolean; demo_mode: boolean; trading_mode: string;
  auto_live_locked: boolean; live_commands_enabled: boolean;
  last_monitor_tick: string | null; emergency_paused: boolean; badges: string[];
};

export type HealthComponent = { name: string; ok: boolean; detail: string };
export type Health = {
  demo_mode: boolean; components: HealthComponent[]; errors: { type: string; count: number }[];
  schema_ok?: boolean; schema_error?: string | null;
  live_locked?: boolean; auto_live_locked?: boolean; version?: string;
  backend_start_time?: string | null; ui_build_id?: string | null; ui_build_time?: string | null;
};

export type CommandRow = {
  command_id: string; created_at: string; type: string; status: string;
  payload_json?: string | null; result_json?: string | null; error?: string | null;
  applied_at?: string | null; telegram_user_id?: number | null; username?: string | null;
  source?: string | null;
};
export type AuditRow = {
  id: number; ts: string; action_type: string; result?: string | null; error?: string | null;
  old_value?: string | null; new_value?: string | null; username?: string | null; command_id?: string | null;
};
export type ManualOrder = {
  order_id: string; created_at: string; symbol: string; direction: string; mode: string;
  status: string; risk_pct?: number; entry_price?: number; stop?: number; signal_id?: string | null;
};
export type SanityReport = {
  ok: boolean; passed: number; total: number;
  checks: { name: string; ok: boolean; detail: string }[];
};
export type SystemErrors = { errors: { ts: string | null; source: string; type: string; detail: string }[]; count: number };

export type RiskConfig = {
  trading_mode: string; paper_balance: number; live_balance: number;
  risk_per_trade: number; daily_loss_limit: number; weekly_loss_limit: number;
  max_positions: number; max_sector_exposure: number;
  allowed_modes: Record<string, boolean>; symbol_whitelist: string[];
  emergency_paused: boolean; _locked: Record<string, boolean>;
};

export type Market = {
  narratives: { name: string; symbols: string[]; count: number; strength: number }[];
  funding_oi: { symbol: string; funding?: string; oi?: string }[];
};

// News Source Health (read-only diagnostics; live_locked). Mirrors news_source_health.json.
export interface NewsSourceHealthSource {
  source: string; asset_class: string; source_type: string;
  enabled: boolean; primary_source: boolean;
  rows_24h: number; rows_72h: number; rows_total: number;
  symbol_match_rate_24h: number | null; latest_published_at: string | null;
  // CONFIGURED = enabled/known provider not currently ingesting rows (free/fallback), not an alarm.
  stale_status: "OK" | "STALE" | "DEAD" | "CONFIGURED" | "DISABLED"; warnings: string[];
}
export interface NewsSourceHealth {
  available: boolean; live_locked?: boolean; reason?: string; generated_at?: string;
  summary: {
    total_configured?: number; ok?: number; stale?: number; dead?: number;
    configured?: number; disabled?: number; dead_primary?: string[]; unregistered_sources?: number;
  };
  sources: NewsSourceHealthSource[];
}

// News Entity Resolver Health (read-only diagnostics; live_locked). Mirrors news_entity_health.json.
export interface NewsEntityHealthWindow {
  rows?: number; resolved?: number; resolved_pct?: number | null;
  symbol_tagged?: number; unresolved_symbol_tagged?: number;
  unresolved_share?: number; trusted_symbol_tagged?: number;
  preexisting_unverified?: number;
}
export interface NewsEntityHealthExample {
  title?: string; source?: string | null; published_at?: string;
  age_minutes?: number; asset_class?: string | null; detected_symbols_json?: string | null;
}
export interface NewsEntityHealth {
  available: boolean; live_locked?: boolean; reason?: string; generated_at?: string;
  severity?: "OK" | "WARN" | "CRITICAL" | "UNKNOWN" | string;
  severity_reason?: string; trust_layer_present?: boolean;
  resolver_last_run_at?: string | null; resolver_last_run_age_minutes?: number | null;
  resolver_stale?: boolean; max_unresolved_age_minutes?: number | null;
  windows?: { "24h"?: NewsEntityHealthWindow; "72h"?: NewsEntityHealthWindow };
  newest_unresolved_examples?: NewsEntityHealthExample[];
}

// Production News Catalysts / RISK-only warnings (read-only, live_locked). Mirrors
// news_catalysts.json. These effects NEVER change a score/tier, create a buy/sell, or unlock live.
export interface NewsRiskWarning {
  symbol: string; asset_class?: string; event_type: string; effect: string;
  reason?: string; source?: string; published_at?: string;
}
export interface NewsCatalysts {
  available: boolean; live_locked?: boolean; reason?: string; as_of?: string;
  window_hours?: number;
  symbols_requiring_operator_review: string[];
  warnings: NewsRiskWarning[];
  allowed_effects?: string[]; not_allowed?: string[];
  events_summary?: {
    available: boolean; count?: number; deduped_from?: number;
    conflicting_symbols?: string[];
    by_event_type?: Record<string, number>; by_asset_class?: Record<string, number>;
  };
}

// Crypto Quality Overlay (read-only diagnostics; live_locked). Soft PAPER sizing/routing breaker
// read-model — FULL/HALF/SHADOW/BLOCK. Never triggers a trade / config change / live unlock.
export interface CryptoOverlayCooldown {
  mode: string | null; reason: string | null; expires_at: string | null;
  recent_closed_count: number | null; recent_original_stop_count: number | null;
  recent_net_pnl_usd: number | null; recent_profit_factor: number | null;
  session_bucket?: string | null;   // session cooldowns (current weak sessions)
  symbol?: string | null;           // symbol cooldowns / worst symbols
}
export interface CryptoOverlayCFWindow {
  evaluated: number; with_usd: number;
  baseline_pnl_usd: number; overlay_pnl_usd: number; net_overlay_delta_usd: number;
  avoided_loss_usd: number; missed_profit_usd: number;
  baseline_pf: number | null; overlay_pf: number | null;
  baseline_original_stops: number; overlay_original_stops_kept: number; original_stop_reduction: number;
  missed_tp3_runners: number; total_tp3_runners: number;
  missed_winners: number; kept_full_size: number; trade_count_delta: number;
}
export interface CryptoOverlayReport {
  read_only: boolean; live_locked: boolean; actionable: boolean;
  overlay_version: string; note: string;
  available: boolean; reason?: string; generated_at: string;
  action_mix: Record<string, number>;               // FULL_SIZE/HALF_SIZE/SHADOW_ONLY/BLOCK
  top_reasons: { reason: string; count: number }[];
  active_session_cooldowns: CryptoOverlayCooldown[]; // current weak sessions
  active_symbol_cooldowns: CryptoOverlayCooldown[];
  worst_symbols: CryptoOverlayCooldown[];
  counterfactual: Partial<Record<"d2" | "d7" | "d14" | "all", CryptoOverlayCFWindow>>;
}
export interface CryptoOverlaySignal {
  read_only: boolean; live_locked: boolean; actionable: boolean;
  overlay_version: string; note: string;
  available: boolean; reason?: string; signal_id: string;
  quality_action?: string | null;
  would_have_been_action_without_overlay?: string | null;
  crypto_quality_verdict?: string | null; crypto_quality_score?: number | null;
  quality_reasons?: string[];
  btc_regime_state?: string | null; eth_confirm_state?: string | null;
  session_bucket_utc?: string | null; session_quality_state?: string | null;
  symbol_cooldown_state?: string | null; mode_session_cooldown_state?: string | null;
  computed_at?: string | null;
  overlay_changed_action?: boolean; overlay_changed_size?: boolean;
}

export type ChartData = {
  symbol: string; tf: string;
  candles: { t: string; o: number; h: number; l: number; c: number; v: number }[];
  candles_available: boolean;
  overlays: Record<string, any>;
  signal: Signal | null;
};
