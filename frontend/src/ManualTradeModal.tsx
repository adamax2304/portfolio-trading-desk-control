import { useEffect, useRef, useState } from "react";
import type { Signal } from "./types";
import { api, haptic, hapticNotify } from "./api";
import { Badge, KV, fmt } from "./components";

type Step = "ticket" | "confirm" | "done";

export function ManualTradeModal({ signal, onClose }: { signal?: Signal | null; onClose: () => void }) {
  const [step, setStep] = useState<Step>("ticket");
  const [risk, setRisk] = useState("0.25");
  const [lev, setLev] = useState("1");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  // a11y: focus the dialog on open, Escape closes, Tab is trapped inside, focus is
  // restored to the previously focused element on close. Runs once on mount so query
  // re-renders never steal focus from the inputs.
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    function focusable(): HTMLElement[] {
      const sel = 'button:not([disabled]), input, textarea, [href], [tabindex]:not([tabindex="-1"])';
      return Array.from(panelRef.current?.querySelectorAll<HTMLElement>(sel) ?? [])
        .filter((el) => el.offsetParent !== null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") { e.preventDefault(); closeRef.current(); return; }
      if (e.key === "Tab") {
        const f = focusable();
        if (f.length === 0) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, []);

  // custom (no-signal) order inputs
  const isCustom = !signal;
  const [csym, setCsym] = useState("");
  const [cdir, setCdir] = useState("long");
  const [centry, setCentry] = useState("");
  const [cstop, setCstop] = useState("");
  const [ctp1, setCtp1] = useState("");

  const sym = signal?.symbol ?? csym;
  const dir = signal?.direction ?? cdir;
  const entry = signal ? (signal.entry_trigger ?? signal.entry_low) : (centry === "" ? undefined : Number(centry));
  const stop = signal ? signal.stop_loss : (cstop === "" ? undefined : Number(cstop));
  const stopDistPct = entry && stop ? (Math.abs(entry - stop) / entry) * 100 : null;
  const a = signal?.actionability;
  const blocked = a ? !a.actionable : false;
  // custom orders need a symbol + a valid stop before they can be reviewed (backend re-checks)
  const customInvalid = isCustom && (!sym.trim() || stop == null || Number.isNaN(stop as number));
  const reviewDisabled = blocked || customInvalid;

  async function submitPaper() {
    haptic("medium");
    const r = await api.command("MANUAL_PAPER_ORDER", {
      symbol: sym, signal_id: signal?.signal_id, direction: dir, asset_class: signal?.asset_class,
      risk_pct: Number(risk) / 100, leverage: Number(lev), entry_price: entry, stop,
      tp1: signal?.tp1 ?? (ctp1 === "" ? undefined : Number(ctp1)),
      tp2: signal?.tp2, tp3: signal?.tp3, notes,
    });
    const ok = r.status === "applied";
    if (ok) hapticNotify("success"); else hapticNotify("error");
    setResult({ ok, msg: ok ? "Paper order queued" : `Rejected: ${r.error ?? "blocked by safety gate"}` });
    setStep("done");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end" style={{ background: "rgba(3,5,10,0.72)", backdropFilter: "blur(4px)" }} onClick={onClose}>
      <div ref={panelRef} role="dialog" aria-modal="true" aria-labelledby="order-ticket-title" tabIndex={-1}
        className="glass w-full max-w-[480px] mx-auto rounded-b-none animate-rise focus:outline-none" style={{ borderRadius: "22px 22px 0 0", maxHeight: "88vh", overflowY: "auto", paddingBottom: "calc(var(--safe-b) + 16px)" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-center pt-2"><div className="w-9 h-1 rounded-full bg-white/15" /></div>
        <div className="p-4">
          <div className="flex items-center justify-between">
            <div id="order-ticket-title" className="text-[17px] font-semibold">Order ticket</div>
            <button className="text-faint" onClick={onClose} aria-label="close"><i className="ti ti-x text-lg" /></button>
          </div>

          {signal && (
            <div className="glass-soft p-3 mt-3 flex items-center justify-between">
              <div>
                <div className="font-semibold">{sym} <span className={dir === "short" ? "text-danger" : "text-profit"}>{dir.toUpperCase()}</span></div>
                <div className="text-[11px] text-faint mt-0.5">{signal.asset_class} · {signal.mode} · Tier {signal.tier} · linked #{signal.signal_id.slice(-6)}</div>
              </div>
              <Badge tone={blocked ? "b-danger" : "b-profit"}>{a?.freshness.label ?? "—"}</Badge>
            </div>
          )}

          {blocked && (
            <div className="glass-soft p-3 mt-3" style={{ borderColor: "rgba(255,93,108,0.4)" }}>
              <div className="text-danger text-[13px] font-medium">Blocked — {a?.blocked_reason}</div>
              <div className="text-[11px] text-faint mt-1">{a?.reasons.join(" · ")}</div>
            </div>
          )}

          {step === "ticket" && (
            <>
              {isCustom ? (
                <>
                  <div className="text-[12px] text-faint mt-3">Custom paper order — paper mode only, stop required.</div>
                  <label className="label block mt-3">Symbol</label>
                  <input value={csym} onChange={(e) => setCsym(e.target.value.toUpperCase())} placeholder="e.g. BTC/USDT"
                    className="w-full bg-white/5 border border-line rounded-xl px-3 py-2.5 mt-1 text-[14px]" />
                  <div className="seg mt-3">
                    {["long", "short"].map((d) => (
                      <button key={d} data-on={cdir === d} onClick={() => { haptic("light"); setCdir(d); }} className="capitalize">{d}</button>
                    ))}
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-3">
                    <Field label="Entry" value={centry} onChange={setCentry} />
                    <Field label="Stop" value={cstop} onChange={setCstop} />
                    <Field label="TP1" value={ctp1} onChange={setCtp1} />
                  </div>
                  {customInvalid && (
                    <div className="text-[11px] text-warn mt-2"><i className="ti ti-alert-triangle mr-1" />Symbol and a valid stop are required.</div>
                  )}
                </>
              ) : (
                <div className="grid grid-cols-3 gap-2 mt-3">
                  <KV k="Entry" v={fmt(entry)} />
                  <KV k="Stop" v={fmt(stop)} tone="text-danger" />
                  <KV k="Stop dist" v={stopDistPct != null ? `${stopDistPct.toFixed(2)}%` : "—"} />
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 mt-3">
                <Field label="Risk %" value={risk} onChange={setRisk} />
                <Field label="Leverage" value={lev} onChange={setLev} />
              </div>
              <label className="label block mt-3">Notes</label>
              <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="optional"
                className="w-full bg-white/5 border border-line rounded-xl px-3 py-2.5 mt-1 text-[13px]" />
              <div className="grid grid-cols-2 gap-2 mt-4">
                <button className="btn" onClick={onClose}>Cancel</button>
                <button className="btn btn-accent" disabled={reviewDisabled} onClick={() => { haptic(); setStep("confirm"); }}>Review</button>
              </div>
              <div className="text-[11px] text-faint mt-3 text-center">Live submit is locked — paper only in v1.</div>
            </>
          )}

          {step === "confirm" && (
            <>
              <div className="glass-soft p-4 mt-3 space-y-2.5">
                <Conf k="Symbol" v={`${sym} ${dir.toUpperCase()}`} />
                <Conf k="Mode" v="PAPER" tone="text-accent" />
                <Conf k="Risk" v={`${risk}%`} />
                <Conf k="Leverage" v={`${lev}x`} />
                <Conf k="Stop distance" v={stopDistPct != null ? `${stopDistPct.toFixed(2)}%` : "—"} />
                <Conf k="Reason" v={signal ? `manual from signal #${signal.signal_id.slice(-6)}` : "free entry"} />
              </div>
              <div className="grid grid-cols-2 gap-2 mt-4">
                <button className="btn" onClick={() => setStep("ticket")}>Back</button>
                <button className="btn btn-accent" onClick={submitPaper}>Confirm Paper</button>
              </div>
              <button className="btn btn-danger w-full mt-2" disabled>Hold to Confirm Live · LOCKED</button>
              <div className="text-[11px] text-faint mt-1.5 text-center">Live requires 30-day forward validation + readiness audit</div>
            </>
          )}

          {step === "done" && (
            <div className="py-8 text-center">
              <div className={`text-2xl mb-3 ${result?.ok ? "text-profit" : "text-danger"}`}>
                <i className={`ti ${result?.ok ? "ti-circle-check" : "ti-alert-triangle"}`} />
              </div>
              <div className="text-[14px]">{result?.msg}</div>
              <button className="btn btn-accent w-full mt-5" onClick={onClose}>Done</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="label block">{label}</label>
      <input value={value} inputMode="decimal" onChange={(e) => onChange(e.target.value)}
        className="w-full bg-white/5 border border-line rounded-xl px-3 py-2.5 mt-1 text-[14px] tnum" />
    </div>
  );
}
function Conf({ k, v, tone = "" }: { k: string; v: string; tone?: string }) {
  return <div className="flex justify-between text-[13px]"><span className="text-muted">{k}</span><span className={`tnum ${tone}`}>{v}</span></div>;
}
