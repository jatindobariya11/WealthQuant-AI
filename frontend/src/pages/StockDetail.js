import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine, Cell
} from "recharts";
import { api } from "../api";
import TVChart from "../components/TVChart";

const C = {
  bg: "#050505", panel: "rgba(18, 18, 22, 0.65)", hover: "rgba(30, 30, 36, 0.85)",
  border: "rgba(255, 255, 255, 0.08)", text: "#fff", muted: "#9ca3af",
  blue: "#3b82f6", green: "#10b981", red: "#ef4444", yellow: "#f59e0b", purple: "#8b5cf6"
};

const StatBlock = ({ label, value, sub, color = C.text, style = {} }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: "2px", ...style }}>
    <span style={{ fontSize: "0.7rem", color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>{label}</span>
    <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
      <span style={{ fontSize: "1.1rem", fontWeight: 700, color, fontFamily: "Outfit" }}>{value ?? "—"}</span>
      {sub && <span style={{ fontSize: "0.75rem", color: C.muted }}>{sub}</span>}
    </div>
  </div>
);

export default function StockDetail() {
  const { sym }   = useParams();
  const navigate  = useNavigate();
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [instData, setInstData] = useState(null);
  const [gammaData, setGammaData] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;

    setLoading(true);
    setError(null);
    setInstData(null);
    setGammaData(null);
    
    // FIX: was api.getStock(sym) which hit non-existent /api/stock route
    api.getSignalDesk(sym, "1d", { signal })
       .then(d => setData(d))
       .catch(e => {
         if (e.name === 'CanceledError' || e.name === 'AbortError' || e.code === 'ERR_CANCELED') return;
         setError(e.message); setData(null); 
       })
       .finally(() => {
         if (!signal.aborted) setLoading(false);
       });

    // Fetch institutional alerts initially
    const loadInst = () => {
      api.getInstitutionalAlerts(sym, { signal })
         .then(setInstData)
         .catch(e => {
           if (e.name === 'CanceledError' || e.name === 'AbortError' || e.code === 'ERR_CANCELED') return;
           console.error("Institutional Alerts Error:", e);
         });
    };
    loadInst();

    // Fetch gamma squeeze alerts initially
    const loadGamma = () => {
      api.getGammaSqueeze(sym, { signal })
         .then(setGammaData)
         .catch(e => {
            if (e.name === 'CanceledError' || e.name === 'AbortError' || e.code === 'ERR_CANCELED') return;
            console.error("Gamma Squeeze Error:", e);
            setGammaData({
              error: true,
              message: e.response?.data?.detail || e.message || "NSE options chain data is temporarily offline."
            });
         });
    };
    loadGamma();

    // Poll every 30s
    const instInterval = setInterval(loadInst, 30000);
    const gammaInterval = setInterval(loadGamma, 30000);

    return () => {
      controller.abort();
      clearInterval(instInterval);
      clearInterval(gammaInterval);
    };
  }, [sym]);

  if (loading) return (
    <div style={{ height: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="brand-font" style={{ fontSize: "1.2rem", fontWeight: 600, color: C.blue }}>
        Loading {sym?.replace(".NS", "")}...
      </div>
    </div>
  );

  if (error || !data) return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <p style={{ color: C.red, fontFamily: "Outfit", fontWeight: 500, marginBottom: "1rem" }}>
        {error || `Could not load ${sym}. Try another symbol.`}
      </p>
      <button onClick={() => navigate(-1)}
        className="glass-panel"
        style={{ padding: "8px 20px", border: `1px solid ${C.border}`, background: C.panel, color: C.text, fontSize: 13, borderRadius: 10 }}>
        ← Go Back
      </button>
    </div>
  );

  const sig   = data.signal || {};
  const mo    = data.market_overview || {};
  const ee    = data.entry_exit || {};
  const sr    = data.sr_zone || {};
  const q     = data.quality || {};
  const quant = data.quant || {};

  const netBias = instData?.net_bias || "NEUTRAL";
  const glowColor = netBias === "BUY" ? "rgba(16, 185, 129, 0.4)" : netBias === "SELL" ? "rgba(239, 68, 68, 0.4)" : "rgba(255, 255, 255, 0.1)";
  const alertActive = instData?.total_events_24h > 0;

  const gammaUrgency = gammaData?.urgency || "WATCH";
  const gammaActive = gammaUrgency === "IMMEDIATE" || gammaUrgency === "ALERT";
  const gammaGlowColor = gammaUrgency === "IMMEDIATE" ? "rgba(139, 92, 246, 0.4)" : gammaUrgency === "ALERT" ? "rgba(245, 158, 11, 0.3)" : "rgba(255, 255, 255, 0.1)";

  const activeDirection = sig.signal !== "NO TRADE" ? sig.signal : (sig.breakdown?.Direction || "");
  const isBuy  = activeDirection?.includes("BUY") || activeDirection?.includes("CALL");
  const isSell = activeDirection?.includes("SELL") || activeDirection?.includes("PUT");
  
  const state = data.state || (data.allow_trade === false ? "NO TRADE" : "EXECUTE");
  let stateColor, stateGlow, stateTitle;
  
  if (state === "EXECUTE") {
     stateColor = C.green;
     stateGlow = 'rgba(16,185,129,0.08)';
     stateTitle = sig.signal?.replace(/_/g, ' ') || 'NEUTRAL';
  } else if (state === "READY") {
     stateColor = C.purple;
     stateGlow = 'rgba(139, 92, 246, 0.08)';
     stateTitle = "READY (IMMINENT)";
  } else if (state === "SETUP BUILDING") {
     stateColor = C.yellow;
     stateGlow = 'rgba(245, 158, 11, 0.08)';
     stateTitle = "SETUP BUILDING";
  } else {
     stateColor = C.muted;
     stateGlow = 'transparent';
     stateTitle = "NO TRADE ZONE";
  }

  return (
    <div style={{ maxWidth: "1600px", margin: "0 auto" }}>
      {/* Back Button */}
      <button onClick={() => navigate(-1)}
        className="glass-panel animate-fade-in"
        style={{ marginBottom: "1.5rem", padding: "8px 20px", border: `1px solid ${C.border}`, background: C.panel, color: C.text, fontSize: 13, borderRadius: 10 }}>
        ← Back
      </button>

      {/* Header */}
      <header className="animate-fade-in" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "2rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h2 className="brand-font" style={{ fontSize: "2rem", fontWeight: 800, margin: 0 }}>
            {sym?.replace(".NS", "")}
            <span style={{ fontSize: "0.9rem", color: C.muted, fontWeight: 400, marginLeft: 12 }}>{sym}</span>
          </h2>
          <p style={{ color: C.muted, fontSize: "0.85rem", marginTop: "4px" }}>
            {mo.trend} • {mo.candle?.replace(/_/g, " ")} • ADX {mo.adx}
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="brand-font" style={{ fontSize: "2.2rem", fontWeight: 700, lineHeight: 1 }}>
            ₹{data.price?.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "1rem", fontWeight: 600, color: (data.change_pct ?? 0) >= 0 ? C.green : C.red, marginTop: "4px" }}>
            {(data.change_pct ?? 0) >= 0 ? "▲" : "▼"} {Math.abs(data.change_pct || 0).toFixed(2)}%
          </div>
        </div>
      </header>

      {/* Top Metrics */}
      <div className="animate-fade-in" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1.2rem", marginBottom: "1.5rem" }}>
        {/* Signal */}
        <div className="glass-panel" style={{ padding: "1.5rem", border: `1px solid ${stateColor}40`, background: stateGlow }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
            <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase" }}>AI Signal</span>
            <span style={{ fontSize: "0.7rem", padding: "2px 8px", borderRadius: "4px", background: `${stateColor}20`, color: stateColor, fontWeight: 700 }}>{sig.confidence?.label ?? sig.confidence}</span>
          </div>
          <div className="brand-font" style={{ fontSize: "2rem", fontWeight: 800, color: stateColor }}>
            {stateTitle}
          </div>
          
          {state !== "EXECUTE" && data.reason?.length > 0 && (
             <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '10px', marginBottom: '10px' }}>
                <span style={{ color: C.muted, fontSize: '0.8rem', fontWeight: 600 }}>Missing Triggers:</span>
                {data.reason.map((r, idx) => (
                  <span key={idx} style={{ color: state === "READY" ? C.purple : C.yellow, fontSize: '0.8rem', fontWeight: 600 }}>• {r}</span>
                ))}
             </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: C.muted, marginTop: "4px", paddingTop: "0.5rem", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
            <span>Readiness: <span style={{ color: (data.readiness ?? (data.score ?? sig.score)) >= 75 ? C.green : (data.readiness ?? (data.score ?? sig.score)) >= 60 ? C.purple : (data.readiness ?? (data.score ?? sig.score)) >= 40 ? C.yellow : C.muted, fontWeight: 700 }}>{data.readiness ?? (data.score ?? sig.score)}</span></span>
            <span>Score: <span style={{ color: (data.score ?? sig.score) >= 75 ? C.green : (data.score ?? sig.score) >= 60 ? C.yellow : C.red, fontWeight: 700 }}>{data.score ?? sig.score}</span></span>
          </div>
        </div>

        {/* Execution Setup */}
        <div className="glass-panel" style={{ padding: "1.5rem", display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase", display: "block", marginBottom: "1rem" }}>Execution Setup</span>
          {state === "NO TRADE" ? (
             <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.muted, fontSize: '0.9rem', fontWeight: 600, textAlign: 'center', flexDirection: 'column', gap: '8px', height: '60%' }}>
                <span style={{ fontSize: '1.5rem' }}>🚫</span>
                No Valid Trade Setup
             </div>
          ) : state !== "EXECUTE" ? (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '1rem' }}>
                  <StatBlock label="Estimated Move" value={data.estimated_move || (isBuy ? "Potential bullish breakout" : isSell ? "Potential bearish breakdown" : "Neutral range expansion")} color={isBuy ? C.green : isSell ? C.red : C.muted} />
                 <StatBlock label="Next Trigger" value={data.next_trigger || "Waiting for signal"} color={C.yellow} />
                 <div style={{ fontSize: '0.8rem', color: C.muted, marginTop: '8px' }}>
                   Awaiting confirmation. Targets hidden until EXECUTE.
                 </div>
              </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <StatBlock label="Entry" value={`₹${ee.entry?.toLocaleString() ?? "—"}`} />
              <StatBlock label="Stop Loss" value={`₹${ee.stop_loss?.toLocaleString() ?? "—"}`} color={C.red} />
              <StatBlock label="Target 1" value={`₹${ee.target1?.toLocaleString() ?? "—"}`} color={C.green} />
              <StatBlock label="R:R" value={ee.rr ? `1 : ${ee.rr}` : "—"} color={ee.rr > 1 ? C.green : C.yellow} />
            </div>
          )}
        </div>

        {/* Technical Indicators */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase", display: "block", marginBottom: "1rem" }}>Technical Snapshot</span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <StatBlock label="RSI (14)" value={mo.rsi} color={(mo.rsi ?? 50) < 35 ? C.blue : (mo.rsi ?? 50) > 65 ? C.red : C.text} />
            <StatBlock label="Vol Ratio" value={mo.volume?.ratio ? `${mo.volume.ratio}x` : "—"} />
            <StatBlock label="ADX" value={mo.adx} color={(mo.adx ?? 0) > 25 ? C.yellow : C.muted} />
            <StatBlock label="ATR" value={mo.atr ? `₹${mo.atr}` : "—"} />
          </div>
        </div>

        {/* Quality Checklist */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase" }}>Signal Quality</span>
            <span style={{ fontSize: "0.8rem", fontWeight: 700, color: q.pct >= 75 ? C.green : q.pct >= 60 ? C.yellow : C.red }}>
              {q.pct}% — {q.label || "Loading"}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "140px", overflowY: "auto" }}>
            {(q.conditions || []).map((c, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.8rem" }}>
                <span style={{ color: c.met ? C.green : C.red, fontSize: "0.9rem" }}>{c.met ? "✓" : "✗"}</span>
                <span style={{ color: c.met ? C.text : C.muted }}>{c.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="glass-panel animate-fade-in-delayed" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <div>
            <h3 className="brand-font" style={{ fontSize: "1.1rem", margin: 0 }}>Candlestick Chart</h3>
            <p style={{ fontSize: "0.75rem", color: C.muted, margin: "4px 0 0" }}>TradingView Lightweight Charts • OHLCV + EMAs</p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            {ee.stop_loss && <span style={{ fontSize: "0.75rem", padding: "2px 8px", borderRadius: "4px", background: `${C.red}20`, color: C.red, fontWeight: 600 }}>SL ₹{ee.stop_loss?.toLocaleString()}</span>}
            {ee.target1 && <span style={{ fontSize: "0.75rem", padding: "2px 8px", borderRadius: "4px", background: `${C.green}20`, color: C.green, fontWeight: 600 }}>T1 ₹{ee.target1?.toLocaleString()}</span>}
          </div>
        </div>
        <TVChart data={data.chart || []} height={400} />
      </div>

      {/* RSI + MACD Charts */}
      <div className="animate-fade-in-delayed" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.2rem" }}>
        {/* RSI */}
        <div className="glass-panel" style={{ padding: "1.2rem" }}>
          <h3 className="brand-font" style={{ fontSize: "0.85rem", color: C.muted, marginBottom: "0.8rem", textTransform: "uppercase" }}>RSI (14)</h3>
          <div style={{ width: "100%", height: 160 }}>
            <ResponsiveContainer>
              <ComposedChart data={data.chart} margin={{ top: 5, right: -10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                <XAxis dataKey="Datetime" hide />
                <YAxis domain={[0, 100]} stroke={C.muted} tick={{fontSize: 10}} width={40} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: "#18181b", border: `1px solid ${C.border}`, borderRadius: "8px" }} labelFormatter={() => ""} />
                <ReferenceLine y={70} stroke={C.red} strokeDasharray="3 3" opacity={0.5} />
                <ReferenceLine y={30} stroke={C.green} strokeDasharray="3 3" opacity={0.5} />
                <ReferenceLine y={50} stroke={C.border} opacity={0.5} />
                <Line type="monotone" dataKey="RSI" stroke="#06b6d4" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* MACD */}
        <div className="glass-panel" style={{ padding: "1.2rem" }}>
          <h3 className="brand-font" style={{ fontSize: "0.85rem", color: C.muted, marginBottom: "0.8rem", textTransform: "uppercase" }}>MACD Flow</h3>
          <div style={{ width: "100%", height: 160 }}>
            <ResponsiveContainer>
              <ComposedChart data={data.chart} margin={{ top: 5, right: -10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                <XAxis dataKey="Datetime" hide />
                <YAxis stroke={C.muted} tick={{fontSize: 10}} width={40} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: "#18181b", border: `1px solid ${C.border}`, borderRadius: "8px" }} labelFormatter={() => ""} />
                <Bar dataKey="MACD_Hist" opacity={0.8}>
                  {(data.chart || []).map((d, idx) => (
                    <Cell key={`cell-${idx}`} fill={(d.MACD_Hist ?? 0) >= 0 ? C.green : C.red} />
                  ))}
                </Bar>
                <Line type="monotone" dataKey="MACD" stroke={C.blue} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="MACD_Signal" stroke={C.yellow} strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* S/R + Options + MTF Row */}
      <div className="animate-fade-in-delayed" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.2rem", marginTop: "1.5rem" }}>
        {/* S/R Zone */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase" }}>Key Levels</span>
            <span style={{ fontSize: "0.7rem", fontWeight: 600, padding: "2px 8px", background: "rgba(255,255,255,0.1)", borderRadius: "4px" }}>{sr.zone}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <StatBlock label="Support" value={sr.support_str || "—"} color={C.green} sub={sr.dist_to_support != null ? `${sr.dist_to_support}% away` : ""} />
            <StatBlock label="Resistance" value={sr.resistance_str || "—"} color={C.red} sub={sr.dist_to_resistance != null ? `${sr.dist_to_resistance}% away` : ""} />
          </div>
        </div>

        {/* Options Data */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase", display: "block", marginBottom: "1rem" }}>Options Intelligence</span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <StatBlock label="PCR" value={data.options?.pcr?.pcr ?? "—"} color={(data.options?.pcr?.pcr ?? 1) > 1.2 ? C.green : (data.options?.pcr?.pcr ?? 1) < 0.8 ? C.red : C.yellow} />
            <StatBlock label="Max Pain" value={data.options?.max_pain ? `₹${data.options.max_pain?.toLocaleString()}` : "—"} color={C.blue} />
            <StatBlock label="OI Signal" value={data.options?.oi_signal || "—"} />
            <StatBlock label="ATM IV" value={data.options?.atm_iv ? `${data.options.atm_iv}%` : "—"} />
          </div>
        </div>

        {/* Quant Engine */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase", display: "block", marginBottom: "1rem" }}>Quant MTF Engine</span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <StatBlock label="Signal" value={quant.signal || "—"} color={quant.confidence > 0 ? C.green : quant.confidence < 0 ? C.red : C.yellow} />
            <StatBlock label="Score" value={quant.score ?? "—"} />
            <StatBlock label="1M Return" value={quant.returns?.["1m"] != null ? `${(quant.returns["1m"] * 100).toFixed(2)}%` : "—"} color={(quant.returns?.["1m"] ?? 0) > 0 ? C.green : C.red} />
            <StatBlock label="1Y Return" value={quant.returns?.["1y"] != null ? `${(quant.returns["1y"] * 100).toFixed(2)}%` : "—"} color={(quant.returns?.["1y"] ?? 0) > 0 ? C.green : C.red} />
          </div>
        </div>

        {/* Institutional Order Flow Monitor */}
        <div className={`glass-panel ${alertActive ? "institutional-active institutional-sweep" : ""}`} style={{ 
          padding: '1.5rem', 
          position: 'relative', 
          overflow: 'hidden',
          '--inst-glow-color': glowColor,
          border: alertActive ? `1px solid ${netBias === "BUY" ? C.green : C.red}40` : `1px solid ${C.border}`,
          transition: 'all 0.3s ease'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase" }}>Institutional Flow</span>
            <span style={{ 
              background: netBias === 'BUY' ? `${C.green}20` : netBias === 'SELL' ? `${C.red}20` : 'rgba(255,255,255,0.05)', 
              color: netBias === 'BUY' ? C.green : netBias === 'SELL' ? C.red : C.muted, 
              padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 800 
            }}>
              {netBias} BIAS
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: C.muted }}>Alerts (24h)</span>
            <span style={{ fontSize: '0.95rem', fontWeight: 800, color: alertActive ? (netBias === 'BUY' ? C.green : C.red) : C.muted }}>
              {instData?.total_events_24h ?? 0} {instData?.total_events_24h === 1 ? 'Alert' : 'Alerts'}
            </span>
          </div>

          {instData?.active_alerts?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '120px', overflowY: 'auto', marginTop: '0.8rem', paddingRight: '4px' }}>
              {instData.active_alerts.map((alert, i) => (
                <div key={i} style={{ 
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                  padding: '8px 10px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', 
                  border: `1px solid ${alert.aggressor === 'BUY' ? C.green : C.red}15` 
                }}>
                  <div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: alert.aggressor === 'BUY' ? C.green : C.red }}>
                      {alert.aggressor === 'BUY' ? '▲ BUY SWEEP' : '▼ SELL SWEEP'}
                    </div>
                    <div style={{ fontSize: '0.62rem', color: C.muted }}>
                      {alert.time} • Price: ₹{alert.price}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 800, fontFamily: 'Outfit' }}>
                      {alert.volume_ratio}x Vol
                    </div>
                    <div style={{ fontSize: '0.62rem', color: alert.strength === 'EXTREME' ? C.purple : alert.strength === 'STRONG' ? C.blue : C.muted, fontWeight: 700 }}>
                      {alert.strength}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: C.muted, fontSize: '0.8rem', textAlign: 'center', padding: '1.2rem 0', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '1.5rem' }}>🛡️</span>
              <span>No institutional sweeps detected (24h).</span>
            </div>
          )}
        </div>

        {/* Gamma Squeeze Monitor */}
        <div className={`glass-panel ${gammaActive ? "institutional-active institutional-sweep" : ""}`} style={{ 
          padding: '1.5rem', 
          position: 'relative', 
          overflow: 'hidden',
          '--inst-glow-color': gammaGlowColor,
          border: gammaActive ? `1px solid ${gammaUrgency === "IMMEDIATE" ? C.purple : C.yellow}40` : `1px solid ${C.border}`,
          transition: 'all 0.3s ease'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase" }}>Gamma Squeeze</span>
            <span style={{ 
              background: gammaUrgency === 'IMMEDIATE' ? `${C.purple}20` : gammaUrgency === 'ALERT' ? `${C.yellow}20` : 'rgba(255,255,255,0.05)', 
              color: gammaUrgency === 'IMMEDIATE' ? C.purple : gammaUrgency === 'ALERT' ? C.yellow : C.muted, 
              padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 800 
            }}>
              {gammaUrgency}
            </span>
          </div>

          {gammaData ? (
            gammaData.error ? (
              <div style={{ color: C.muted, fontSize: '0.8rem', textAlign: 'center', padding: '1.2rem 0', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '1.5rem' }}>⚠️</span>
                <span style={{ fontWeight: 600, color: C.text }}>Options Data Offline</span>
                <p style={{ fontSize: '0.72rem', lineHeight: '1.4', margin: 0, opacity: 0.8, maxWidth: '240px' }}>
                  {gammaData.message}
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                
                {/* Trapped MM Pain Index */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', marginBottom: '4px' }}>
                    <span style={{ color: C.muted }}>Dealer Pain (IPI)</span>
                    <span style={{ fontWeight: 700, color: gammaData.ipi_score >= 75 ? C.red : gammaData.ipi_score >= 50 ? C.yellow : C.green }}>
                      {gammaData.ipi_score} / 100
                    </span>
                  </div>
                  <div style={{ height: '5px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ 
                      height: '100%', 
                      width: `${gammaData.ipi_score}%`, 
                      background: gammaData.ipi_score >= 75 ? C.red : gammaData.ipi_score >= 50 ? C.yellow : C.green,
                      borderRadius: '3px',
                      transition: 'width 0.5s ease'
                    }} />
                  </div>
                </div>

                {/* Squeeze Direction & Wall Strike */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', padding: '8px 0', borderTop: '1px solid rgba(255,255,255,0.05)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <div>
                    <div style={{ fontSize: '0.62rem', color: C.muted, textTransform: 'uppercase', fontWeight: 600 }}>Gamma Wall</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 800, fontFamily: 'Outfit', color: gammaData.direction === 'UP' ? C.green : C.red }}>
                      ₹{gammaData.gamma_wall?.toLocaleString()}
                    </div>
                    <div style={{ fontSize: '0.62rem', color: C.muted }}>
                      {gammaData.direction === 'UP' ? '▲ Bullish Squeeze' : '▼ Bearish Squeeze'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.62rem', color: C.muted, textTransform: 'uppercase', fontWeight: 600 }}>Distance</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 800, fontFamily: 'Outfit', color: C.text }}>
                      {gammaData.distance_pct}%
                    </div>
                    <div style={{ fontSize: '0.62rem', color: C.muted }}>
                      to cover
                    </div>
                  </div>
                </div>

                {/* GEX and Flip level */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', fontSize: '0.78rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: C.muted }}>Net GEX:</span>
                    <span style={{ fontWeight: 700, color: gammaData.net_gex_cr >= 0 ? C.green : C.red }}>
                      {gammaData.net_gex_cr > 0 ? '+' : ''}{gammaData.net_gex_cr} Cr
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: C.muted }}>Flip Lvl:</span>
                    <span style={{ fontWeight: 700, fontFamily: 'Outfit' }}>
                      ₹{gammaData.flip_level?.toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Recommended Execution Action */}
                <div style={{ 
                  marginTop: '4px',
                  padding: '8px 10px', 
                  borderRadius: '8px', 
                  background: gammaActive ? (gammaUrgency === 'IMMEDIATE' ? `${C.purple}12` : `${C.yellow}10`) : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${gammaActive ? (gammaUrgency === 'IMMEDIATE' ? C.purple : C.yellow) : 'transparent'}20`,
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  color: gammaActive ? (gammaUrgency === 'IMMEDIATE' ? '#e9d5ff' : C.yellow) : C.muted,
                  lineHeight: '1.2'
                }}>
                  {gammaData.action}
                </div>

              </div>
            )
          ) : (
            <div style={{ color: C.muted, fontSize: '0.8rem', textAlign: 'center', padding: '1.5rem 0', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '1.5rem' }}>🛡️</span>
              <span>No gamma squeeze threats (24h).</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
