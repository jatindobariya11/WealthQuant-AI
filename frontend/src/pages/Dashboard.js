import React, { useEffect, useState, useCallback, useRef, memo } from "react";
import {
  ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine, Cell
} from "recharts";
import { api } from "../api";
import TVChart from "../components/TVChart";
import { Link } from "react-router-dom";

const INDICES = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"];
const INTERVALS = ["5m", "15m", "30m", "1h", "1d"];
const REFRESH_INTERVAL = 15000;  // 15s — was 5s (too aggressive, caused rate limiting)

// ── V8.0: Module-level preload cache (outside React state, instant tab switching) ──
const _preloadCache = {};
let _preloadInterval = "5m";

const C = {
  bg: "#050505", panel: "rgba(18, 18, 22, 0.65)", hover: "rgba(30, 30, 36, 0.85)",
  border: "rgba(255, 255, 255, 0.08)", text: "#fff", muted: "#9ca3af",
  blue: "#3b82f6", green: "#10b981", red: "#ef4444", yellow: "#f59e0b", purple: "#8b5cf6",
  cyan: "#06b6d4",
};

const StatBlock = ({ label, value, sub, color = C.text, style = {} }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: "2px", ...style }}>
    <span style={{ fontSize: "0.7rem", color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>{label}</span>
    <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
      <span style={{ fontSize: "1.15rem", fontWeight: 700, color, fontFamily: 'Outfit' }}>{value ?? "—"}</span>
      {sub && <span style={{ fontSize: "0.75rem", color: C.muted }}>{sub}</span>}
    </div>
  </div>
);

/* ── Gauge Component ─────────────────────────── */
const MiniGauge = ({ value, min = 0, max = 100, label, zones, size = 60 }) => {
  const pct = Math.max(0, Math.min(100, ((value ?? 50) - min) / (max - min) * 100));
  const angle = -90 + (pct / 100) * 180;
  const zoneLabel = zones?.find(z => (value ?? 50) >= z.from && (value ?? 50) < z.to)?.label || "";
  const zoneColor = zones?.find(z => (value ?? 50) >= z.from && (value ?? 50) < z.to)?.color || C.muted;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
      <svg width={size} height={size * 0.6} viewBox="0 0 100 60">
        <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" strokeLinecap="round" />
        <line
          x1="50" y1="55" x2={50 + 35 * Math.cos(angle * Math.PI / 180)} y2={55 + 35 * Math.sin(angle * Math.PI / 180)}
          stroke={zoneColor} strokeWidth="2.5" strokeLinecap="round"
        />
        <circle cx="50" cy="55" r="3" fill={zoneColor} />
      </svg>
      <div style={{ fontSize: "0.9rem", fontWeight: 700, color: zoneColor, fontFamily: "Outfit" }}>{value?.toFixed?.(1) ?? "—"}</div>
      <div style={{ fontSize: "0.6rem", color: C.muted, textTransform: "uppercase", fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: "0.6rem", color: zoneColor, fontWeight: 700 }}>{zoneLabel}</div>
    </div>
  );
};

/* ── Skeleton Loader ─────────────────────────── */
const Skeleton = ({ width = "100%", height = "16px" }) => (
  <div className="skeleton-pulse" style={{ width, height, borderRadius: "8px", background: "rgba(255,255,255,0.06)" }} />
);

const SkeletonCard = () => (
  <div className="glass-panel" style={{ padding: "1.5rem" }}>
    <Skeleton width="60%" height="12px" />
    <div style={{ marginTop: "1rem" }}><Skeleton width="80%" height="28px" /></div>
    <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
      <Skeleton width="40%" height="14px" />
      <Skeleton width="30%" height="14px" />
    </div>
  </div>
);

const getRegimeColor = (regime) => {
  switch (regime) {
    case "TRENDING_BULL": return C.green;
    case "TRENDING_BEAR": return C.red;
    case "MEAN_REVERTING": return C.blue;
    case "HIGH_VOLATILITY": return C.yellow;
    case "LOW_VOLATILITY": return C.purple;
    default: return C.muted;
  }
};

/* ── V8.0: Live Status Bar ────────────────────────────────────── */
function _ageLabel(isoString) {
  if (!isoString) return "—";
  try {
    const secs = Math.round((Date.now() - new Date(isoString).getTime()) / 1000);
    if (secs < 60) return `${secs}s ago`;
    if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
    return `${Math.round(secs / 3600)}h ago`;
  } catch { return "—"; }
}

function _timeLabel(isoString) {
  if (!isoString) return "—";
  try {
    return new Date(isoString).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch { return "—"; }
}

const LiveStatusBar = memo(({ liveStatus, schedulerStatus }) => {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  if (!liveStatus) return null;

  const items = [
    {
      label: "Prediction",
      value: _timeLabel(liveStatus.prediction_generated),
      sub: `valid until ${_timeLabel(liveStatus.prediction_valid_until)}`,
      color: liveStatus.prediction_state === "LIVE" ? C.green : C.yellow,
      dot: liveStatus.prediction_state === "LIVE" ? C.green : C.yellow,
    },
    {
      label: "Pred Age",
      value: _ageLabel(liveStatus.prediction_generated),
      color: C.text,
      dot: C.cyan,
    },
    {
      label: "Market Data",
      value: _ageLabel(liveStatus.market_data_age),
      color: C.text,
      dot: C.blue,
    },
    {
      label: "Options Data",
      value: _ageLabel(liveStatus.options_data_age),
      color: C.text,
      dot: C.purple,
    },
    {
      label: "DB Sync",
      value: liveStatus.db_sync || "—",
      color: liveStatus.db_sync === "LIVE" ? C.green : C.red,
      dot: liveStatus.db_sync === "LIVE" ? C.green : C.red,
    },
    {
      label: "Scheduler",
      value: liveStatus.scheduler_running ? "ACTIVE" : "STOPPED",
      color: liveStatus.scheduler_running ? C.green : C.red,
      dot: liveStatus.scheduler_running ? C.green : C.red,
    },
    {
      label: "State",
      value: liveStatus.prediction_state || "LOCKED",
      color: C.green,
      dot: C.green,
    },
  ];

  return (
    <div id="live-status-bar" style={{
      display: "flex", alignItems: "center", flexWrap: "wrap",
      gap: "1.5rem", padding: "0.55rem 1.2rem",
      background: "rgba(10,10,14,0.85)",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      backdropFilter: "blur(12px)",
      fontSize: "0.72rem", fontFamily: "Outfit",
      marginBottom: "1rem", borderRadius: "10px",
    }}>
      <span style={{ color: C.muted, fontWeight: 700, fontSize: "0.65rem", letterSpacing: "0.08em", textTransform: "uppercase", marginRight: "0.5rem" }}>
        🟢 LIVE
      </span>
      {items.map(item => (
        <div key={item.label} style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: item.dot, flexShrink: 0, boxShadow: `0 0 4px ${item.dot}` }} />
          <span style={{ color: C.muted }}>{item.label}:</span>
          <span style={{ color: item.color, fontWeight: 700 }}>{item.value}</span>
          {item.sub && <span style={{ color: C.muted, fontSize: "0.65rem" }}>({item.sub})</span>}
        </div>
      ))}
    </div>
  );
});


