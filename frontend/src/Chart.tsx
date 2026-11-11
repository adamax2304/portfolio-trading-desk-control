import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, AutoscaleInfo } from "lightweight-charts";

type Candle = { t: string; o: number; h: number; l: number; c: number };
type ExecMarker = {
  marker_type: string; event_type?: string; timestamp?: string | null; price?: number | null;
  label?: string; r_at_marker?: number | null; pnl_usdt_at_marker?: number | null;
  qty_closed?: number | null; order_type?: string | null;
};
type ExecLine = { label: string; price: number; kind: string; r_multiple?: number | null };
const toSec = (t: string) => { const ms = Date.parse(t); return Number.isNaN(ms) ? 0 : Math.floor(ms / 1000); };

// lightweight-charts marker glyph per lifecycle marker_type
const GLYPH: Record<string, { shape: string; color: string; pos: string }> = {
  entry: { shape: "arrowUp", color: "#35e0f0", pos: "belowBar" },
  tp_fill: { shape: "circle", color: "#27d18b", pos: "aboveBar" },
  moved_stop: { shape: "square", color: "#e0a83b", pos: "belowBar" },
  stop: { shape: "square", color: "#ff5d6c", pos: "aboveBar" },
  expired_exit: { shape: "square", color: "#8693ab", pos: "aboveBar" },
  missed: { shape: "circle", color: "#8693ab", pos: "aboveBar" },
};
const LINE_COLOR: Record<string, string> = {
  entry: "#35e0f0", stop: "#ff5d6c", moved_stop: "#e0a83b", tp: "#7c6cff",
};

export function ChartPanel(
  { candles, overlays, markers, lines }:
  { candles: Candle[]; overlays: Record<string, any>; markers?: ExecMarker[]; lines?: ExecLine[] }
) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !candles?.length) return;
    const chart: IChartApi = createChart(ref.current, {
      width: ref.current.clientWidth, height: 300,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#5b6680", fontFamily: "JetBrains Mono, monospace" },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.05)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0, vertLine: { color: "rgba(53,224,240,0.4)", labelBackgroundColor: "#0b1020" }, horzLine: { color: "rgba(53,224,240,0.4)", labelBackgroundColor: "#0b1020" } },
    });

    // price levels to keep in view: prefer the explicit lifecycle lines, else overlays.
    const lineList: ExecLine[] = (lines && lines.length)
      ? lines
      : (["entry_trigger", "stop_loss", "tp1", "tp2", "tp3"]
          .map((k) => ({ label: k, price: overlays[k] as number, kind: k.startsWith("tp") ? "tp" : k.includes("stop") ? "stop" : "entry" }))
          .filter((l) => typeof l.price === "number" && Number.isFinite(l.price)) as ExecLine[]);
    const overlayPrices = lineList.map((l) => l.price);

    const series = chart.addCandlestickSeries({
      upColor: "#27d18b", downColor: "#ff5d6c", borderVisible: false,
      wickUpColor: "#27d18b", wickDownColor: "#ff5d6c",
      autoscaleInfoProvider: (orig: () => AutoscaleInfo | null): AutoscaleInfo | null => {
        const res = orig();
        if (!res || !res.priceRange || overlayPrices.length === 0) return res;
        const lo = Math.min(res.priceRange.minValue, ...overlayPrices);
        const hi = Math.max(res.priceRange.maxValue, ...overlayPrices);
        const pad = (hi - lo) * 0.04 || Math.abs(hi) * 0.01 || 1;
        return { priceRange: { minValue: lo - pad, maxValue: hi + pad }, margins: res.margins };
      },
    });
    series.setData(candles.map((c) => ({ time: toSec(c.t) as any, open: c.o, high: c.h, low: c.l, close: c.c })));

    // horizontal price lines (entry / stop / moved stop / TP1-3) — exact price levels
    const mkLine = (price: number, color: string, title: string, dashed = true) =>
      series.createPriceLine({ price, color, lineWidth: 1, lineStyle: dashed ? 2 : 0, axisLabelVisible: true, title });
    if (lines && lines.length) {
      for (const l of lineList) {
        const r = l.r_multiple != null ? ` ${l.r_multiple > 0 ? "+" : ""}${l.r_multiple}R` : "";
        mkLine(l.price, LINE_COLOR[l.kind] || "#7c6cff", `${l.label}${r}`, l.kind !== "entry");
      }
    } else {
      if (overlays.entry_high) mkLine(overlays.entry_high, "rgba(53,224,240,0.7)", "entry↑");
      if (overlays.entry_low) mkLine(overlays.entry_low, "rgba(53,224,240,0.7)", "entry↓");
      if (overlays.entry_trigger) mkLine(overlays.entry_trigger, "#35e0f0", "entry", false);
      if (overlays.stop_loss) mkLine(overlays.stop_loss, "#ff5d6c", "stop");
      if (overlays.tp1) mkLine(overlays.tp1, "#7c6cff", "TP1");
      if (overlays.tp2) mkLine(overlays.tp2, "#9c8cff", "TP2");
      if (overlays.tp3) mkLine(overlays.tp3, "#b6acff", "TP3");
    }

    const mk: any[] = [];
    if (markers && markers.length) {
      // TRUE execution markers from the position lifecycle — entry + each partial TP fill
      // + moved/structural stops + final exit. No misleading single generic exit.
      for (const m of markers) {
        if (!m.timestamp || m.price == null) continue;     // mfe/mae have no time → skip on candles
        const g = GLYPH[m.marker_type] || { shape: "circle", color: "#8693ab", pos: "aboveBar" };
        const rTxt = m.r_at_marker != null ? ` ${m.r_at_marker > 0 ? "+" : ""}${m.r_at_marker}R` : "";
        mk.push({ time: toSec(m.timestamp) as any, position: g.pos, color: g.color, shape: g.shape,
                  text: `${m.label ?? m.marker_type}${rTxt}` });
      }
    } else {
      if (overlays.created_at) mk.push({ time: toSec(overlays.created_at) as any, position: "aboveBar", color: "#5b6680", shape: "circle", text: "signal" });
      if (overlays.entry_triggered_at) mk.push({ time: toSec(overlays.entry_triggered_at) as any, position: "belowBar", color: "#35e0f0", shape: "arrowUp", text: "entry" });
      if (overlays.exit_at) {
        const win = typeof overlays.final_outcome === "string" && /win|tp/i.test(overlays.final_outcome);
        const loss = typeof overlays.final_outcome === "string" && /loss|stop/i.test(overlays.final_outcome);
        mk.push({ time: toSec(overlays.exit_at) as any, position: "aboveBar",
          color: win ? "#27d18b" : loss ? "#ff5d6c" : "#8693ab", shape: "square", text: "exit" });
      }
    }
    if (mk.length) series.setMarkers(mk.sort((a, b) => a.time - b.time));

    chart.timeScale().fitContent();
    const onResize = () => ref.current && chart.applyOptions({ width: ref.current.clientWidth });
    window.addEventListener("resize", onResize);
    return () => { window.removeEventListener("resize", onResize); chart.remove(); };
  }, [candles, overlays, markers, lines]);

  return <div ref={ref} className="glass-soft overflow-hidden" style={{ padding: 4 }} />;
}
