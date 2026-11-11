import { useEffect, useState } from "react";
import type { Signal } from "./types";
import { api, haptic } from "./api";
import { useStatus, queryClient } from "./query";
import { TopStatusStrip, BottomNav } from "./shell";
import { ManualTradeModal } from "./ManualTradeModal";
import { Home, Signals, Trades, TradeDetail, Market, Risk, System } from "./screens";

export function App() {
  const [tab, setTab] = useState("Home");
  const [detail, setDetail] = useState<Signal | null>(null);
  const [manual, setManual] = useState<Signal | null | undefined>(undefined); // undefined = closed
  const [confirmPause, setConfirmPause] = useState(false);
  const st = useStatus();

  // Escape closes the emergency-pause confirm dialog.
  useEffect(() => {
    if (!confirmPause) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setConfirmPause(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [confirmPause]);

  const manualAllowed = (st.data?.trading_mode ?? "paper") === "paper"; // manual-live locked
  const openChart = (s: Signal) => { haptic(); setDetail(s); };
  const openManual = (s: Signal) => { haptic(); setManual(s); };
  const goTab = (t: string) => { haptic("light"); setTab(t); setDetail(null); };

  async function doPause() {
    await api.emergencyPause();
    setConfirmPause(false);
    queryClient.invalidateQueries();
    setTab("System");
  }

  return (
    <div className="min-h-full max-w-[480px] mx-auto relative">
      <TopStatusStrip st={st.data} />

      {detail ? (
        <TradeDetail signal={detail} onBack={() => setDetail(null)} onManual={openManual} />
      ) : (
        <>
          {tab === "Home" && <Home go={goTab} onPause={() => setConfirmPause(true)} />}
          {tab === "Signals" && <Signals onChart={openChart} onManual={openManual} />}
          {tab === "Trades" && <Trades onChart={openChart} />}
          {tab === "Market" && <Market />}
          {tab === "Risk" && <Risk />}
          {tab === "System" && <System onPause={() => setConfirmPause(true)} />}
        </>
      )}

      {manualAllowed && !detail && (
        <button onClick={() => setManual(null)} aria-label="manual trade"
          className="fixed z-40 btn btn-accent rounded-full !px-5 !py-3.5 shadow-glow font-semibold"
          style={{ bottom: "calc(var(--safe-b) + 84px)", right: "max(16px, calc(50% - 240px + 16px))" }}>
          <i className="ti ti-plus mr-1" />Manual
        </button>
      )}

      {manual !== undefined && <ManualTradeModal signal={manual} onClose={() => setManual(undefined)} />}

      {confirmPause && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(3,5,10,0.72)", backdropFilter: "blur(4px)" }} onClick={() => setConfirmPause(false)}>
          <div role="dialog" aria-modal="true" aria-labelledby="pause-title" className="glass p-5 w-full max-w-[340px] animate-rise" onClick={(e) => e.stopPropagation()}>
            <div className="text-danger text-2xl mb-2"><i className="ti ti-player-pause" /></div>
            <div id="pause-title" className="text-[16px] font-semibold">Emergency pause?</div>
            <div className="text-[12px] text-faint mt-1.5">Sets the engine paused flag (audited command). No running process is killed; nothing is unwound. You can resume from Risk.</div>
            <div className="grid grid-cols-2 gap-2 mt-4">
              <button className="btn" onClick={() => setConfirmPause(false)}>Cancel</button>
              <button className="btn btn-danger" onClick={doPause}>Confirm pause</button>
            </div>
          </div>
        </div>
      )}

      <BottomNav tab={detail ? "" : tab} onTab={goTab} />
    </div>
  );
}
