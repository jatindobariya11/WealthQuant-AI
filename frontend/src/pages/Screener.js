import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const C = {
  bg: "#050505", panel: "rgba(18, 18, 22, 0.65)", hover: "rgba(30, 30, 36, 0.85)",
  border: "rgba(255, 255, 255, 0.08)", text: "#fff", muted: "#9ca3af",
  blue: "#3b82f6", green: "#10b981", red: "#ef4444", yellow: "#f59e0b", purple: "#8b5cf6"
};

const SIG_STYLE = {
  BUY:  { background: "rgba(16,185,129,0.15)", color: C.green, border: `1px solid ${C.green}40` },
  SELL: { background: "rgba(239,68,68,0.15)",  color: C.red,   border: `1px solid ${C.red}40` },
  WAIT: { background: "rgba(255,255,255,0.05)", color: C.muted, border: `1px solid ${C.border}` },
};

export default function Screener() {
  const [data,    setData]    = useState(null);
  const [filter,  setFilter]  = useState("all");
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState("score");
  const [sortAsc, setSortAsc] = useState(false);
  const [hoveredSec, setHoveredSec] = useState(null);
  const [selectedSector, setSelectedSector] = useState(null);
  const navigate = useNavigate();

  const runScan = useCallback(() => {
    setLoading(true);
    api.getScreener()
       // FIX: was .then(r => setData(r.data)) — axios already unwraps .data
       .then(r => setData(r))
       .catch(() => setData(null))
       .finally(() => setLoading(false));
  }, []);

  // Auto-run on mount
  useEffect(() => { runScan(); }, [runScan]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const stocks = (data?.stocks || [])
    .filter(s => filter === "all" ? true : s.signal === filter)
    .filter(s => selectedSector ? s.sector === selectedSector : true)
    .sort((a, b) => {
      const av = a[sortKey] ?? "";
      const bv = b[sortKey] ?? "";
      if (typeof av === "string" && typeof bv === "string") {
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortAsc ? av - bv : bv - av;
    });

  const SortHeader = ({ label, dataKey }) => (
    <th
      onClick={() => handleSort(dataKey)}
      style={{
        padding: "12px 14px", textAlign: "left", fontSize: "0.7rem", color: C.muted,
        fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em",
        cursor: "pointer", userSelect: "none", whiteSpace: "nowrap",
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      {label} {sortKey === dataKey ? (sortAsc ? "▲" : "▼") : ""}
    </th>
  );

  return (
    <div style={{ maxWidth: "1600px", margin: "0 auto" }}>
      {/* Header */}
      <div className="animate-fade-in" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h2 className="brand-font" style={{ fontWeight: 700, margin: 0, fontSize: "1.8rem" }}>
            Nifty 50 Screener
          </h2>
          <p style={{ color: C.muted, fontSize: "0.85rem", marginTop: "4px" }}>
            AI-powered stock scanner • {data ? `${data.summary?.total || 0} of ${data.summary?.scanned || 50} stocks loaded` : "Click scan to begin"}
            {data && (data.summary?.failed || 0) > 0 && (
              <span style={{ color: C.yellow, marginLeft: "8px", fontSize: "0.75rem" }}>
                ⚠ {data.summary.failed} stocks unavailable
              </span>
            )}
          </p>
        </div>
        <button onClick={runScan}
          className="glass-panel"
          style={{
            padding: "10px 24px", borderRadius: 12, border: `1px solid ${C.blue}40`,
            background: loading ? "rgba(59,130,246,0.1)" : "rgba(59,130,246,0.2)",
            color: C.blue, fontSize: 14, fontWeight: 600,
          }}>
          {loading ? "⟳ Scanning..." : "⚡ Scan Now"}
        </button>
      </div>

      {/* Loading State */}
      {loading && !data && (
        <div className="glass-panel animate-fade-in" style={{ padding: "3rem", textAlign: "center" }}>
          <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>📊</div>
          <p style={{ color: C.muted, fontSize: "0.9rem" }}>
            Scanning all 50 Nifty stocks... This should take about 5-10 seconds.
          </p>
          <div style={{ width: "200px", height: "4px", background: C.border, borderRadius: "2px", margin: "1rem auto", overflow: "hidden" }}>
            <div style={{
              width: "40%", height: "100%", background: `linear-gradient(90deg, ${C.blue}, ${C.purple})`,
              borderRadius: "2px", animation: "shimmer 1.5s ease-in-out infinite",
            }} />
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {data && !loading && (
        <>
          <div className="animate-fade-in" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
            {[
              { k: "all",  label: "Total",   count: data.summary?.total || 0, color: C.blue,   icon: "📊" },
              { k: "BUY",  label: "BUY",     count: data.summary?.buy || 0,   color: C.green,  icon: "🟢" },
              { k: "SELL", label: "SELL",     count: data.summary?.sell || 0,  color: C.red,    icon: "🔴" },
              { k: "WAIT", label: "WAIT",     count: data.summary?.wait || 0,  color: C.yellow, icon: "🟡" },
            ].map(f => (
              <div
                key={f.k}
                onClick={() => setFilter(f.k)}
                className="glass-panel"
                style={{
                  padding: "1rem 1.2rem", cursor: "pointer",
                  border: filter === f.k ? `1px solid ${f.color}60` : `1px solid ${C.border}`,
                  background: filter === f.k ? `${f.color}10` : C.panel,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.75rem", color: C.muted, fontWeight: 600, textTransform: "uppercase" }}>{f.label}</span>
                  <span>{f.icon}</span>
                </div>
                <div className="brand-font" style={{ fontSize: "2rem", fontWeight: 800, color: f.color, marginTop: "4px" }}>
                  {f.count}
                </div>
              </div>
            ))}
          </div>

          {/* Sector Heatmap */}
          {data.sectors && data.sectors.length > 0 && (
            <div className="glass-panel animate-fade-in" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <h3 className="brand-font" style={{ fontSize: "0.85rem", color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em", margin: 0 }}>
                  Sector Momentum Heatmap
                </h3>
                <span style={{ fontSize: "0.75rem", color: C.muted }}>
                  Size represents stock count • Color intensity represents momentum score
                </span>
              </div>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                gap: "1rem"
              }}>
                {data.sectors.map(sec => {
                  const score = sec.avg_score;
                  const isHovered = hoveredSec === sec.sector;
                  const isSelected = selectedSector === sec.sector;
                  
                  // Calculate dynamic colors based on avg_score intensity (-10 to 10)
                  let bg = "rgba(255, 255, 255, 0.03)";
                  let border = isSelected ? `2px solid ${C.blue}` : "1px solid rgba(255, 255, 255, 0.08)";
                  let shadow = isSelected ? `0 0 16px ${C.blue}40` : "none";
                  let scoreColor = C.muted;

                  if (score > 0) {
                    const intensity = 0.05 + (score / 10) * 0.25;
                    bg = `rgba(16, 185, 129, ${isHovered || isSelected ? intensity + 0.1 : intensity})`;
                    if (!isSelected) {
                      border = `1px solid rgba(16, 185, 129, ${0.15 + (score / 10) * 0.35})`;
                    }
                    scoreColor = C.green;
                    if (isHovered && !isSelected) {
                      shadow = `0 8px 24px rgba(16, 185, 129, ${0.1 + (score / 10) * 0.15})`;
                    }
                  } else if (score < 0) {
                    const intensity = 0.05 + (Math.abs(score) / 10) * 0.25;
                    bg = `rgba(239, 68, 68, ${isHovered || isSelected ? intensity + 0.1 : intensity})`;
                    if (!isSelected) {
                      border = `1px solid rgba(239, 68, 68, ${0.15 + (Math.abs(score) / 10) * 0.35})`;
                    }
                    scoreColor = C.red;
                    if (isHovered && !isSelected) {
                      shadow = `0 8px 24px rgba(239, 68, 68, ${0.1 + (Math.abs(score) / 10) * 0.15})`;
                    }
                  } else {
                    if (isHovered && !isSelected) {
                      bg = "rgba(255, 255, 255, 0.06)";
                      border = "1px solid rgba(255, 255, 255, 0.15)";
                      shadow = "0 8px 24px rgba(255, 255, 255, 0.05)";
                    }
                  }

                  const waits = sec.count - sec.buy - sec.sell;

                  return (
                    <div
                      key={sec.sector}
                      onMouseEnter={() => setHoveredSec(sec.sector)}
                      onMouseLeave={() => setHoveredSec(null)}
                      onClick={() => setSelectedSector(isSelected ? null : sec.sector)}
                      style={{
                        padding: "1.2rem",
                        borderRadius: "14px",
                        background: bg,
                        border: border,
                        boxShadow: shadow,
                        transform: isHovered ? "translateY(-4px)" : "none",
                        transition: "all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)",
                        cursor: "pointer",
                        position: "relative",
                        overflow: "hidden"
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", position: "relative", zIndex: 1 }}>
                        <div>
                          <div style={{ fontSize: "1rem", fontWeight: 700, color: C.text }}>
                            {sec.sector}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: C.muted, marginTop: "2px" }}>
                            {sec.count} {sec.count === 1 ? "stock" : "stocks"}
                          </div>
                        </div>
                        <div style={{
                          padding: "4px 8px",
                          borderRadius: "8px",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          background: "rgba(0,0,0,0.2)",
                          color: scoreColor,
                          border: `1px solid ${border}`
                        }}>
                          {score > 0 ? "+" : ""}{score.toFixed(1)}
                        </div>
                      </div>

                      {/* Tri-Color Distribution Progress Bar */}
                      <div style={{ display: "flex", height: "5px", background: "rgba(255,255,255,0.05)", borderRadius: "3px", overflow: "hidden", marginTop: "1.2rem", marginBottom: "0.6rem", position: "relative", zIndex: 1 }}>
                        {sec.buy > 0 && <div style={{ width: `${(sec.buy / sec.count) * 100}%`, background: C.green }} />}
                        {waits > 0 && <div style={{ width: `${(waits / sec.count) * 100}%`, background: "rgba(255,255,255,0.15)" }} />}
                        {sec.sell > 0 && <div style={{ width: `${(sec.sell / sec.count) * 100}%`, background: C.red }} />}
                      </div>

                      {/* Signals Count Labels */}
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: C.muted, fontWeight: 500, position: "relative", zIndex: 1 }}>
                        <span style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                          <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: C.green }} />
                          {sec.buy} Buy
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                          <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: "rgba(255,255,255,0.3)" }} />
                          {waits} Wait
                        </span>
                        <span style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                          <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: C.red }} />
                          {sec.sell} Sell
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Active Filters Display */}
          {selectedSector && (
            <div className="animate-fade-in" style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "0.8rem" }}>
              <span style={{ fontSize: "0.8rem", color: C.muted }}>Active Filter:</span>
              <span style={{
                display: "inline-flex", alignItems: "center", gap: "6px",
                padding: "4px 12px", borderRadius: "20px", background: "rgba(59,130,246,0.15)",
                color: C.blue, border: `1px solid ${C.blue}40`, fontSize: "0.8rem", fontWeight: 600
              }}>
                Sector: {selectedSector}
                <button
                  onClick={() => setSelectedSector(null)}
                  style={{
                    background: "none", border: "none", color: C.blue, cursor: "pointer",
                    padding: 0, fontSize: "0.9rem", fontWeight: 700, marginLeft: "4px",
                    lineHeight: 1
                  }}
                >
                  ✕
                </button>
              </span>
              <button
                onClick={() => setSelectedSector(null)}
                style={{
                  background: "none", border: "none", color: C.muted, cursor: "pointer",
                  fontSize: "0.75rem", textDecoration: "underline", padding: 0
                }}
              >
                Clear sector filter
              </button>
            </div>
          )}

          {/* Stock Table */}
          <div className="glass-panel animate-fade-in-delayed" style={{ overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr>
                  <SortHeader label="Stock" dataKey="name" />
                  <SortHeader label="Sector" dataKey="sector" />
                  <SortHeader label="Price" dataKey="price" />
                  <SortHeader label="Score" dataKey="score" />
                  <SortHeader label="RSI" dataKey="rsi" />
                  <SortHeader label="Setup" dataKey="breakout_structure" />
                  <SortHeader label="VWAP" dataKey="vwap_confirmation" />
                  <SortHeader label="PCR" dataKey="pcr" />
                  <SortHeader label="OI Buildup" dataKey="oi_buildup" />
                  <SortHeader label="Change" dataKey="chg_pct" />
                  <th style={{ padding: "12px 14px", textAlign: "left", fontSize: "0.7rem", color: C.muted, fontWeight: 600, textTransform: "uppercase", borderBottom: `1px solid ${C.border}` }}>Signal</th>
                </tr>
              </thead>
              <tbody>
                {stocks.map((s, i) => (
                  <tr key={s.symbol}
                    onClick={() => navigate(`/stock/${s.symbol}`)}
                    style={{
                      borderBottom: `1px solid ${C.border}`, cursor: "pointer",
                      transition: "background 0.2s",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "rgba(59,130,246,0.05)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                    <td style={{ padding: "12px 14px", fontWeight: 600 }}>{s.name}</td>
                    <td style={{ padding: "12px 14px", color: C.muted, fontSize: "0.8rem" }}>{s.sector}</td>
                    <td style={{ padding: "12px 14px", fontWeight: 500, fontFamily: "Outfit" }}>₹{s.price?.toLocaleString("en-IN")}</td>
                    <td style={{ padding: "12px 14px", fontWeight: 700,
                      color: s.score > 0 ? C.green : s.score < 0 ? C.red : C.muted }}>
                      {s.score > 0 ? "+" : ""}{s.score}
                    </td>
                    <td style={{ padding: "12px 14px",
                      color: (s.rsi ?? 50) < 35 ? C.blue : (s.rsi ?? 50) > 65 ? C.red : C.text }}>
                      {s.rsi?.toFixed(1) ?? "—"}
                    </td>
                    <td style={{ padding: "12px 14px" }}>
                      <span style={{
                        color: s.breakout_structure === "BULLISH_BREAKOUT" || s.bollinger_bands === "EXPANDING_OUTSIDE_UPPER" ? C.green :
                               s.breakout_structure === "BEARISH_BREAKDOWN" || s.bollinger_bands === "EXPANDING_OUTSIDE_LOWER" ? C.red :
                               s.bollinger_bands === "BAND_SQUEEZE" ? C.yellow : C.text,
                        fontWeight: 600, fontSize: "0.75rem"
                      }}>
                        {s.breakout_structure === "BULLISH_BREAKOUT" ? "🔥 Breakout" :
                         s.breakout_structure === "BEARISH_BREAKDOWN" ? "⚠️ Breakdown" :
                         s.bollinger_bands === "BAND_SQUEEZE" ? "⏳ Squeeze" : "Range"}
                      </span>
                    </td>
                    <td style={{ padding: "12px 14px", fontWeight: 600, color: s.vwap_confirmation === "BULLISH" ? C.green : C.red }}>
                      {s.vwap_confirmation === "BULLISH" ? "▲ Above" : "▼ Below"}
                    </td>
                    <td style={{ padding: "12px 14px", fontWeight: 500, color: s.pcr > 1.25 ? C.green : s.pcr < 0.75 ? C.red : C.text }}>
                      {s.pcr?.toFixed(2) ?? "—"}
                    </td>
                    <td style={{ padding: "12px 14px", fontWeight: 500,
                      color: s.oi_buildup_alignment === "Bullish Alignment" ? C.green :
                             s.oi_buildup_alignment === "Bearish Alignment" ? C.red : C.muted }}>
                      {s.oi_buildup ?? "—"}
                    </td>
                    <td style={{ padding: "12px 14px",
                      color: (s.chg_pct ?? 0) >= 0 ? C.green : C.red }}>
                      {(s.chg_pct ?? 0) >= 0 ? "+" : ""}{s.chg_pct?.toFixed(2)}%
                    </td>
                    <td style={{ padding: "12px 14px" }}>
                      <span style={{
                        ...(SIG_STYLE[s.signal] || SIG_STYLE.WAIT),
                        fontSize: "0.75rem", fontWeight: 700, padding: "4px 12px",
                        borderRadius: 20, display: "inline-block",
                      }}>
                        {s.signal}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {stocks.length === 0 && (
              <div style={{ padding: "2rem", textAlign: "center", color: C.muted }}>
                No stocks match this filter
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
