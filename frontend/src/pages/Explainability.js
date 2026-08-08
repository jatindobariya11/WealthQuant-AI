import React, { useState, useEffect } from "react";
import { api } from "../api";

const SYMBOLS = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"];

export default function Explainability() {
  const [activeTab, setActiveTab] = useState("dashboard"); // 'dashboard', 'leaderboard', 'predictions'
  const [activeSymbol, setActiveSymbol] = useState("NIFTY");
  
  // State variables for endpoints
  const [summary, setSummary] = useState(null);
  const [contributions, setContributions] = useState([]);
  const [ablation, setAblation] = useState([]);
  const [regimePerf, setRegimePerf] = useState([]);
  const [drift, setDrift] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [predictions, setPredictions] = useState([]);
  
  // Pagination & limits
  const [predPage, setPredPage] = useState(1);
  const [leadPage, setLeadPage] = useState(1);
  const [limit] = useState(10);
  
  // Loading & Error states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchExplainabilityData = async (sym = activeSymbol, signal = undefined) => {
    setLoading(true);
    setError(null);
    try {
      // Fetch data based on active symbol and pagination
      const [sumData, contribData, abData, regData, driftData] = await Promise.all([
        api.getResearchSummary(sym, { signal }),
        api.getStageContributions(sym, 1, 50, { signal }),
        api.getAblationResults(sym, 1, 50, { signal }),
        api.getRegimePerformance(sym, 1, 50, { signal }),
        api.getFeatureDrift(sym, 1, 50, { signal })
      ]);
      
      setSummary(sumData);
      setContributions(contribData);
      setAblation(abData);
      setDrift(driftData);

      // Group regime performance by regime for easier grid rendering
      const groupedRegimes = {};
      if (regData && regData.length > 0) {
        regData.forEach(r => {
          if (!groupedRegimes[r.regime]) {
            groupedRegimes[r.regime] = [];
          }
          groupedRegimes[r.regime].push(r);
        });
      }
      setRegimePerf(groupedRegimes);

    } catch (err) {
      if (err.name === 'CanceledError' || err.name === 'AbortError' || err.code === 'ERR_CANCELED') return;
      console.error("Failed to load explainability data:", err);
      setError("Failed to retrieve explainability reports. Verify backend connection.");
    } finally {
      setLoading(false);
    }
  };

  const fetchLeaderboard = async (page = leadPage, signal = undefined) => {
    try {
      const data = await api.getAlphaLeaderboard(page, limit, { signal });
      setLeaderboard(data);
    } catch (err) {
      if (err.name === 'CanceledError' || err.name === 'AbortError' || err.code === 'ERR_CANCELED') return;
      console.error("Failed to load leaderboard:", err);
    }
  };

  const fetchPredictions = async (sym = activeSymbol, page = predPage, signal = undefined) => {
    try {
      const data = await api.getSignalExplanations(sym, "", "", page, limit, { signal });
      setPredictions(data);
    } catch (err) {
      if (err.name === 'CanceledError' || err.name === 'AbortError' || err.code === 'ERR_CANCELED') return;
      console.error("Failed to load prediction explanations:", err);
    }
  };

  // Re-run on active tab or symbol change
  useEffect(() => {
    const controller = new AbortController();
    if (activeTab === "dashboard") {
      fetchExplainabilityData(activeSymbol, controller.signal);
    } else if (activeTab === "leaderboard") {
      fetchLeaderboard(leadPage, controller.signal);
    } else if (activeTab === "predictions") {
      fetchPredictions(activeSymbol, predPage, controller.signal);
    }
    return () => controller.abort();
  }, [activeTab, activeSymbol, leadPage, predPage]);

  // Handle retry
  const handleRetry = () => {
    if (activeTab === "dashboard") fetchExplainabilityData(activeSymbol);
    else if (activeTab === "leaderboard") fetchLeaderboard(leadPage);
    else fetchPredictions(activeSymbol, predPage);
  };

  const renderBadge = (status) => {
    const s = status ? status.toUpperCase() : "NEUTRAL";
    let color = "#f59e0b";
    let bg = "rgba(245, 158, 11, 0.15)";
    let border = "1px solid rgba(245, 158, 11, 0.25)";

    if (s === "HELPING" || s === "TRUE" || s === "STABLE") {
      color = "#10b981";
      bg = "rgba(16, 185, 129, 0.15)";
      border = "1px solid rgba(16, 185, 129, 0.25)";
    } else if (s === "HURTING" || s === "FALSE" || s === "DRIFTED" || s === "DECAYED") {
      color = "#ef4444";
      bg = "rgba(239, 68, 68, 0.15)";
      border = "1px solid rgba(239, 68, 68, 0.25)";
    }

    return (
      <span className="glass-pill" style={{
        color, background: bg, border,
        fontSize: "10px", fontWeight: 700, padding: "2px 8px", borderRadius: "999px",
        textTransform: "uppercase", display: "inline-block"
      }}>
        {s}
      </span>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", color: "#fff", fontFamily: "Inter, sans-serif" }}>
      
      {/* ─── HEADER BAR ─── */}
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
            Explainability & Alpha Discovery
          </h2>
          <div style={{ display: "flex", background: "rgba(255,255,255,0.04)", borderRadius: "8px", padding: "2px" }}>
            <button
              onClick={() => setActiveTab("dashboard")}
              style={{
                background: activeTab === "dashboard" ? "rgba(255,255,255,0.08)" : "transparent",
                border: "none", borderRadius: "6px", color: activeTab === "dashboard" ? "#fff" : "#a1a1aa",
                padding: "6px 14px", fontSize: "13px", fontWeight: 600, cursor: "pointer", transition: "all 0.2s"
              }}
            >
              🔬 Research Summary
            </button>
            <button
              onClick={() => setActiveTab("leaderboard")}
              style={{
                background: activeTab === "leaderboard" ? "rgba(255,255,255,0.08)" : "transparent",
                border: "none", borderRadius: "6px", color: activeTab === "leaderboard" ? "#fff" : "#a1a1aa",
                padding: "6px 14px", fontSize: "13px", fontWeight: 600, cursor: "pointer", transition: "all 0.2s"
              }}
            >
              🏆 Alpha Leaderboard
            </button>
            <button
              onClick={() => setActiveTab("predictions")}
              style={{
                background: activeTab === "predictions" ? "rgba(255,255,255,0.08)" : "transparent",
                border: "none", borderRadius: "6px", color: activeTab === "predictions" ? "#fff" : "#a1a1aa",
                padding: "6px 14px", fontSize: "13px", fontWeight: 600, cursor: "pointer", transition: "all 0.2s"
              }}
            >
              📋 Predictions Audit Log
            </button>
          </div>
        </div>

        {/* Symbol Selector (Disabled on Leaderboard tab) */}
        {activeTab !== "leaderboard" && (
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
        )}
      </div>

      {/* ─── ERROR STATE ─── */}
      {error && (
        <div className="glass-panel" style={{ padding: "30px", textAlign: "center", color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
          <h4 style={{ margin: 0, color: "#ef4444" }}>Research Pipeline Offline</h4>
          <p style={{ color: "#a1a1aa", fontSize: "13px", margin: 0 }}>{error}</p>
          <button onClick={handleRetry} style={{ background: "linear-gradient(135deg, #3b82f6, #8b5cf6)", color: "#fff", border: "none", padding: "8px 20px", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}>
            Retry Connection
          </button>
        </div>
      )}

      {/* ─── LOADING STATE ─── */}
      {loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <div className="glass-panel skeleton-pulse" style={{ height: "120px", width: "100%" }} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
            <div className="glass-panel skeleton-pulse" style={{ height: "250px" }} />
            <div className="glass-panel skeleton-pulse" style={{ height: "250px" }} />
          </div>
        </div>
      )}

      {/* ─── TAB CONTENT: RESEARCH SUMMARY & DASHBOARD ─── */}
      {!loading && !error && activeTab === "dashboard" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          {/* 1. Research Analytics Summary Panel */}
          {summary && (
            <div className="glass-panel" style={{ padding: "20px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "11px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Best Performing Stage</span>
                <strong style={{ fontSize: "16px", color: "#10b981" }}>🥇 {summary.best_stage}</strong>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "11px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Worst Performing Stage</span>
                <strong style={{ fontSize: "16px", color: "#ef4444" }}>💀 {summary.worst_stage}</strong>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "11px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Best Market Regime</span>
                <strong style={{ fontSize: "16px", color: "#8b5cf6" }}>📈 {summary.best_regime.replace("_", " ")}</strong>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "11px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Worst Market Regime</span>
                <strong style={{ fontSize: "16px", color: "#f59e0b" }}>📉 {summary.worst_regime.replace("_", " ")}</strong>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "11px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Highest Drift Indicator</span>
                <strong style={{ fontSize: "16px", color: "#3b82f6" }}>⚠️ {summary.highest_drift_feature}</strong>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "11px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Ablation Significance</span>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <strong style={{ fontSize: "14px" }}>p={summary.latest_p_value}</strong>
                  {renderBadge(summary.edge_significant ? "STABLE" : "NEUTRAL")}
                </div>
              </div>
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(480px, 1fr))", gap: "24px" }}>
            
            {/* 2. Stage Contributions */}
            <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Stage Contribution Audit</h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", color: "#a1a1aa" }}>
                      <th style={{ padding: "10px 8px" }}>Mathematical Stage</th>
                      <th style={{ padding: "10px 8px" }}>Directional Accuracy</th>
                      <th style={{ padding: "10px 8px" }}>Pearson Corr</th>
                      <th style={{ padding: "10px 8px" }}>MAE</th>
                      <th style={{ padding: "10px 8px" }}>Sharpe Contribution</th>
                      <th style={{ padding: "10px 8px" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contributions.map((row, idx) => (
                      <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                        <td style={{ padding: "12px 8px", fontWeight: 600 }}>{row.stage}</td>
                        <td style={{ padding: "12px 8px" }}>{row.accuracy ? `${(row.accuracy * 100).toFixed(1)}%` : "N/A"}</td>
                        <td style={{ padding: "12px 8px", color: row.correlation > 0 ? "#10b981" : "#ef4444" }}>
                          {row.correlation ? row.correlation.toFixed(4) : "0.0000"}
                        </td>
                        <td style={{ padding: "12px 8px" }}>{row.mae ? row.mae.toFixed(5) : "N/A"}</td>
                        <td style={{ padding: "12px 8px" }}>{row.sharpe_contribution ? row.sharpe_contribution.toFixed(2) : "0.0"}</td>
                        <td style={{ padding: "12px 8px" }}>{renderBadge(row.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 3. Ablation Testing Framework */}
            <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Ablation Analysis</h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", color: "#a1a1aa" }}>
                      <th style={{ padding: "10px 8px" }}>Configuration Removed</th>
                      <th style={{ padding: "10px 8px" }}>Sharpe</th>
                      <th style={{ padding: "10px 8px" }}>Sortino</th>
                      <th style={{ padding: "10px 8px" }}>Profit Factor</th>
                      <th style={{ padding: "10px 8px" }}>Win Rate</th>
                      <th style={{ padding: "10px 8px" }}>p-value vs Full</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ablation.map((row, idx) => (
                      <tr key={idx} style={{
                        borderBottom: "1px solid rgba(255,255,255,0.04)",
                        background: row.configuration === "Full System" ? "rgba(139, 92, 246, 0.05)" : "transparent"
                      }}>
                        <td style={{ padding: "12px 8px", fontWeight: row.configuration === "Full System" ? 700 : 600, color: row.configuration === "Full System" ? "#8b5cf6" : "#fff" }}>
                          {row.configuration} {row.configuration === "Full System" && "✨"}
                        </td>
                        <td style={{ padding: "12px 8px" }}>{row.sharpe ? row.sharpe.toFixed(2) : "N/A"}</td>
                        <td style={{ padding: "12px 8px" }}>{row.sortino ? row.sortino.toFixed(2) : "N/A"}</td>
                        <td style={{ padding: "12px 8px" }}>{row.profit_factor ? row.profit_factor.toFixed(2) : "N/A"}</td>
                        <td style={{ padding: "12px 8px" }}>{row.win_rate ? `${(row.win_rate * 100).toFixed(1)}%` : "N/A"}</td>
                        <td style={{ padding: "12px 8px", fontWeight: 600 }}>
                          {row.configuration === "Full System" ? "-" : row.p_value.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 4. Regime Attribution */}
            <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Market State / Regime Attribution</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {Object.keys(regimePerf).map((regime, rIdx) => (
                  <div key={rIdx} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)", borderRadius: "8px", padding: "14px" }}>
                    <h4 style={{ margin: "0 0 10px 0", fontSize: "14px", color: "#8b5cf6", textTransform: "capitalize" }}>
                      🎭 {regime.replace("_", " ")} Regime
                    </h4>
                    <div style={{ overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", color: "#a1a1aa" }}>
                            <th style={{ padding: "6px 4px" }}>Mathematical Stage</th>
                            <th style={{ padding: "6px 4px" }}>Directional Accuracy</th>
                            <th style={{ padding: "6px 4px" }}>Pearson Correlation</th>
                            <th style={{ padding: "6px 4px" }}>MAE</th>
                          </tr>
                        </thead>
                        <tbody>
                          {regimePerf[regime].map((row, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
                              <td style={{ padding: "8px 4px", fontWeight: 600 }}>{row.stage}</td>
                              <td style={{ padding: "8px 4px" }}>{row.accuracy ? `${(row.accuracy * 100).toFixed(1)}%` : "N/A"}</td>
                              <td style={{ padding: "8px 4px", color: row.correlation > 0 ? "#10b981" : "#ef4444" }}>
                                {row.correlation ? row.correlation.toFixed(4) : "0.0000"}
                              </td>
                              <td style={{ padding: "8px 4px" }}>{row.mae ? row.mae.toFixed(5) : "N/A"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 5. Feature Drift Monitor */}
            <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Technical Feature Drift Monitor</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {drift.map((feat, idx) => (
                  <div key={idx} style={{
                    display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center",
                    padding: "12px 16px", borderRadius: "8px", background: "rgba(255,255,255,0.02)",
                    border: feat.is_drifted ? "1px solid rgba(239, 68, 68, 0.25)" : "1px solid rgba(255,255,255,0.04)"
                  }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                      <strong style={{ fontSize: "14px" }}>{feat.feature_name}</strong>
                      <div style={{ fontSize: "11px", color: "#a1a1aa" }}>
                        Baseline Mean: {feat.baseline_mean?.toFixed(2)} | Recent Mean: {feat.recent_mean?.toFixed(2)}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: "10px", color: "#a1a1aa", textTransform: "uppercase", fontWeight: 600 }}>Drift Z-Score</div>
                        <strong style={{ fontSize: "14px", color: feat.drift_score > 2.0 ? "#ef4444" : "#fff" }}>
                          {feat.drift_score?.toFixed(2)}
                        </strong>
                      </div>
                      {renderBadge(feat.is_drifted ? "DRIFTED" : "STABLE")}
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ─── TAB CONTENT: ALPHA LEADERBOARD ─── */}
      {!loading && !error && activeTab === "leaderboard" && (
        <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "20px" }}>
          <div>
            <h3 style={{ margin: "0 0 6px 0", fontSize: "18px", fontWeight: 700 }}>Alpha Leaderboard</h3>
            <p style={{ margin: 0, fontSize: "13px", color: "#a1a1aa" }}>
              Ranked comparison of quant strategies, validation folds, and ablation experiments across global performance metrics.
            </p>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", color: "#a1a1aa" }}>
                  <th style={{ padding: "12px 10px" }}>Rank & Name</th>
                  <th style={{ padding: "12px 10px" }}>Type</th>
                  <th style={{ padding: "12px 10px" }}>Sharpe Ratio</th>
                  <th style={{ padding: "12px 10px" }}>Sortino Ratio</th>
                  <th style={{ padding: "12px 10px" }}>Profit Factor</th>
                  <th style={{ padding: "12px 10px" }}>Win Rate</th>
                  <th style={{ padding: "12px 10px" }}>Max Drawdown</th>
                  <th style={{ padding: "12px 10px" }}>p-value vs Baseline</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((row, idx) => (
                  <tr key={idx} style={{
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                    background: idx === 0 ? "rgba(16, 185, 129, 0.03)" : "transparent"
                  }}>
                    <td style={{ padding: "16px 10px", fontWeight: 600 }}>
                      <span style={{ marginRight: "10px", color: idx === 0 ? "#10b981" : "#a1a1aa" }}>
                        {idx + 1 + (leadPage - 1) * limit}.
                      </span>
                      {row.name} {idx === 0 && "👑"}
                    </td>
                    <td style={{ padding: "16px 10px" }}>
                      <span style={{
                        fontSize: "10px", textTransform: "uppercase", padding: "2px 6px", borderRadius: "4px",
                        background: row.type === "strategy" ? "rgba(59, 130, 246, 0.15)" : (row.type === "experiment" ? "rgba(139, 92, 246, 0.15)" : "rgba(245, 158, 11, 0.15)"),
                        color: row.type === "strategy" ? "#3b82f6" : (row.type === "experiment" ? "#8b5cf6" : "#f59e0b"),
                        fontWeight: 700
                      }}>
                        {row.type}
                      </span>
                    </td>
                    <td style={{ padding: "16px 10px", fontWeight: 700, color: "#10b981" }}>{row.sharpe ? row.sharpe.toFixed(2) : "0.00"}</td>
                    <td style={{ padding: "16px 10px" }}>{row.sortino ? row.sortino.toFixed(2) : "0.00"}</td>
                    <td style={{ padding: "16px 10px" }}>{row.profit_factor ? row.profit_factor.toFixed(2) : "1.00"}</td>
                    <td style={{ padding: "16px 10px" }}>{row.win_rate ? `${(row.win_rate * 100).toFixed(1)}%` : "N/A"}</td>
                    <td style={{ padding: "16px 10px", color: "#ef4444" }}>{row.max_drawdown ? `${(row.max_drawdown * 100).toFixed(1)}%` : "0.0%"}</td>
                    <td style={{ padding: "16px 10px", fontWeight: 600 }}>
                      {row.p_value !== undefined && row.p_value !== 1.0 ? row.p_value.toFixed(4) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Leaderboard Pagination */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "14px" }}>
            <span style={{ fontSize: "12px", color: "#a1a1aa" }}>Showing page {leadPage}</span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                disabled={leadPage === 1}
                onClick={() => setLeadPage(p => Math.max(1, p - 1))}
                style={{
                  background: "rgba(255,255,255,0.06)", color: leadPage === 1 ? "#555" : "#fff",
                  border: "none", padding: "6px 12px", borderRadius: "4px", fontSize: "12px",
                  fontWeight: 600, cursor: leadPage === 1 ? "not-allowed" : "pointer"
                }}
              >
                ◀ Previous
              </button>
              <button
                disabled={leaderboard.length < limit}
                onClick={() => setLeadPage(p => p + 1)}
                style={{
                  background: "rgba(255,255,255,0.06)", color: leaderboard.length < limit ? "#555" : "#fff",
                  border: "none", padding: "6px 12px", borderRadius: "4px", fontSize: "12px",
                  fontWeight: 600, cursor: leaderboard.length < limit ? "not-allowed" : "pointer"
                }}
              >
                Next ▶
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB CONTENT: PREDICTIONS AUDIT LOG ─── */}
      {!loading && !error && activeTab === "predictions" && (
        <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "20px" }}>
          <div>
            <h3 style={{ margin: "0 0 6px 0", fontSize: "18px", fontWeight: 700 }}>Predictions Audit Log</h3>
            <p style={{ margin: 0, fontSize: "13px", color: "#a1a1aa" }}>
              Live audit timeline of registered signals, model weights agreement, capital allocation ratios, and post-hoc evaluated returns.
            </p>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", color: "#a1a1aa" }}>
                  <th style={{ padding: "10px 8px" }}>Prediction Time</th>
                  <th style={{ padding: "10px 8px" }}>Spot Price</th>
                  <th style={{ padding: "10px 8px" }}>Estimators (K/P/E/F)</th>
                  <th style={{ padding: "10px 8px" }}>Regime</th>
                  <th style={{ padding: "10px 8px" }}>Signal & Conf</th>
                  <th style={{ padding: "10px 8px" }}>Kelly Sizing</th>
                  <th style={{ padding: "10px 8px" }}>Actual Return</th>
                  <th style={{ padding: "10px 8px" }}>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
                    <td style={{ padding: "12px 8px", whiteSpace: "nowrap" }}>
                      {row.timestamp ? new Date(row.timestamp).toLocaleString() : "N/A"}
                    </td>
                    <td style={{ padding: "12px 8px", fontWeight: 600 }}>
                      {row.spot_price ? row.spot_price.toLocaleString("en-IN", { style: "currency", currency: "INR" }) : "N/A"}
                    </td>
                    <td style={{ padding: "12px 8px" }}>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <span title="Kalman Velocity" style={{ color: "#3b82f6" }}>K:{row.kalman_velocity?.toFixed(2) || "0"}</span>
                        <span title="Particle Mean" style={{ color: "#10b981" }}>P:{row.particle_mean?.toFixed(1) || "0"}</span>
                        <span title="Ensemble prediction" style={{ color: "#f59e0b" }}>E:{row.ensemble_prediction?.toFixed(4) || "0"}</span>
                        <span title="Fusion mean" style={{ color: "#8b5cf6" }}>F:{row.fusion_mean?.toFixed(4) || "0"}</span>
                      </div>
                    </td>
                    <td style={{ padding: "12px 8px", textTransform: "capitalize" }}>
                      {row.regime_state?.replace("_", " ").toLowerCase()}
                    </td>
                    <td style={{ padding: "12px 8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <strong>{row.signal}</strong>
                        <span style={{ color: "#a1a1aa" }}>({Math.round(row.signal_confidence * 100)}%)</span>
                      </div>
                    </td>
                    <td style={{ padding: "12px 8px", fontWeight: 600, color: "#3b82f6" }}>
                      {row.kelly_fraction ? `${(row.kelly_fraction * 100).toFixed(1)}%` : "0.0%"}
                    </td>
                    <td style={{ padding: "12px 8px", color: row.actual_return > 0 ? "#10b981" : (row.actual_return < 0 ? "#ef4444" : "#fff") }}>
                      {row.actual_return ? `${(row.actual_return * 100).toFixed(2)}%` : "-"}
                    </td>
                    <td style={{ padding: "12px 8px" }}>
                      {row.actual_return !== null ? renderBadge(row.correct ? "STABLE" : "HURTING") : renderBadge("NEUTRAL")}
                    </td>
                  </tr>
                ))}
                {predictions.length === 0 && (
                  <tr>
                    <td colSpan={8} style={{ padding: "30px", textAlign: "center", color: "#a1a1aa" }}>
                      No registered signal explanations found for {activeSymbol}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Predictions Pagination */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "14px" }}>
            <span style={{ fontSize: "12px", color: "#a1a1aa" }}>Showing page {predPage}</span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                disabled={predPage === 1}
                onClick={() => setPredPage(p => Math.max(1, p - 1))}
                style={{
                  background: "rgba(255,255,255,0.06)", color: predPage === 1 ? "#555" : "#fff",
                  border: "none", padding: "6px 12px", borderRadius: "4px", fontSize: "12px",
                  fontWeight: 600, cursor: predPage === 1 ? "not-allowed" : "pointer"
                }}
              >
                ◀ Previous
              </button>
              <button
                disabled={predictions.length < limit}
                onClick={() => setPredPage(p => p + 1)}
                style={{
                  background: "rgba(255,255,255,0.06)", color: predictions.length < limit ? "#555" : "#fff",
                  border: "none", padding: "6px 12px", borderRadius: "4px", fontSize: "12px",
                  fontWeight: 600, cursor: predictions.length < limit ? "not-allowed" : "pointer"
                }}
              >
                Next ▶
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
