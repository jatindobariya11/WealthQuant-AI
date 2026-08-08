import React, { useState, useEffect, useRef } from "react";
import { api } from "../api";
import AIDecisionPanel from "../components/AIDecisionPanel";
import ProbabilityGauge from "../components/ProbabilityGauge";
import RegimeTimeline from "../components/RegimeTimeline";
import PipelineFlow from "../components/PipelineFlow";
import BayesianDistribution from "../components/BayesianDistribution";

const SYMBOLS = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"];
const INTERVALS = ["5m", "15m", "1h", "1d"];

export default function Pipeline() {
  const [activeSymbol, setActiveSymbol] = useState("NIFTY");
  const [activeInterval, setActiveInterval] = useState("15m");
  const [pipelineData, setPipelineData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [countdown, setCountdown] = useState(30);

  const timerRef = useRef(null);

  const fetchData = async (sym = activeSymbol, int = activeInterval, signal = undefined) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPipeline(sym, int, { signal });
      if (data && data.stages) {
        setPipelineData(data);
      } else {
        throw new Error("Invalid pipeline data response");
      }
    } catch (err) {
      if (err.name === 'CanceledError' || err.name === 'AbortError' || err.code === 'ERR_CANCELED') return;
      console.error(err);
      setError(err.message || "Failed to fetch AI pipeline data.");
    } finally {
      setLoading(false); // Can be safely called, the next request will set it to true if still mounted
    }
  };

  // Initial load and symbol/interval updates
  useEffect(() => {
    const controller = new AbortController();
    fetchData(activeSymbol, activeInterval, controller.signal);
    setCountdown(30);
    return () => controller.abort();
  }, [activeSymbol, activeInterval]);

  // Countdown timer and auto-refresh
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);

    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          fetchData(activeSymbol, activeInterval); // No abort signal needed for polling
          return 30;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [activeSymbol, activeInterval]);

  const handleRetry = () => {
    fetchData(activeSymbol, activeInterval);
    setCountdown(30);
  };

  // Safe accessor helper
  const getStage = (stageName) => {
    return pipelineData?.stages?.[stageName] || {};
  };

  const getMetadata = () => {
    return {
      latency_ms: pipelineData?.latency_ms || 0,
      stage_latencies: pipelineData?.stage_latencies || {},
      errors: pipelineData?.errors || {},
      timestamp: pipelineData?.timestamp || null
    };
  };

  if (loading && !pipelineData) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "20px", color: "#fff" }}>
        {/* Skeleton Header */}
        <div className="glass-panel skeleton-pulse" style={{ height: "60px", width: "100%" }} />
        {/* Skeleton Flow */}
        <div className="glass-panel skeleton-pulse" style={{ height: "120px", width: "100%" }} />
        {/* Skeleton Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
          <div className="glass-panel skeleton-pulse" style={{ height: "250px" }} />
          <div className="glass-panel skeleton-pulse" style={{ height: "250px" }} />
          <div className="glass-panel skeleton-pulse" style={{ height: "250px" }} />
        </div>
      </div>
    );
  }

  if (error && !pipelineData) {
    return (
      <div className="glass-panel" style={{ padding: "40px", textAlign: "center", color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", gap: "16px" }}>
        <h3 style={{ margin: 0, color: "#ef4444" }}>Pipeline Connection Error</h3>
        <p style={{ color: "#a1a1aa", fontSize: "14px" }}>{error}</p>
        <button
          onClick={handleRetry}
          style={{
            background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
            color: "#fff", border: "none", padding: "10px 24px", borderRadius: "8px",
            fontWeight: 700, cursor: "pointer", transition: "all 0.2s"
          }}
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const probStage = getStage("probabilities");
  const regimeStage = getStage("regime");
  const fusionStage = getStage("fusion");
  const hawkesStage = getStage("hawkes");
  const kalmanStage = getStage("kalman");
  const particleStage = getStage("particle");
  const metaStage = getStage("meta_learning");
  const reportStage = getStage("analyst_report");
  const meta = getMetadata();

  const spotPrice = kalmanStage.filtered_price || 0;

  // Render variables mapping
  const activeRegime = regimeStage.current_regime || "TRANSITION";
  const confidence = regimeStage.regime_confidence || 0.5;
  const isCascade = hawkesStage.is_cascade || false;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", color: "#fff", fontFamily: "Inter, sans-serif" }}>
      {/* ─── Header Section ─── */}
      <div className="glass-panel" style={{
        padding: "16px 24px", display: "flex", flexWrap: "wrap", justifyContent: "space-between",
        alignItems: "center", gap: "16px", borderRadius: "12px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <h2 className="brand-font" style={{
            margin: 0, fontSize: "22px", fontWeight: 800,
            background: "linear-gradient(135deg, #fff, #a1a1aa)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
          }}>
            AI Pipeline Intelligence
          </h2>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#a1a1aa" }}>
            <span className="live-dot" style={{ background: "#10b981" }} />
            <span>Auto-refreshing in {countdown}s</span>
          </div>
        </div>

        {/* Dropdowns / Pickers */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {/* Symbol Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", color: "#a1a1aa", fontWeight: 600 }}>Symbol:</span>
            <select
              value={activeSymbol}
              onChange={(e) => setActiveSymbol(e.target.value)}
              style={{
                background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: "6px", color: "#fff", padding: "6px 12px", fontSize: "13px", fontWeight: 600,
                outline: "none", cursor: "pointer"
              }}
            >
              {SYMBOLS.map((s) => <option key={s} value={s} style={{ background: "#0c0c0e" }}>{s}</option>)}
            </select>
          </div>

          {/* Interval Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", color: "#a1a1aa", fontWeight: 600 }}>Interval:</span>
            <div style={{ display: "flex", background: "rgba(255,255,255,0.04)", borderRadius: "6px", padding: "2px" }}>
              {INTERVALS.map((int) => (
                <button
                  key={int}
                  onClick={() => setActiveInterval(int)}
                  style={{
                    background: activeInterval === int ? "rgba(255,255,255,0.12)" : "transparent",
                    border: "none", borderRadius: "4px", color: activeInterval === int ? "#fff" : "#a1a1aa",
                    padding: "4px 10px", fontSize: "12px", fontWeight: 600, cursor: "pointer", transition: "all 0.2s"
                  }}
                >
                  {int}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ─── 10-Stage Pipeline Flow ─── */}
      <PipelineFlow
        stageLatencies={meta.stage_latencies}
        stageErrors={meta.errors}
        activeStage={loading ? 3 : 10}
      />

      {/* ─── AI Final Decision Panel ─── */}
      <AIDecisionPanel
        pipelineData={pipelineData}
        symbol={activeSymbol}
        loading={loading}
      />

      {/* ─── Grid Dashboard Area ─── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
        gap: "24px"
      }}>
        {/* A. Probability Command Center */}
        <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "20px" }}>
          <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff" }}>
            Probability Command Center
          </h4>
          <ProbabilityGauge
            pUp={probStage.p_up}
            pDown={probStage.p_down}
            pSideways={probStage.p_sideways}
            signal={probStage.signal}
            confidence={probStage.signal_confidence}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "12px" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ color: "#a1a1aa" }}>Kelly Fraction</span>
              <strong style={{ fontSize: "14px", color: "#3b82f6" }}>{Math.round(probStage.kelly_fraction * 100)}%</strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", alignItems: "flex-end" }}>
              <span style={{ color: "#a1a1aa" }}>Suggested Position Size</span>
              <strong style={{ fontSize: "14px", color: "#10b981" }}>{Math.round(probStage.suggested_position_size * 100)}%</strong>
            </div>
          </div>
        </div>

        {/* B. Regime Panel */}
        <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "20px" }}>
          <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff" }}>
            Regime Status Desk
          </h4>
          <div style={{ display: "flex", alignItems: "center", gap: "16px", padding: "16px", borderRadius: "8px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
            <div style={{ fontSize: "28px" }}>📈</div>
            <div>
              <div style={{ fontSize: "10px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Active Market State</div>
              <div style={{ fontSize: "18px", fontWeight: 800, color: "#fff", fontFamily: "Outfit" }}>
                {activeRegime.replace("_", " ")}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "12px" }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                <span style={{ color: "#a1a1aa" }}>Regime Transition Prob</span>
                <strong style={{ color: regimeStage.transition_probability > 0.5 ? "#f59e0b" : "#fff" }}>
                  {Math.round(regimeStage.transition_probability * 100)}%
                </strong>
              </div>
              <div style={{ width: "100%", height: "4px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", overflow: "hidden" }}>
                <div style={{ width: `${regimeStage.transition_probability * 100}%`, height: "100%", background: "#f59e0b", transition: "all 0.5s" }} />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#a1a1aa" }}>Regime Duration</span>
              <strong>{regimeStage.regime_duration_bars} bars</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#a1a1aa" }}>Likely Target Regime</span>
              <strong style={{ color: "#8b5cf6" }}>{regimeStage.transition_target?.replace("_", " ")}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#a1a1aa" }}>Meta Model Adaptation</span>
              <strong style={{ color: "#10b981" }}>{metaStage.adaptation_status}</strong>
            </div>
          </div>
        </div>

        {/* C. Model Weights & Bayesian Opinion Pool */}
        <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "20px" }}>
          <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff" }}>
            Bayesian Weights Pool
          </h4>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "12px", color: "#a1a1aa" }}>Model Agreement Score</span>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <strong style={{ fontSize: "14px" }}>{Math.round(fusionStage.model_agreement * 100)}%</strong>
              {fusionStage.conflict_alert && (
                <span className="glass-pill" style={{ background: "rgba(239, 44, 68, 0.15)", color: "#ef4444", border: "1px solid rgba(239,44,68,0.25)", fontSize: "9px", padding: "2px 6px" }}>
                  Conflict Alert
                </span>
              )}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "4px" }}>
            {fusionStage.model_weights && Object.entries(fusionStage.model_weights).map(([name, weight]) => (
              <div key={name} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", fontWeight: 600 }}>
                  <span style={{ color: name === fusionStage.dominant_model ? "#8b5cf6" : "#a1a1aa", textTransform: "capitalize" }}>
                    {name.replace("_", " ")} {name === fusionStage.dominant_model && "👑"}
                  </span>
                  <span>{Math.round(weight * 100)}%</span>
                </div>
                <div style={{ width: "100%", height: "4px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{ width: `${weight * 100}%`, height: "100%", background: name === fusionStage.dominant_model ? "#8b5cf6" : "#3b82f6", transition: "all 0.5s" }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ─── Bayesian Distribution Component ─── */}
      <BayesianDistribution
        distributionData={fusionStage.distribution_histogram}
        varValue={probStage.var_95}
        expectedReturn={probStage.expected_return}
        currentPrice={spotPrice}
      />

      {/* ─── Timeline Component ─── */}
      <RegimeTimeline
        regimeHistory={regimeStage.regime_history}
        currentRegime={activeRegime}
        confidence={confidence}
      />

      {/* ─── Detailed Statistics ─── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
        gap: "24px"
      }}>
        {/* Risk Metrics */}
        <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff", marginBottom: "4px" }}>
            Uncertainty & Risk Metrics
          </h4>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Value-at-Risk (VaR 95%)</span>
            <strong style={{ color: "#ef4444" }}>{(probStage.var_95 * 100).toFixed(2)}%</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Conditional VaR (CVaR 95%)</span>
            <strong style={{ color: "#ef4444" }}>{(probStage.cvar_95 * 100).toFixed(2)}%</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Tail Risk score (0-100)</span>
            <strong style={{ color: probStage.tail_risk_score > 30 ? "#f59e0b" : "#fff" }}>
              {probStage.tail_risk_score?.toFixed(1)}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Expected Return</span>
            <strong style={{ color: "#10b981" }}>{(probStage.expected_return * 100).toFixed(2)}%</strong>
          </div>
        </div>

        {/* Hawkes Event Clustering */}
        <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff", marginBottom: "4px" }}>
            Hawkes Event Cascading
          </h4>
          {isCascade && (
            <div className="glass-pill" style={{
              background: "rgba(239, 44, 68, 0.15)", color: "#ef4444", border: "1px solid rgba(239,44,68,0.25)",
              fontSize: "11px", fontWeight: 700, textAlign: "center", padding: "6px", borderRadius: "6px",
              animation: "dataBlink 1.5s infinite"
            }}>
              🚨 CASCADE DETECTED: EVENT MULTIPLICATION ACTIVE
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Excitation Intensity Ratio</span>
            <strong>{hawkesStage.excitation_ratio?.toFixed(2)}x</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Branching Ratio (Criticality)</span>
            <strong style={{ color: isCascade ? "#ef4444" : "#fff" }}>
              {hawkesStage.branching_ratio?.toFixed(3)}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Excitation Decay Halflife</span>
            <strong>{hawkesStage.decay_halflife_seconds?.toFixed(1)} s</strong>
          </div>
        </div>

        {/* Kalman State Estimation */}
        <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff", marginBottom: "4px" }}>
            Kalman State Estimation
          </h4>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>Estimated True Price</span>
            <strong>₹{spotPrice?.toFixed(2)}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>State Price Uncertainty</span>
            <strong>±₹{kalmanStage.price_uncertainty?.toFixed(2)}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>State Price Velocity (Momentum)</span>
            <strong style={{ color: kalmanStage.estimated_velocity > 0 ? "#10b981" : "#ef4444" }}>
              {kalmanStage.estimated_velocity > 0 ? "▲" : "▼"} ₹{Math.abs(kalmanStage.estimated_velocity)?.toFixed(3)} / bar
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
            <span style={{ color: "#a1a1aa" }}>State Acceleration (Forces)</span>
            <strong>{kalmanStage.estimated_acceleration?.toFixed(4)}</strong>
          </div>
        </div>
      </div>

      {/* ─── LLM Analyst Report ─── */}
      <div className="glass-panel" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "20px", borderRadius: "12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "14px" }}>
          <h3 className="brand-font" style={{ margin: 0, fontSize: "18px", fontWeight: 800, color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🧠</span> LLM Quantitative Analyst Report
          </h3>
          <span className="glass-pill" style={{
            background: reportStage.conviction_level === "HIGH" ? "rgba(16, 185, 129, 0.15)" : 
                        reportStage.conviction_level === "MEDIUM" ? "rgba(245, 158, 11, 0.15)" : "rgba(107, 114, 128, 0.15)",
            color: reportStage.conviction_level === "HIGH" ? "#10b981" : 
                   reportStage.conviction_level === "MEDIUM" ? "#f59e0b" : "#9ca3af",
            border: reportStage.conviction_level === "HIGH" ? "1px solid rgba(16,185,129,0.25)" : 
                    reportStage.conviction_level === "MEDIUM" ? "1px solid rgba(245,158,11,0.25)" : "1px solid rgba(107,114,128,0.25)",
            fontSize: "11px", fontWeight: 700, padding: "3px 10px"
          }}>
            {reportStage.conviction_level} CONVICTION
          </span>
        </div>

        {reportStage.headline ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <h4 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#3b82f6" }}>
              {reportStage.headline}
            </h4>
            <p style={{ margin: 0, fontSize: "13.5px", lineHeight: "1.6", color: "#e4e4e7" }}>
              {reportStage.summary}
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
              {/* Thesis */}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <strong style={{ fontSize: "12px", color: "#a1a1aa", textTransform: "uppercase" }}>Analytical Thesis</strong>
                <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.6", color: "#d4d4d8" }}>{reportStage.thesis}</p>
              </div>

              {/* Drivers & Risks */}
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div>
                  <strong style={{ fontSize: "12px", color: "#10b981", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Key Drivers</strong>
                  <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "12.5px", color: "#d4d4d8", display: "flex", flexDirection: "column", gap: "4px" }}>
                    {reportStage.key_drivers?.map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </div>
                <div>
                  <strong style={{ fontSize: "12px", color: "#ef4444", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Contrarian Risks</strong>
                  <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "12.5px", color: "#d4d4d8", display: "flex", flexDirection: "column", gap: "4px" }}>
                    {reportStage.contrarian_risks?.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              </div>
            </div>

            {/* Scenario Analysis */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "8px" }}>
              <strong style={{ fontSize: "12px", color: "#a1a1aa", textTransform: "uppercase" }}>Scenario & Catalysts Analysis</strong>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
                {/* Bull Case */}
                <div className="glass-panel" style={{ padding: "14px", background: "rgba(16, 185, 129, 0.02)", border: "1px solid rgba(16,185,129,0.12)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ fontWeight: 700, color: "#10b981", fontSize: "12px" }}>BULL CASE</span>
                    <span style={{ fontSize: "11px", fontWeight: 600 }}>{Math.round((reportStage.bull_case?.probability || 0) * 100)}%</span>
                  </div>
                  <div style={{ fontSize: "14px", fontWeight: 800, color: "#fff", marginBottom: "4px" }}>{reportStage.bull_case?.target}</div>
                  <div style={{ fontSize: "10px", color: "#a1a1aa" }}>
                    Catalysts: {reportStage.bull_case?.catalysts?.join(", ")}
                  </div>
                </div>

                {/* Base Case */}
                <div className="glass-panel" style={{ padding: "14px", background: "rgba(161, 161, 170, 0.02)", border: "1px solid rgba(161,161,170,0.12)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ fontWeight: 700, color: "#a1a1aa", fontSize: "12px" }}>BASE CASE</span>
                    <span style={{ fontSize: "11px", fontWeight: 600 }}>{Math.round((reportStage.base_case?.probability || 0) * 100)}%</span>
                  </div>
                  <div style={{ fontSize: "14px", fontWeight: 800, color: "#fff", marginBottom: "4px" }}>{reportStage.base_case?.target}</div>
                  <div style={{ fontSize: "10px", color: "#a1a1aa" }}>
                    Catalysts: {reportStage.base_case?.catalysts?.join(", ")}
                  </div>
                </div>

                {/* Bear Case */}
                <div className="glass-panel" style={{ padding: "14px", background: "rgba(239, 44, 68, 0.02)", border: "1px solid rgba(239,44,68,0.12)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <span style={{ fontWeight: 700, color: "#ef4444", fontSize: "12px" }}>BEAR CASE</span>
                    <span style={{ fontSize: "11px", fontWeight: 600 }}>{Math.round((reportStage.bear_case?.probability || 0) * 100)}%</span>
                  </div>
                  <div style={{ fontSize: "14px", fontWeight: 800, color: "#fff", marginBottom: "4px" }}>{reportStage.bear_case?.target}</div>
                  <div style={{ fontSize: "10px", color: "#a1a1aa" }}>
                    Catalysts: {reportStage.bear_case?.catalysts?.join(", ")}
                  </div>
                </div>
              </div>
            </div>

            {/* Tactical Execution Plan */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "16px", marginTop: "8px" }}>
              <strong style={{ fontSize: "12px", color: "#a1a1aa", textTransform: "uppercase" }}>Tactical Execution Plan</strong>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px", fontSize: "12.5px" }}>
                <div>Action: <strong style={{ color: "#3b82f6" }}>{reportStage.recommended_action}</strong></div>
                <div>Entry Zone: <strong>{reportStage.entry_zone}</strong></div>
                <div>Stop Loss: <strong style={{ color: "#ef4444" }}>{reportStage.stop_loss}</strong></div>
                <div>Targets: <strong style={{ color: "#10b981" }}>{reportStage.targets?.join(" • ")}</strong></div>
                <div>Timeframe: <strong>{reportStage.timeframe}</strong></div>
                <div>Sizing: <strong>{reportStage.position_sizing}</strong></div>
              </div>
            </div>

            {/* Warnings / Caveats */}
            {(reportStage.risk_warnings?.length > 0 || reportStage.confidence_caveats?.length > 0) && (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", background: "rgba(245, 158, 11, 0.03)", border: "1px solid rgba(245,158,11,0.1)", padding: "12px", borderRadius: "6px" }}>
                {reportStage.risk_warnings?.map((w, i) => (
                  <div key={i} style={{ fontSize: "11.5px", color: "#f59e0b", fontWeight: 500 }}>
                    {w}
                  </div>
                ))}
                {reportStage.confidence_caveats?.map((c, i) => (
                  <div key={i} style={{ fontSize: "11.5px", color: "#a1a1aa", fontWeight: 500 }}>
                    ℹ️ {c}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "20px", color: "#a1a1aa" }}>
            LLM Report not generated or loading
          </div>
        )}
      </div>
    </div>
  );
}
