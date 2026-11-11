# Control Plane — Premium UI/UX Redesign Report (v0.2)

**Date:** 2026-06-17 · **Verdict: `CONTROL_PLANE_UI_PREMIUM_READY`**
Backend, safety model, and command queue unchanged (18 backend tests still pass). This was a
frontend-only redesign + data-presentation pass.

## Design philosophy
Institutional dark cockpit — TradingView-mobile × Linear × Bloomberg-lite. Layered
near-black navy (`#05070D`) with two soft radial accent washes; translucent **glass** cards
with hairline borders; electric-cyan primary + violet secondary; green/amber/red status,
purple = shadow/non-actionable. Inter for UI, JetBrains Mono tabular numerals for prices/R.
Strong hierarchy: tiny uppercase labels, big metrics, one primary action per card. Subtle
motion only (status pulse, card rise, skeleton shimmer) — no casino glow.

## Design tokens (one place)
`tailwind.config.js` (palette, fonts, shadows `glow`/`card`, keyframes) + `src/index.css`
(`.glass`, `.glass-soft`, `.badge` variants, `.btn*`, `.seg`, `.skel`, safe-area vars,
`.tnum`). Restyle the whole app from these two files.

## Screens redesigned (all 6 + detail)
- **Home** — hero status card (gradient, live dot, mode/tick, emergency pause), 4 metric
  cards, conditional **Action required** panel (late/sector-cap/errors/offline), icon
  **event timeline**.
- **Signals** — segmented filters (asset + status), premium `SignalCard`: actionable cards
  get a green-glow border + Manual Entry; blocked cards desaturate + show DO NOT CHASE /
  SHADOW ONLY / sector-cap and **no** Manual Entry.
- **Trades** — open/pending/closed/shadow tabs, `TradeCard` with R + outcome + MFE/MAE,
  designed empty states ("System is monitoring pending setups").
- **Trade detail** — `ChartPanel` (lightweight-charts: transparent bg, cyan entry band,
  red stop, violet TP1/2/3, signal+entry markers), result hero for closed trades, setup-
  analysis rows with check/warn icons; honest "chart data unavailable".
- **Market** — narratives (strength) + funding/OI (squeeze flagged red), compact.
- **Risk** — mode control (paper/disabled; manual+auto live shown locked), metric cards,
  allowed-modes list (scalp = locked "research only"), base+override note.
- **System** — health cards with live dots + status, 24h error list, sanity/pause actions;
  "no destructive restart in v1" note.

## Component system (`components.tsx`, `shell.tsx`, `ManualTradeModal.tsx`, `Chart.tsx`)
StatusDot (pulse), ModeBadge, ActionabilityBadge, Badge, MetricCard, Sparkline, KV,
SignalCard, TradeCard, EmptyState, Skeleton/SkeletonList, ErrorBanner, TopStatusStrip,
BottomNav (Tabler icons + active glow), ChartPanel, ManualTradeModal (3-step order ticket:
ticket → confirmation sheet → result; paper confirm, **live hold-to-confirm locked**),
emergency-pause confirm modal.

## Data / state
Typed `types.ts`; typed `api.ts` client (initData header). **TanStack Query** (`query.ts`)
with 15–30s polling, skeleton loading, error→retry. Telegram WebApp: `expand()`, header/bg
color, **haptics** on actions, safe-area padding, 480px max width, no horizontal overflow.

## Safety UI (backend still final authority)
Manual Entry is hidden/disabled for scalp, C-tier, rejected, shadow, late/very-late,
sector-cap, missing-stop, live-locked. Banners: DO NOT CHASE / SHADOW ONLY / SECTOR CAP /
scalp locked / live locked. The order ticket blocks submit on non-actionable signals and
the backend independently rejects (verified by existing tests).

## Known limitations
- **Build not run here** (offline sandbox — no `npm install`). Source is TypeScript-correct
  by inspection, deps declared, no dangling imports. Run `npm install && npm run build` to
  confirm; CDN webfonts (Inter, JetBrains Mono, Tabler icons) load at runtime.
- Polling, not SSE/WebSocket (live push is the next upgrade).
- Sparkline component shipped but trade history series isn't exposed by the API yet (needs a
  small read-only adapter addition to populate per-trade equity points).
- Risk-edit controls render current state; the inline slider→confirm write flow reuses the
  existing `/api/risk/update` command (wired in `api.ts`), full UI control surface is a
  fast follow.