export default function Dashboard() {
  const [activeIdx, setActiveIdx] = useState("NIFTY");
  const [activeInt, setActiveInt] = useState("5m");
  const [data, setData] = useState(null);
  const [livePrice, setLivePrice] = useState(null);  // V8.0: separate fast-update state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [marketContext, setMarketContext] = useState(null);
  const [instData, setInstData] = useState(null);
  const [gammaData, setGammaData] = useState(null);
  const [liveStatus, setLiveStatus] = useState(null);  // V8.0: live status bar state
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL / 1000);
  const [turbo, setTurbo] = useState(false);
  const [isFastOnly, setIsFastOnly] = useState(false);
  const [pipelineProb, setPipelineProb] = useState(null);
  const [pipelineRegime, setPipelineRegime] = useState(null);
  const countdownRef = useRef(null);
  const fullLoadRef = useRef(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const lastPredictionId = useRef(null);  // V8.0: track prediction lock changes

  // ── V8.0: Startup preload — warm NIFTY + BANKNIFTY cache before user clicks ──
  useEffect(() => {
    const symbols = ["NIFTY", "BANKNIFTY"];
    symbols.forEach(sym => {
      api.getDashboard(sym, "5m")
        .then(d => {
          _preloadCache[sym] = d;
          // If this is the active symbol, hydrate the dashboard immediately
          if (sym === "NIFTY") {
            setData(d);
            setLivePrice(d?.market_snapshot?.ltp);
            setLiveStatus(d?.live_status || null);
          }
        })
        .catch(() => {}); // Silent — preload failures don't block UI
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // Poll V7.4 scheduler status every 60 seconds
  useEffect(() => {
    let mounted = true;
    const poll = () => api.getSchedulerStatus().then(res => { if (mounted) setSchedulerStatus(res); }).catch(() => {});
    poll();
    const t = setInterval(poll, 60000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  const loadFast = useCallback((idx, int_) => {
    setLoading(true);
    setIsFastOnly(true);
    api.getFastSignal(idx, int_)
      .then(d => {
        // V8.0: Only update livePrice (not the whole card) if prediction is locked
        const newPredId = d?.prediction_meta?.prediction_id;
        if (newPredId && newPredId === lastPredictionId.current) {
          // Same prediction — only update live market data
          setLivePrice(d?.price || d?.ltp);
          setData(prev => prev ? {
            ...prev,
            price: d.price,
            ltp: d.ltp,
            change_pct: d.change_pct,
            market_overview: d.market_overview,
          } : d);
        } else {
          // New prediction or first load — full update
          if (newPredId) lastPredictionId.current = newPredId;
          setData(prev => prev ? { ...prev, ...d } : d);
          setLivePrice(d?.price || d?.ltp);
        }
        setError(null);
        setIsFastOnly(true);
      })
      .catch(e => { setError(e.message); })
      .finally(() => setLoading(false));
  }, []);

  const loadFull = useCallback((idx, int_) => {
    api.getSignalDesk(idx, int_)
      .then(d => {
        const newPredId = d?.prediction_meta?.prediction_id;
        if (newPredId && newPredId === lastPredictionId.current) {
          // Same candle prediction — only refresh market data, keep prediction card stable
          setData(prev => prev ? { ...prev, market_overview: d.market_overview, change_pct: d.change_pct, price: d.price } : d);
        } else {
          if (newPredId) lastPredictionId.current = newPredId;
          setData(d);
          setLiveStatus(d?.live_status || null);
        }
        setError(null);
        setIsFastOnly(false);
        setCountdown(REFRESH_INTERVAL / 1000);
      })
      .catch(e => console.warn("Full signal failed:", e.message));
  }, []);

  const loadContext = useCallback(() => {
    api.getMarketContext()
      .then(setMarketContext)
      .catch(err => console.error("Market Context Error", err));
  }, []);

  const loadInstitutional = useCallback((idx) => {
    api.getInstitutionalAlerts(idx)
      .then(setInstData)
      .catch(e => console.error("Institutional Alerts Error", e));
  }, []);

  const loadGammaSqueeze = useCallback((idx) => {
    api.getGammaSqueeze(idx)
      .then(setGammaData)
      .catch(e => {
        console.error("Gamma Squeeze Error", e);
        setGammaData({
          error: true,
          message: e.response?.data?.detail || e.message || "NSE options chain data is temporarily offline."
        });
      });
  }, []);

  const loadPipelineData = useCallback((idx, int_) => {
    api.getRegime(idx, int_)
      .then(setPipelineRegime)
      .catch(e => console.warn("Pipeline regime fetch failed:", e.message));
    
    api.getProbability(idx, int_)
      .then(setPipelineProb)
      .catch(e => console.warn("Pipeline probability fetch failed:", e.message));
  }, []);

  // V8.0: On tab switch — serve from preload cache instantly, refresh in background
  const handleTabSwitch = useCallback((idx) => {
    setActiveIdx(idx);
    const cached = _preloadCache[idx];
    if (cached) {
      // Instant serve from module-level cache
      setData(cached);
      setLivePrice(cached?.market_snapshot?.ltp);
      setLiveStatus(cached?.live_status || null);
      setIsFastOnly(false);
      setLoading(false);
    } else {
      setLoading(true);
    }
    // Background refresh regardless
    api.getDashboard(idx, activeInt)
      .then(d => {
        _preloadCache[idx] = d;
        setData(d);
        setLivePrice(d?.market_snapshot?.ltp);
        setLiveStatus(d?.live_status || null);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [activeInt]);


  const isFirstMount = useRef(true);

  useEffect(() => {
    if (fullLoadRef.current) clearTimeout(fullLoadRef.current);
    if (isFirstMount.current) {
      loadFast(activeIdx, activeInt);
      loadContext();
      loadInstitutional(activeIdx);
      loadGammaSqueeze(activeIdx);
      loadPipelineData(activeIdx, activeInt);
      isFirstMount.current = false;
    } else {
      loadFast(activeIdx, activeInt);
      loadInstitutional(activeIdx);
      loadGammaSqueeze(activeIdx);
      loadPipelineData(activeIdx, activeInt);
    }
    fullLoadRef.current = setTimeout(() => loadFull(activeIdx, activeInt), 500);
    const fastId = setInterval(() => loadFast(activeIdx, activeInt), REFRESH_INTERVAL);
    const fullId = setInterval(() => loadFull(activeIdx, activeInt), REFRESH_INTERVAL * 2);
    const instId = setInterval(() => loadInstitutional(activeIdx), 30000);
    const gammaId = setInterval(() => loadGammaSqueeze(activeIdx), 30000);
    const pipelineId = setInterval(() => loadPipelineData(activeIdx, activeInt), 30000);
    return () => {
      clearTimeout(fullLoadRef.current);
      clearInterval(fastId);
      clearInterval(fullId);
      clearInterval(instId);
      clearInterval(gammaId);
      clearInterval(pipelineId);
    };
  }, [activeIdx, activeInt, loadFast, loadFull, loadContext, loadInstitutional, loadGammaSqueeze, loadPipelineData]);

  useEffect(() => {
    const host = window.location.hostname;
    const wsUrl = process.env.REACT_APP_WS_URL || `ws://${host}:8000/ws/live/${activeIdx}`;
    let ws;
    try { ws = new WebSocket(wsUrl); } catch { return; }
    ws.onmessage = (event) => {
      try {
        const tick = JSON.parse(event.data);
        if (tick.ltp) {
          setData(prev => prev ? { ...prev, price: tick.ltp, market_overview: { ...prev.market_overview, ltp: tick.ltp } } : prev);
        }
      } catch (err) { console.error("WebSocket parsing error:", err); }
    };
    return () => { if (ws) ws.close(); };
  }, [activeIdx]);

  useEffect(() => {
    loadContext();
    const id = setInterval(loadContext, 60000);
    return () => clearInterval(id);
  }, [loadContext]);

  useEffect(() => {
    countdownRef.current = setInterval(() => {
      setCountdown(prev => (prev <= 1 ? REFRESH_INTERVAL / 1000 : prev - 1));
    }, 1000);
    return () => clearInterval(countdownRef.current);
  }, []);

  // ── Skeleton loading state ──
  if (loading && !data) return (
    <div style={{ minHeight: '100vh', padding: '1.5rem 2rem', maxWidth: '1600px', margin: '0 auto' }}>
      <div className="animate-fade-in" style={{ marginBottom: "2rem" }}>
        <Skeleton width="200px" height="32px" />
        <div style={{ marginTop: "0.5rem" }}><Skeleton width="300px" height="14px" /></div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
        {[1,2,3,4].map(i => <SkeletonCard key={i} />)}
      </div>
      <div style={{ marginTop: "1.5rem" }}><Skeleton width="100%" height="400px" /></div>
    </div>
  );

  if (!data) return (
    <div style={{ padding: '2rem', textAlign: 'center', color: C.red, fontFamily: 'Outfit', fontWeight: 500 }}>
      Unable to connect to Signal Desk. Please check backend server.
      {error && <div style={{ fontSize: "0.85rem", marginTop: "0.5rem", color: C.muted }}>{error}</div>}
    </div>
  );

  const sig = data.signal || {};
  const quality = data.signal_quality || data.quality || {};
  const qualityScore = quality.pct ?? quality.score ?? 0;
  const qualityPassed = quality.passed ?? 0;
  const qualityTotal = quality.total ?? 11;
  const ee = data.entry_exit || {};
  const sr = data.sr_zone || {};
  const mo = data.market_overview || {};
  const quant = data.quant || {};
  const returns = quant.returns || {};
  const adv_dec = data.adv_dec || {};


  const activeDirection = sig.signal !== "NO TRADE" ? sig.signal : (sig.breakdown?.Direction || "");
  const isSell = activeDirection?.includes("PUT") || activeDirection?.includes("SELL");
  const isBuy = !isSell && (activeDirection?.includes("BUY") || activeDirection?.includes("CALL"));
  
  const state = data.state || (data.allow_trade === false ? "NO TRADE" : "EXECUTE");
  let stateColor, stateGlow, stateTitle;
  
  if (state === "EXECUTE") {
     stateColor = C.green;
     stateGlow = 'rgba(16,185,129,0.12)';
     stateTitle = sig.signal?.replace(/_/g, ' ') || 'NEUTRAL';
  } else if (state === "READY") {
     stateColor = C.purple;
     stateGlow = 'rgba(139, 92, 246, 0.12)';
     stateTitle = "READY (IMMINENT)";
  } else if (state === "SETUP BUILDING") {
     stateColor = C.yellow;
     stateGlow = 'rgba(245, 158, 11, 0.12)';
     stateTitle = "SETUP BUILDING";
  } else {
     stateColor = C.muted;
     stateGlow = 'transparent';
     stateTitle = "NO TRADE ZONE";
  }

  const netBias = instData?.net_bias || "NEUTRAL";
  const glowColor = netBias === "BUY" ? "rgba(16, 185, 129, 0.4)" : netBias === "SELL" ? "rgba(239, 68, 68, 0.4)" : "rgba(255, 255, 255, 0.1)";
  const alertActive = instData?.total_events_24h > 0;

  const gammaUrgency = gammaData?.urgency || "WATCH";
  const gammaActive = gammaUrgency === "IMMEDIATE" || gammaUrgency === "ALERT";
  const gammaGlowColor = gammaUrgency === "IMMEDIATE" ? "rgba(139, 92, 246, 0.4)" : gammaUrgency === "ALERT" ? "rgba(245, 158, 11, 0.3)" : "rgba(255, 255, 255, 0.05)";

  const rsiZones = [
    { from: 0, to: 30, label: "OVERSOLD", color: C.green },
    { from: 30, to: 45, label: "WEAK", color: C.cyan },
    { from: 45, to: 55, label: "NEUTRAL", color: C.muted },
    { from: 55, to: 70, label: "STRONG", color: C.yellow },
    { from: 70, to: 100, label: "OVERBOUGHT", color: C.red },
  ];
  const adxZones = [
    { from: 0, to: 15, label: "NO TREND", color: C.muted },
    { from: 15, to: 25, label: "WEAK", color: C.yellow },
    { from: 25, to: 50, label: "STRONG", color: C.green },
    { from: 50, to: 100, label: "EXTREME", color: C.purple },
  ];

  return (
    <div style={{ minHeight: '100vh', padding: '1.5rem 2rem', maxWidth: '1600px', margin: '0 auto' }}>

      {/* V8.0: LIVE STATUS BAR */}
      <LiveStatusBar liveStatus={liveStatus || data?.live_status} schedulerStatus={schedulerStatus} />

      {/* ERROR BANNER */}
      {error && (
        <div style={{ padding: '10px 16px', background: 'rgba(239,68,68,0.1)',
          borderBottom: `1px solid ${C.red}`, fontSize: 12, color: C.red,
          borderRadius: '8px', marginBottom: '1rem', fontFamily: 'Outfit' }}>
          ⚠️ <strong>Error:</strong> {error} — check backend is running and BASE URL in api.js
        </div>
      )}

      {/* HEADER SECTION */}
      <header className="animate-fade-in" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <h1 className="brand-font gradient-text" style={{ fontSize: '2.5rem', fontWeight: 800, margin: 0 }}>WealthQuant</h1>
            <div className="glass-pill" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', fontWeight: 600, color: C.green }}>
              <span className="live-dot" /> LIVE SYNC
            </div>
            {/* Refresh countdown */}
            <div className="glass-pill" style={{ fontSize: '0.7rem', color: C.muted, fontWeight: 500 }}>
              ⟳ {countdown}s
            </div>
            {data._perf && (
              <div className="glass-pill" style={{ fontSize: '0.65rem', color: C.muted }}>
                API: {data._perf.elapsed_seconds}s
              </div>
            )}
            {isFastOnly && (
              <div className="glass-pill" style={{ fontSize: '0.65rem', color: C.cyan, fontWeight: 600 }}>
                ⟳ Loading deep data...
              </div>
            )}
            {/* V7.4 Scheduler badge */}
            {schedulerStatus && (
              <div className="glass-pill" style={{
                fontSize: '0.65rem', fontWeight: 700,
                color: schedulerStatus.running ? '#10b981' : '#ef4444',
                border: `1px solid ${schedulerStatus.running ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                background: schedulerStatus.running ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                display: 'flex', alignItems: 'center', gap: '5px',
              }}>
                <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: schedulerStatus.running ? '#10b981' : '#ef4444' }} />
                V7.4 {schedulerStatus.running ? 'COLLECTING' : 'OFFLINE'}
                {schedulerStatus.rows_added_today > 0 && (
                  <span style={{ color: '#a1a1aa' }}>· +{schedulerStatus.rows_added_today.toLocaleString()} rows</span>
                )}
              </div>
            )}
          </div>
          <p style={{ color: C.muted, margin: 0, fontSize: '0.9rem' }}>Algorithmic Trading & Analytics Command Center</p>
        </div>

        <div style={{ textAlign: 'right' }}>
           <div className="brand-font" style={{ fontSize: '2.5rem', fontWeight: 700, lineHeight: 1 }}>
             ₹{data.price?.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
           </div>
           <div style={{ fontSize: '1.1rem', fontWeight: 600, color: data.change_pct >= 0 ? C.green : C.red, marginTop: '4px' }}>
             {data.change_pct >= 0 ? '▲' : '▼'} {Math.abs(data.change_pct || 0).toFixed(2)}%
           </div>
        </div>
      </header>

      {/* MARKET CONTEXT TICKER */}
      {marketContext && (
        <div className="animate-fade-in glass-panel" style={{ display: 'flex', gap: '2rem', padding: '0.8rem 1.5rem', marginBottom: '1.5rem', alignItems: 'center', overflowX: 'auto', border: `1px solid ${C.blue}30` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderRight: `1px solid ${C.border}`, paddingRight: '1.5rem' }}>
            <span style={{ fontSize: '0.7rem', color: C.muted, fontWeight: 700, textTransform: 'uppercase' }}>India VIX</span>
            <span style={{ fontSize: '1.1rem', fontWeight: 800, color: (marketContext.vix?.vix || 0) > 18 ? C.red : C.green }}>{marketContext.vix?.vix || '—'}</span>
            <span style={{ fontSize: '0.7rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(255,255,255,0.1)', color: C.muted }}>{marketContext.vix?.regime}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', borderRight: `1px solid ${C.border}`, paddingRight: '1.5rem' }}>
             <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 700 }}>FII NET</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 700, color: (marketContext.fii_dii?.fii_net || 0) > 0 ? C.green : C.red }}>{marketContext.fii_dii?.fii_net > 0 ? '+' : ''}{marketContext.fii_dii?.fii_net} Cr</span>
             </div>
             <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 700 }}>DII NET</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 700, color: (marketContext.fii_dii?.dii_net || 0) > 0 ? C.green : C.red }}>{marketContext.fii_dii?.dii_net > 0 ? '+' : ''}{marketContext.fii_dii?.dii_net} Cr</span>
             </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.7rem', color: C.muted, fontWeight: 700, textTransform: 'uppercase' }}>Global Context</span>
            <div style={{ display: 'flex', gap: '12px' }}>
               {[
                 { name: "S&P", data: marketContext.global?.sp500 },
                 { name: "NAS", data: marketContext.global?.nasdaq },
                 { name: "DXY", data: marketContext.global?.dxy },
               ].map(m => (
                 <div key={m.name} style={{ display: 'flex', gap: '4px', alignItems: 'center', fontSize: '0.75rem', fontWeight: 600 }}>
                    <span style={{ color: C.muted }}>{m.name}:</span>
                    <span style={{ color: (m.data?.chg_pct ?? 0) >= 0 ? C.green : C.red }}>
                      {(m.data?.chg_pct ?? 0) > 0 ? '+' : ''}{m.data?.chg_pct ?? "—"}%
                    </span>
                 </div>
               ))}
            </div>
            <span style={{ marginLeft: '1rem', padding: '2px 8px', borderRadius: '4px', background: marketContext.global?.bias === 'BULLISH' ? `${C.green}20` : `${C.red}20`, color: marketContext.global?.bias === 'BULLISH' ? C.green : C.red, fontSize: '0.7rem', fontWeight: 800 }}>{marketContext.global?.bias}</span>
          </div>
        </div>
      )}

      {/* MARKET BREADTH & AI LOGIC */}
      {adv_dec && adv_dec.combined && (
        <div className="animate-fade-in glass-panel" style={{ padding: '1.2rem 1.5rem', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '2rem' }}>
              <div>
                <span style={{ fontSize: '0.7rem', color: C.muted, fontWeight: 700, textTransform: 'uppercase' }}>NSE Breadth</span>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '2px', color: (adv_dec.nse?.advances > adv_dec.nse?.declines) ? C.green : C.red }}>
                  {adv_dec.nse?.advances} / {adv_dec.nse?.declines}
                </div>
                <div style={{ fontSize: '0.65rem', color: C.muted }}>Ratio: {adv_dec.nse?.ratio}</div>
              </div>
              <div>
                <span style={{ fontSize: '0.7rem', color: C.muted, fontWeight: 700, textTransform: 'uppercase' }}>BSE Breadth</span>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '2px', color: (adv_dec.bse?.advances > adv_dec.bse?.declines) ? C.green : C.red }}>
                  {adv_dec.bse?.advances} / {adv_dec.bse?.declines}
                </div>
                <div style={{ fontSize: '0.65rem', color: C.muted }}>Ratio: {adv_dec.bse?.ratio}</div>
              </div>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: `1px solid ${C.border}` }}>
              <div>
                <span style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 700, textTransform: 'uppercase' }}>Breadth Sentiment Index</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: adv_dec.combined?.bsi >= 50 ? C.green : C.red }}>{adv_dec.combined?.bsi}%</div>
              </div>
              <div style={{ width: '120px', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${adv_dec.combined?.bsi}%`, background: adv_dec.combined?.bsi >= 50 ? C.green : C.red, borderRadius: '3px' }} />
              </div>
            </div>
          </div>
          
          {adv_dec.ai_logic && (
            <div style={{ padding: '0.8rem 1rem', background: 'rgba(59, 130, 246, 0.05)', borderRadius: '8px', borderLeft: `3px solid ${adv_dec.ai_logic.bias?.includes('BUY') ? C.green : adv_dec.ai_logic.bias?.includes('NEUTRAL') ? C.yellow : C.red}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: C.text }}>AI Regime: <span style={{ color: adv_dec.ai_logic.bias?.includes('BUY') ? C.green : adv_dec.ai_logic.bias?.includes('NEUTRAL') ? C.yellow : C.red }}>{adv_dec.ai_logic.regime?.replace(/_/g, ' ')}</span></span>
                {adv_dec.ai_logic.divergence_active && <span style={{ fontSize: '0.65rem', padding: '2px 6px', background: `${C.yellow}30`, color: C.yellow, borderRadius: '4px', fontWeight: 700 }}>⚠️ DIVERGENCE ACTIVE</span>}
              </div>
              <p style={{ fontSize: '0.75rem', color: C.muted, margin: '0 0 6px 0', lineHeight: 1.4 }}>{adv_dec.ai_logic.regime_description}</p>
              <p style={{ fontSize: '0.75rem', color: C.text, margin: 0, fontWeight: 600 }}>💡 Recommendation: {adv_dec.ai_logic.recommendation}</p>
            </div>
          )}
        </div>
      )}

      {/* CONTROLS */}
      <div className="animate-fade-in" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ display: 'flex', padding: '0.3rem', gap: '4px', borderRadius: '12px' }}>
          {INDICES.map(s => (
            <button key={s} onClick={() => setActiveIdx(s)}
              style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', background: activeIdx === s ? 'rgba(255,255,255,0.1)' : 'transparent', color: activeIdx === s ? '#fff' : C.muted, fontWeight: activeIdx === s ? 600 : 500 }}>
              {s}
            </button>
          ))}
        </div>
        <div className="glass-panel" style={{ display: 'flex', padding: '0.3rem', gap: '4px', borderRadius: '12px' }}>
          {INTERVALS.map(tf => (
            <button key={tf} onClick={() => setActiveInt(tf)}
              style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', background: activeInt === tf ? 'rgba(59,130,246,0.2)' : 'transparent', color: activeInt === tf ? C.blue : C.muted, fontWeight: activeInt === tf ? 600 : 500 }}>
              {tf}
            </button>
          ))}
        </div>
        <div className="glass-panel" style={{ display: 'flex', padding: '0.3rem', gap: '4px', borderRadius: '12px', border: turbo ? `1px solid ${C.purple}60` : `1px solid ${C.border}`, background: turbo ? 'rgba(139, 92, 246, 0.05)' : 'transparent' }}>
           <button onClick={() => setTurbo(!turbo)}
              style={{ 
                padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', 
                background: turbo ? `linear-gradient(135deg, ${C.purple}, ${C.blue})` : 'transparent', 
                color: '#fff', fontWeight: 700, fontSize: '0.75rem', 
                boxShadow: turbo ? `0 0 15px ${C.purple}50` : 'none',
                transition: 'all 0.3s ease',
                display: 'flex', alignItems: 'center', gap: '6px'
              }}>
              <span style={{ fontSize: '1rem' }}>{turbo ? '🤖' : '🧠'}</span>
              {turbo ? 'AGENT ACTIVE' : 'AGENT MODE'}
           </button>
        </div>
        {loading && <span className="glass-pill" style={{ fontSize: "0.7rem", color: C.cyan, fontWeight: 600 }}>⟳ Refreshing...</span>}
      </div>

      {/* TOP METRICS GRID */}
      <div className="animate-fade-in-delayed" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>

        {/* WIDGET 1: AI CORE SIGNAL */}
        <div className="glass-panel" style={{ padding: '1.5rem', position: 'relative', overflow: 'hidden', background: stateGlow, border: `1px solid ${stateColor}40` }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: stateColor, boxShadow: `0 0 20px ${stateColor}` }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
            <h3 className="brand-font" style={{ color: C.text, fontSize: '1rem', opacity: 0.9 }}>AI Direction</h3>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              {pipelineRegime && (
                <span style={{ 
                  background: `${getRegimeColor(pipelineRegime.current_regime)}20`, 
                  color: getRegimeColor(pipelineRegime.current_regime), 
                  padding: '2px 8px', 
                  borderRadius: '4px', 
                  fontSize: '0.75rem', 
                  fontWeight: 700, 
                  border: `1px solid ${getRegimeColor(pipelineRegime.current_regime)}40` 
                }}>
                  {pipelineRegime.current_regime?.replace(/_/g, ' ')}
                </span>
              )}
              <span style={{ background: `${stateColor}30`, color: stateColor, padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700, border: `${stateColor}50` }}>{(sig.confidence?.label ?? sig.confidence)?.toUpperCase()}</span>
            </div>
          </div>
          <div className="brand-font" style={{ fontSize: '2.8rem', fontWeight: 800, color: stateColor, margin: '0.5rem 0', textShadow: `0 0 20px ${stateColor}60`, letterSpacing: '-0.02em' }}>
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

          <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: `1px solid rgba(255,255,255,0.1)`, paddingTop: '1rem', marginTop: 'auto' }}>
             <StatBlock label="Readiness" value={data.readiness ?? (data.score ?? sig.score)} sub="/ 100" color={(data.readiness ?? (data.score ?? sig.score)) >= 75 ? C.green : (data.readiness ?? (data.score ?? sig.score)) >= 60 ? C.purple : (data.readiness ?? (data.score ?? sig.score)) >= 40 ? C.yellow : C.muted} style={{ minWidth: 80 }} />
             <StatBlock label="Score" value={data.score ?? sig.score} sub="/ 100" color={(data.score ?? sig.score) >= 75 ? C.green : (data.score ?? sig.score) >= 60 ? C.yellow : C.red} />
             <StatBlock label="Urgency" value={sig.urgency?.replace(/_/g, " ")} color={sig.urgency === "NOW" ? C.green : C.yellow} />
          </div>
        </div>

        {/* WIDGET 2: TRADE SETUP */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
           <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.9rem', marginBottom: '1.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Execution Setup</h3>
           {state === "NO TRADE" ? (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.muted, fontSize: '0.9rem', fontWeight: 600, textAlign: 'center', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '1.5rem' }}>🚫</span>
                No Valid Trade Setup
              </div>
           ) : state !== "EXECUTE" ? (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '1rem' }}>
                 <StatBlock label="Estimated Move" value={data.estimated_move || (isBuy ? "Potential bullish breakout" : "Potential bearish breakdown")} color={isBuy ? C.green : C.red} />
                 <StatBlock label="Next Trigger" value={data.next_trigger || "Waiting for signal"} color={C.yellow} />
                 <div style={{ fontSize: '0.8rem', color: C.muted, marginTop: '8px' }}>
                   Awaiting confirmation. Execution targets are hidden until state is EXECUTE.
                 </div>
              </div>
           ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', flex: 1 }}>
                <StatBlock label="Entry Price" value={`₹${ee.entry?.toLocaleString() ?? '-'}`} />
                <StatBlock label="Stop Loss" value={`₹${ee.stop_loss?.toLocaleString() ?? '-'}`} color={C.red} />
                <StatBlock label="Target 1" value={`₹${ee.target1?.toLocaleString() ?? '-'}`} color={C.green} />
                <StatBlock label="Risk/Reward" value={ee.rr ? `1 : ${ee.rr}` : '—'} color={ee.rr > 1 ? C.green : C.yellow} />
              </div>
           )}
        </div>

        {/* WIDGET 3: S/R ZONES */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.2rem' }}>
            <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Key Levels</h3>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '2px 8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px' }}>{sr.zone}</span>
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '1.5rem' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: C.red, fontSize: '0.85rem', fontWeight: 600 }}>Resistance</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{sr.resistance_str || '—'}</span>
              </div>
              <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                 <div style={{ height: '100%', width: `${Math.min(100, Math.max(5, 100 - (sr.dist_to_resistance || 0)*10))}%`, background: C.red, borderRadius: '2px' }} />
              </div>
              <div style={{ fontSize: '0.7rem', color: C.muted, marginTop: '4px', textAlign: 'right' }}>{sr.dist_to_resistance ?? '—'}% away</div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: C.green, fontSize: '0.85rem', fontWeight: 600 }}>Support</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{sr.support_str || '—'}</span>
              </div>
              <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                 <div style={{ height: '100%', width: `${Math.min(100, Math.max(5, 100 - (sr.dist_to_support || 0)*10))}%`, background: C.green, borderRadius: '2px' }} />
              </div>
              <div style={{ fontSize: '0.7rem', color: C.muted, marginTop: '4px' }}>{sr.dist_to_support ?? '—'}% away</div>
            </div>
          </div>
        </div>

         {/* WIDGET 4: NEWS SENTIMENT */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
           <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.9rem', marginBottom: '1.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>News Intelligence</h3>
           <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
           {data.news?.articles?.length > 0 ? (
               data.news.articles.slice(0, 3).map((a, i) => (
                 <div key={i} style={{ borderBottom: i < 2 ? '1px solid rgba(255,255,255,0.05)' : 'none', paddingBottom: '0.6rem' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 500, color: '#fff', marginBottom: '4px', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.4 }}>{a.title}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.7rem', color: C.muted }}>{a.source}</span>
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, color: a.sentiment === 'BULLISH' ? C.green : a.sentiment === 'BEARISH' ? C.red : C.yellow }}>{a.sentiment}</span>
                    </div>
                 </div>
               ))
             ) : (
               <div style={{ color: C.muted, fontSize: '0.85rem', textAlign: 'center', padding: '1rem 0' }}>No relevant news found</div>
             )}
           </div>
           <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between' }}>
             <span style={{ fontSize: '0.8rem', color: C.muted }}>Sentiment Bias</span>
             <span style={{ fontSize: '0.85rem', fontWeight: 700, color: data.news?.label?.includes('BULLISH') ? C.green : data.news?.label?.includes('BEARISH') ? C.red : C.yellow }}>{data.news?.label || 'NEUTRAL'}</span>
           </div>
        </div>

        {/* WIDGET 5: PIPELINE INTELLIGENCE MINI-WIDGET */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', position: 'relative' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 className="brand-font" style={{ color: C.text, fontSize: '1rem', opacity: 0.9, margin: 0 }}>Pipeline Intelligence</h3>
            <Link to="/pipeline" style={{ 
              color: C.blue, 
              fontSize: '0.75rem', 
              fontWeight: 700, 
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'color 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.color = C.purple}
            onMouseLeave={(e) => e.target.style.color = C.blue}
            >
              Deep Analysis ➔
            </Link>
          </div>

          {!pipelineProb ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.muted, fontSize: '0.8rem' }}>
              Loading pipeline models...
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', justifyContent: 'center', flex: 1 }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                  <span style={{ color: C.green, fontWeight: 600 }}>P(UP)</span>
                  <span style={{ fontWeight: 700, fontFamily: 'Outfit' }}>{(pipelineProb.p_up * 100).toFixed(0)}%</span>
                </div>
                <div style={{ height: '5px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pipelineProb.p_up * 100}%`, background: C.green }} />
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                  <span style={{ color: C.muted, fontWeight: 600 }}>P(SIDEWAYS)</span>
                  <span style={{ fontWeight: 700, fontFamily: 'Outfit' }}>{(pipelineProb.p_sideways * 100).toFixed(0)}%</span>
                </div>
                <div style={{ height: '5px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pipelineProb.p_sideways * 100}%`, background: C.muted }} />
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                  <span style={{ color: C.red, fontWeight: 600 }}>P(DOWN)</span>
                  <span style={{ fontWeight: 700, fontFamily: 'Outfit' }}>{(pipelineProb.p_down * 100).toFixed(0)}%</span>
                </div>
                <div style={{ height: '5px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pipelineProb.p_down * 100}%`, background: C.red }} />
                </div>
              </div>
            </div>
          )}

          {pipelineProb && (
            <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '10px' }}>
              <StatBlock label="Calibrated Signal" value={pipelineProb.signal} color={pipelineProb.signal?.includes("BUY") ? C.green : pipelineProb.signal?.includes("SELL") ? C.red : C.yellow} />
              <StatBlock label="Kelly Size" value={pipelineProb.kelly_fraction ? `${(pipelineProb.kelly_fraction * 100).toFixed(0)}%` : '—'} color={C.blue} />
            </div>
          )}
        </div>

        {/* AGENT MODE ANALYSIS PANEL */}
        {turbo && data.agent_analysis && (
          <div className="glass-panel animate-fade-in" style={{ 
            gridColumn: '1 / -1', 
            padding: '1.5rem', 
            background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(59, 130, 246, 0.05))',
            border: `1px solid ${C.purple}40`,
            position: 'relative',
            overflow: 'hidden'
          }}>
             <div style={{ position: 'absolute', top: 0, right: 0, padding: '4px 12px', background: C.purple, color: '#fff', fontSize: '0.65rem', fontWeight: 800, borderBottomLeftRadius: '12px' }}>AGENT INTELLIGENCE</div>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                <div>
                   <h3 className="brand-font" style={{ color: C.purple, fontSize: '1.1rem', marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="pulse-dot" style={{ backgroundColor: C.purple }} /> Agent Reasoning
                   </h3>
                   <div style={{ fontSize: '0.9rem', color: '#fff', lineHeight: 1.6, marginBottom: '1rem', fontStyle: 'italic', opacity: 0.9 }}>
                      "{data.agent_analysis.summary}"
                   </div>
                   <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {data.agent_analysis.reasons.map((r, i) => (
                        <div key={i} style={{ display: 'flex', gap: '10px', fontSize: '0.82rem', color: C.muted }}>
                           <span style={{ color: C.purple }}>▹</span>
                           <span>{r}</span>
                        </div>
                      ))}
                   </div>
                </div>
                <div style={{ borderLeft: `1px solid ${C.border}`, paddingLeft: '2rem' }}>
                   <h3 className="brand-font" style={{ color: C.blue, fontSize: '1.1rem', marginBottom: '1rem' }}>Trade Projection</h3>
                   <div className="glass-panel" style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', marginBottom: '1rem' }}>
                      <div style={{ fontSize: '0.75rem', color: C.muted, marginBottom: '4px' }}>AGENT TARGET</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 800, color: data.allow_trade === false ? C.muted : C.green }}>{data.allow_trade === false ? 'N/A' : data.agent_analysis.prediction.split(' ')[1]}</div>
                   </div>
                   <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                         <div style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 700 }}>RISK SCORE</div>
                         <div style={{ fontSize: '1.1rem', fontWeight: 800, color: data.agent_analysis.risk_score > 7 ? C.red : data.agent_analysis.risk_score > 4 ? C.yellow : C.green }}>
                            {data.agent_analysis.risk_score} / 10
                         </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                         <div style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 700 }}>STATUS</div>
                         <div style={{ fontSize: '0.8rem', fontWeight: 800, color: data.allow_trade === false ? C.red : C.purple }}>{data.allow_trade === false ? 'TRADE BLOCKED' : 'READY FOR EXECUTION'}</div>
                      </div>
                   </div>
                </div>
             </div>
          </div>
        )}
      </div>

      {/* ── NEW: TECHNICAL INDICATORS PANEL ── */}
      <div className="animate-fade-in-delayed glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.9rem', marginBottom: '1.2rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Technical Indicators Dashboard
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '1.5rem', justifyItems: 'center' }}>
          <MiniGauge value={mo.rsi} min={0} max={100} label="RSI (14)" zones={rsiZones} />
          <MiniGauge value={mo.stoch_k ?? mo.stoch_rsi} min={0} max={100} label="Stoch RSI" zones={rsiZones} />
          <MiniGauge value={mo.adx} min={0} max={80} label="ADX" zones={adxZones} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.6rem', color: C.muted, textTransform: 'uppercase', fontWeight: 600, marginBottom: '6px' }}>Bollinger Band</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: data.price > (mo.bb_upper ?? Infinity) ? C.red : data.price < (mo.bb_lower ?? -Infinity) ? C.green : C.yellow, fontFamily: 'Outfit' }}>
              {data.price > (mo.bb_upper ?? Infinity) ? "ABOVE" : data.price < (mo.bb_lower ?? -Infinity) ? "BELOW" : "INSIDE"}
            </div>
            <div style={{ fontSize: '0.65rem', color: C.muted, marginTop: '4px' }}>
              U: ₹{mo.bb_upper?.toLocaleString() ?? "—"} | L: ₹{mo.bb_lower?.toLocaleString() ?? "—"}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.6rem', color: C.muted, textTransform: 'uppercase', fontWeight: 600, marginBottom: '6px' }}>Volume</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: mo.volume?.confirms ? C.green : C.red, fontFamily: 'Outfit' }}>
              {mo.volume?.ratio ?? "—"}x
            </div>
            <div style={{ fontSize: '0.65rem', color: C.muted, marginTop: '4px' }}>
              {mo.volume?.confirms ? "BULLISH" : "BEARISH"}
            </div>
            <div style={{ fontSize: '0.55rem', color: C.muted, opacity: 0.8 }}>
              {mo.volume?.current?.toLocaleString()} / {mo.volume?.avg_20?.toLocaleString()}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.6rem', color: C.muted, textTransform: 'uppercase', fontWeight: 600, marginBottom: '6px' }}>EMA Stack</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: (mo.ema9 ?? 0) > (mo.ema21 ?? 0) && (mo.ema21 ?? 0) > (mo.ema50 ?? 0) && (mo.ema50 ?? 0) > (mo.ema200 ?? 0) ? C.green : (mo.ema9 ?? 0) < (mo.ema21 ?? 0) && (mo.ema21 ?? 0) < (mo.ema50 ?? 0) && (mo.ema50 ?? 0) < (mo.ema200 ?? 0) ? C.red : C.yellow, fontFamily: 'Outfit' }}>
              {(mo.ema9 ?? 0) > (mo.ema21 ?? 0) && (mo.ema21 ?? 0) > (mo.ema50 ?? 0) && (mo.ema50 ?? 0) > (mo.ema200 ?? 0) ? "BULLISH" : (mo.ema9 ?? 0) < (mo.ema21 ?? 0) && (mo.ema21 ?? 0) < (mo.ema50 ?? 0) && (mo.ema50 ?? 0) < (mo.ema200 ?? 0) ? "BEARISH" : "MIXED"}
            </div>
            <div style={{ fontSize: '0.6rem', color: C.muted, marginTop: '4px' }}>9 {">"} 21 {">"} 50 {">"} 200</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.6rem', color: C.muted, textTransform: 'uppercase', fontWeight: 600, marginBottom: '6px' }}>Candle Pattern</div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: mo.candle?.includes("BULL") ? C.green : mo.candle?.includes("BEAR") ? C.red : C.yellow, fontFamily: 'Outfit' }}>
              {mo.candle?.replace(/_/g, " ") ?? "—"}
            </div>
          </div>
        </div>
      </div>

      {/* SECONDARY ROW: Chart + Sidebar */}
      <div className="animate-fade-in-delayed" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 1fr)', gap: '1.5rem', marginBottom: '1.5rem' }}>

        {/* CHART WIDGET */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
             <div>
               <h3 className="brand-font" style={{ fontSize: '1.2rem', margin: 0 }}>Candlestick Chart</h3>
               <p style={{ fontSize: '0.75rem', color: C.muted, margin: '4px 0 0' }}>TradingView Lightweight Charts • Live OHLCV</p>
             </div>
             <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
               {ee.stop_loss && <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', background: `${C.red}20`, color: C.red, fontWeight: 600 }}>SL ₹{ee.stop_loss?.toLocaleString()}</span>}
               {ee.target1  && <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', background: `${C.green}20`, color: C.green, fontWeight: 600 }}>T1 ₹{ee.target1?.toLocaleString()}</span>}
             </div>
           </div>
           <TVChart data={data.chart || []} height={400} />
        </div>

        {/* SIDEBAR */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

          {/* INSTITUTIONAL ORDER FLOW ALERT DESK */}
          <div className={`glass-panel ${alertActive ? "institutional-active institutional-sweep" : ""}`} style={{ 
            padding: '1.5rem', 
            position: 'relative', 
            overflow: 'hidden',
            '--inst-glow-color': glowColor,
            border: alertActive ? `1px solid ${netBias === "BUY" ? C.green : C.red}40` : `1px solid ${C.border}`,
            transition: 'all 0.3s ease'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Institutional Order Flow</h3>
              <span style={{ 
                background: netBias === 'BUY' ? `${C.green}20` : netBias === 'SELL' ? `${C.red}20` : 'rgba(255,255,255,0.05)', 
                color: netBias === 'BUY' ? C.green : netBias === 'SELL' ? C.red : C.muted, 
                padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 800 
              }}>
                {netBias} BIAS
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.8rem', color: C.muted }}>Active Alerts (24h)</span>
              <span style={{ fontSize: '0.95rem', fontWeight: 800, color: alertActive ? (netBias === 'BUY' ? C.green : C.red) : C.muted }}>
                {instData?.total_events_24h ?? 0} {instData?.total_events_24h === 1 ? 'Alert' : 'Alerts'}
              </span>
            </div>

            {instData?.active_alerts?.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', marginTop: '0.8rem', paddingRight: '4px' }}>
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
              <div style={{ color: C.muted, fontSize: '0.8rem', textAlign: 'center', padding: '1.5rem 0', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '1.5rem' }}>🛡️</span>
                <span>No institutional sweeps detected in the last 24 hours.</span>
              </div>
            )}
          </div>

          {/* GAMMA SQUEEZE DETECTOR */}
          <div className={`glass-panel ${gammaActive ? "institutional-active institutional-sweep" : ""}`} style={{ 
            padding: '1.5rem', 
            position: 'relative', 
            overflow: 'hidden',
            '--inst-glow-color': gammaGlowColor,
            border: gammaActive ? `1px solid ${gammaUrgency === "IMMEDIATE" ? C.purple : C.yellow}40` : `1px solid ${C.border}`,
            transition: 'all 0.3s ease'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Gamma Squeeze Intel</h3>
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
                      <span style={{ color: C.muted }}>Dealer Pain Index (IPI)</span>
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
                        to forced cover
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

                  {/* Urgency Trigger Flags */}
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
                    <span style={{ 
                      fontSize: '0.58rem', padding: '2px 6px', borderRadius: '3px', fontWeight: 700,
                      background: gammaData.triggers?.volume_spike ? `${C.red}20` : 'rgba(255,255,255,0.03)',
                      color: gammaData.triggers?.volume_spike ? C.red : C.muted
                    }}>
                      {gammaData.triggers?.volume_spike ? '⚡ VOL SPIKE' : 'VOL NORMAL'}
                    </span>
                    <span style={{ 
                      fontSize: '0.58rem', padding: '2px 6px', borderRadius: '3px', fontWeight: 700,
                      background: gammaData.triggers?.oi_decay ? `${C.red}20` : 'rgba(255,255,255,0.03)',
                      color: gammaData.triggers?.oi_decay ? C.red : C.muted
                    }}>
                      {gammaData.triggers?.oi_decay ? '🔥 OI PANIC' : 'OI STABLE'}
                    </span>
                    <span style={{ 
                      fontSize: '0.58rem', padding: '2px 6px', borderRadius: '3px', fontWeight: 700,
                      background: gammaData.triggers?.delta_hedge ? `${C.red}20` : 'rgba(255,255,255,0.03)',
                      color: gammaData.triggers?.delta_hedge ? C.red : C.muted
                    }}>
                      {gammaData.triggers?.delta_hedge ? '🛡️ MM HEDGING' : 'MM NORMAL'}
                    </span>
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
              <div style={{ color: C.muted, fontSize: '0.8rem', textAlign: 'center', padding: '1.5rem 0' }}>
                Loading options chain analysis...
              </div>
            )}
          </div>

          {/* SIGNAL QUALITY CHECKLIST */}
          <div className="glass-panel" style={{ 
            padding: '1.5rem', 
            position: 'relative', 
            overflow: 'hidden',
            border: qualityScore === 100 ? `1px solid ${C.green}60` : `1px solid ${C.border}`,
            boxShadow: qualityScore === 100 ? `0 0 20px ${C.green}15` : 'none'
          }}>
            {qualityScore === 100 && (
              <div style={{ 
                position: 'absolute', top: 0, right: 0, 
                padding: '2px 10px', background: C.green, color: '#000', 
                fontSize: '0.6rem', fontWeight: 900, transform: 'rotate(45deg) translate(15px, -10px)',
                width: '100px', textAlign: 'center'
              }}>
                PERFECT
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Signal Quality</h3>
              <span style={{ fontSize: '0.8rem', fontWeight: 800, color: qualityScore >= 75 ? C.green : qualityScore >= 60 ? C.yellow : C.red }}>
                {qualityScore}% — {quality.label || "Loading"}
              </span>
            </div>
            {/* Progress bar */}
            <div style={{ height: "6px", background: "rgba(255,255,255,0.08)", borderRadius: "3px", marginBottom: "1rem", overflow: "hidden" }}>
              <div style={{ 
                height: "100%", width: `${qualityScore || 0}%`, 
                background: qualityScore >= 75 ? C.green : qualityScore >= 60 ? C.yellow : C.red, 
                borderRadius: "3px", transition: "width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)",
                boxShadow: qualityScore === 100 ? `0 0 10px ${C.green}` : 'none'
              }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
              {(quality.conditions || []).map((c, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem' }}>
                  <span style={{ color: c.met ? C.green : "rgba(239,68,68,0.5)", fontSize: '0.85rem', width: '16px', textAlign: 'center', transition: 'all 0.3s' }}>
                    {c.met ? '✓' : '✗'}
                  </span>
                  <span style={{ color: c.met ? C.text : C.muted, transition: 'all 0.3s' }}>{c.label}</span>
                </div>
              ))}
            </div>
            {qualityScore === 100 && (
              <div style={{ marginTop: '1rem', padding: '8px', borderRadius: '6px', background: `${C.green}10`, border: `1px dashed ${C.green}40`, fontSize: '0.7rem', color: C.green, fontWeight: 600, textAlign: 'center' }}>
                🌟 ALL PARAMETERS ALIGNED
              </div>
            )}
          </div>

          {/* PERFORMANCE RETURNS (real data) */}
          <div className="glass-panel" style={{ padding: '1.5rem', flex: 1 }}>
             <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.85rem', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Performance Returns</h3>
             <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {[
                  { label: "1-Week", key: "1w" },
                  { label: "1-Month", key: "1m" },
                  { label: "3-Month", key: "3m" },
                  { label: "6-Month", key: "6m" },
                  { label: "1-Year", key: "1y" }
                ].map(item => {
                  const val = returns[item.key];
                  const pct = val != null ? (val * 100).toFixed(2) : null;
                  const color = val > 0 ? C.green : val < 0 ? C.red : C.muted;
                  return (
                    <div key={item.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                       <span style={{ fontSize: '0.82rem', color: C.muted }}>{item.label}</span>
                       <span style={{ fontSize: '0.85rem', fontWeight: 700, color, fontFamily: 'Outfit' }}>
                         {pct != null ? `${pct > 0 ? '+' : ''}${pct}%` : '—'}
                       </span>
                    </div>
                  );
                })}
             </div>
          </div>

          {/* OPTIONS INTELLIGENCE */}
          <div className="glass-panel" style={{ padding: '1.5rem', flex: 1 }}>
             <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.85rem', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Options Data</h3>
             <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
               <StatBlock label="Put-Call Ratio" value={data.options?.pcr?.pcr ?? '—'} color={(data.options?.pcr?.pcr || 1) > 1.2 ? C.green : (data.options?.pcr?.pcr || 1) < 0.8 ? C.red : C.yellow} />
               <StatBlock label="Max Pain" value={data.options?.max_pain ? `₹${data.options.max_pain?.toLocaleString()}` : '—'} color={C.blue} />
               <StatBlock label="OI Signal" value={data.options?.oi_signal || '—'} color={data.options?.oi_signal === 'bullish' ? C.green : data.options?.oi_signal === 'bearish' ? C.red : C.muted} />
               <StatBlock label="ATM IV" value={data.options?.atm_iv != null ? `${data.options.atm_iv}%` : '—'} />
             </div>
          </div>

          {/* TREND ALIGNMENT */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
             <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.85rem', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Multi-Timeframe</h3>
             <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
               {Object.entries(data.multitf?.timeframes || {}).map(([tf, v]) => (
                 <div key={tf} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 700, marginBottom: '2px' }}>{tf}</div>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: v.bias === 'BULLISH' ? C.green : v.bias === 'BEARISH' ? C.red : C.yellow }}>{v.bias?.slice(0, 4)}</div>
                 </div>
               ))}
             </div>
             <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '0.8rem', borderTop: `1px solid ${C.border}` }}>
               <div>
                 <div style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 600 }}>ALIGNMENT</div>
                 <div style={{ fontSize: '0.8rem', fontWeight: 700, color: data.multitf?.alignment?.includes('BULL') ? C.green : data.multitf?.alignment?.includes('BEAR') ? C.red : C.yellow, marginTop: '2px' }}>
                   {data.multitf?.alignment?.replace(/_/g, ' ') || '—'}
                 </div>
               </div>
               <div style={{ textAlign: 'right' }}>
                 <div style={{ fontSize: '0.65rem', color: C.muted, fontWeight: 600 }}>QUANT</div>
                 <div style={{ fontSize: '0.8rem', fontWeight: 700, color: quant.confidence > 0 ? C.green : quant.confidence < 0 ? C.red : C.yellow, marginTop: '2px' }}>
                   {quant.signal || '—'}
                 </div>
               </div>
             </div>
          </div>

          {/* TRADING RULES */}
          {data.monday?.rules && data.monday.rules.length > 0 && (
            <div className="glass-panel" style={{ padding: '1.2rem', background: 'rgba(59, 130, 246, 0.05)', border: `1px solid rgba(59, 130, 246, 0.2)` }}>
              <h3 className="brand-font" style={{ color: C.blue, fontSize: '0.8rem', marginBottom: '0.8rem', textTransform: 'uppercase' }}>Trading Rules</h3>
              <ul style={{ paddingLeft: '1.2rem', margin: 0, fontSize: '0.78rem', color: C.muted, lineHeight: 1.5 }}>
                {data.monday.rules.map((rule, i) => <li key={i} style={{ marginBottom: '6px' }}>{rule}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* AUX CHARTS */}
      <div className="animate-fade-in-delayed" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: '1.5rem', opacity: 0.9 }}>

        {/* RSI */}
        <div className="glass-panel" style={{ padding: '1.2rem 1.5rem' }}>
           <h3 className="brand-font" style={{ fontSize: '0.9rem', color: C.muted, marginBottom: '1rem', textTransform: 'uppercase' }}>RSI (14)</h3>
           <div style={{ width: '100%', height: 160 }}>
             <ResponsiveContainer>
               <ComposedChart data={data.chart} margin={{ top: 5, right: -10, left: -20, bottom: 0 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                 <XAxis dataKey="Datetime" hide />
                 <YAxis domain={[0, 100]} stroke={C.muted} tick={{fontSize: 10}} width={40} axisLine={false} tickLine={false} />
                 <Tooltip contentStyle={{ backgroundColor: '#18181b', border: `1px solid ${C.border}`, borderRadius: '8px' }} labelFormatter={() => ''} />
                 <ReferenceLine y={70} stroke={C.red} strokeDasharray="3 3" opacity={0.5} />
                 <ReferenceLine y={30} stroke={C.green} strokeDasharray="3 3" opacity={0.5} />
                 <ReferenceLine y={50} stroke={C.border} opacity={0.5} />
                 <Line type="monotone" dataKey="RSI" stroke="#06b6d4" strokeWidth={1.5} dot={false} isAnimationActive={false} />
               </ComposedChart>
             </ResponsiveContainer>
           </div>
        </div>

        {/* MACD HISTOGRAM */}
        <div className="glass-panel" style={{ padding: '1.2rem 1.5rem' }}>
           <h3 className="brand-font" style={{ fontSize: '0.9rem', color: C.muted, marginBottom: '1rem', textTransform: 'uppercase' }}>MACD Flow</h3>
           <div style={{ width: '100%', height: 160 }}>
             <ResponsiveContainer>
               <ComposedChart data={data.chart} margin={{ top: 5, right: -10, left: -20, bottom: 0 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
                 <XAxis dataKey="Datetime" hide />
                 <YAxis stroke={C.muted} tick={{fontSize: 10}} width={40} axisLine={false} tickLine={false} />
                 <Tooltip contentStyle={{ backgroundColor: '#18181b', border: `1px solid ${C.border}`, borderRadius: '8px' }} labelFormatter={() => ''} />
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

      {/* Score Breakdown */}
      {sig.breakdown && (
        <div className="glass-panel animate-fade-in-delayed" style={{ padding: '1.5rem', marginTop: '1.5rem' }}>
          <h3 className="brand-font" style={{ color: C.muted, fontSize: '0.85rem', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Directional Bias Breakdown
          </h3>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {Object.entries(sig.breakdown).map(([key, val]) => {
              const isNum = typeof val === 'number';
              const isPos = isNum && val > 0;
              const isNeg = isNum && val < 0;
              return (
              <div key={key} style={{
                padding: '8px 14px', borderRadius: '10px', fontSize: '0.8rem',
                background: isPos ? `${C.green}12` : isNeg ? `${C.red}12` : 'rgba(255,255,255,0.03)',
                border: `1px solid ${isPos ? C.green : isNeg ? C.red : C.muted}20`,
                color: isPos ? C.green : isNeg ? C.red : C.text,
              }}>
                <span style={{ fontWeight: 700, color: C.muted }}>{key}</span>
                <span style={{ marginLeft: '8px', fontFamily: 'Outfit', fontWeight: 800 }}>
                  {isPos ? `+${val}` : val}
                </span>
              </div>
            )})}
          </div>
        </div>
      )}
    </div>
  );
}
