// Risk/paper control editor: shows old → new value + impact, requires explicit confirm,
// funnels through the backend command queue (validated + audited), shows success/failure.
import { useEffect, useRef, useState } from "react";
import { api, haptic, hapticNotify } from "./api";
import { queryClient } from "./query";

export type NumField = "paper_balance" | "risk_per_trade" | "daily_loss_limit" | "weekly_loss_limit" | "max_positions";
export type EditTarget =
  | { kind: "num"; field: NumField; current: number }
  | { kind: "mode"; mode: string; enabled: boolean }
  | null;

const NUM: Record<NumField, { label: string; cmd: string; unit: string; pct?: boolean; int?: boolean; impact: string }> = {
  paper_balance: { label: "Paper balance", cmd: "SET_PAPER_BALANCE", unit: "$", impact: "Notional equity used to size paper positions." },
  risk_per_trade: { label: "Risk / trade", cmd: "SET_RISK_PER_TRADE", unit: "%", pct: true, impact: "Percent of paper equity risked per trade (size from stop distance)." },
  daily_loss_limit: { label: "Daily loss cap", cmd: "SET_DAILY_LOSS_LIMIT", unit: "%", pct: true, impact: "Max committed paper risk per day — new entries blocked beyond it." },
  weekly_loss_limit: { label: "Weekly loss cap", cmd: "SET_WEEKLY_LOSS_LIMIT", unit: "%", pct: true, impact: "Max cumulative paper loss per week." },
  max_positions: { label: "Max open positions", cmd: "SET_MAX_OPEN_POSITIONS", unit: "", int: true, impact: "Maximum simultaneous open paper positions." },
};

export function RiskEditModal({ target, onClose }: { target: EditTarget; onClose: () => void }) {
  const num = target?.kind === "num" ? NUM[target.field] : null;
  const startVal = target?.kind === "num"
    ? (num?.pct ? String(+(target.current * 100).toFixed(4)) : String(target.current))
    : "";
  const [val, setVal] = useState(startVal);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose); closeRef.current = onClose;

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); closeRef.current(); } };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, []);

  if (!target) return null;

  async function submit() {
    if (!target) return;
    setBusy(true); haptic("medium");
    try {
      let r: any;
      if (target.kind === "num" && num) {
        let v = Number(val);
        if (Number.isNaN(v)) { setResult({ ok: false, msg: "Enter a number" }); setBusy(false); return; }
        if (num.pct) v = v / 100;
        if (num.int) v = Math.round(v);
        r = await api.command(num.cmd, { value: v }, "confirm");
      } else if (target.kind === "mode") {
        const type = target.enabled ? "DISABLE_MODE_PAPER" : "ENABLE_MODE_PAPER";
        r = await api.command(type, { mode: target.mode }, "confirm");
      }
      const ok = r?.status === "applied";
      if (ok) hapticNotify("success"); else hapticNotify("error");
      setResult({ ok, msg: ok ? "Applied & audited" : `Rejected: ${r?.error ?? "blocked"}` });
      if (ok) queryClient.invalidateQueries();
    } catch (e: any) {
      hapticNotify("error"); setResult({ ok: false, msg: `Failed: ${e?.message ?? e}` });
    } finally { setBusy(false); }
  }

  const title = target.kind === "num" ? num!.label : `${target.enabled ? "Disable" : "Enable"} ${target.mode.replace(/_/g, " ")}`;
  const oldDisplay = target.kind === "num"
    ? (num!.pct ? `${(target.current * 100).toFixed(2)}%` : num!.int ? String(target.current) : `${num!.unit}${target.current.toLocaleString()}`)
    : (target.enabled ? "enabled" : "paused");
  const newDisplay = target.kind === "num"
    ? (val === "" ? "—" : num!.pct ? `${val}%` : num!.int ? val : `${num!.unit}${val}`)
    : (target.enabled ? "paused" : "enabled");
  const impact = target.kind === "num" ? num!.impact : "Paper trading mode availability (server-enforced; scalp stays locked).";

  return (
    <div className="fixed inset-0 z-50 flex items-end" style={{ background: "rgba(3,5,10,0.72)", backdropFilter: "blur(4px)" }} onClick={onClose}>
      <div ref={panelRef} role="dialog" aria-modal="true" aria-labelledby="risk-edit-title" tabIndex={-1}
        className="glass w-full max-w-[480px] mx-auto animate-rise focus:outline-none"
        style={{ borderRadius: "22px 22px 0 0", paddingBottom: "calc(var(--safe-b) + 16px)" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-center pt-2"><div className="w-9 h-1 rounded-full bg-white/15" /></div>
        <div className="p-4">
          <div className="flex items-center justify-between">
            <div id="risk-edit-title" className="text-[17px] font-semibold">{title}</div>
            <button className="text-faint" onClick={onClose} aria-label="close"><i className="ti ti-x text-lg" /></button>
          </div>

          {result == null ? (
            <>
              <div className="glass-soft p-3 mt-3 flex items-center justify-between text-[13px]">
                <div><div className="label">Current</div><div className="tnum mt-0.5">{oldDisplay}</div></div>
                <i className="ti ti-arrow-right text-faint" />
                <div className="text-right"><div className="label">New</div><div className="tnum mt-0.5 text-accent">{newDisplay}</div></div>
              </div>

              {target.kind === "num" && (
                <input autoFocus value={val} inputMode="decimal" onChange={(e) => setVal(e.target.value)}
                  className="w-full bg-white/5 border border-line rounded-xl px-3 py-2.5 mt-3 text-[15px] tnum" />
              )}

              <div className="text-[12px] text-faint mt-3 leading-relaxed">
                <i className="ti ti-info-circle mr-1" />{impact} Applied via the audited command queue — reversible.
              </div>

              <div className="grid grid-cols-2 gap-2 mt-4">
                <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
                <button className="btn btn-accent" onClick={submit} disabled={busy}>{busy ? "Applying…" : "Confirm"}</button>
              </div>
            </>
          ) : (
            <div className="py-6 text-center">
              <div className={`text-2xl mb-3 ${result.ok ? "text-profit" : "text-danger"}`}>
                <i className={`ti ${result.ok ? "ti-circle-check" : "ti-alert-triangle"}`} />
              </div>
              <div className="text-[14px]">{result.msg}</div>
              <button className="btn btn-accent w-full mt-5" onClick={onClose}>Done</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
