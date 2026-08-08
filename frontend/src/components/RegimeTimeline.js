import React from "react";

const REGIME_COLORS = {
  TRENDING_BULL: "#10b981",
  TRENDING_BEAR: "#ef4444",
  MEAN_REVERTING: "#3b82f6",
  HIGH_VOLATILITY: "#f59e0b",
  LOW_VOLATILITY: "#8b5cf6",
  TRANSITION: "#6b7280"
};

export default function RegimeTimeline({ regimeHistory = [], currentRegime = "TRANSITION", confidence = 0.5 }) {
  // Normalize history blocks
  const historyBlocks = [...regimeHistory].reverse(); // oldest first

  // Sum of all durations to partition widths
  const totalBars = historyBlocks.reduce((sum, item) => sum + (item.bars || 1), 0) || 1;

  return (
    <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff", letterSpacing: "0.02em" }}>
          Regime History Timeline
        </h4>
        <div style={{ fontSize: "12px", color: "#a1a1aa", display: "flex", alignItems: "center", gap: "8px" }}>
          <span>Active:</span>
          <span style={{
            background: REGIME_COLORS[currentRegime] || "#6b7280",
            color: "#fff", padding: "2px 8px", borderRadius: "4px", fontWeight: 700,
            fontSize: "11px", display: "inline-block"
          }}>
            {currentRegime.replace("_", " ")}
          </span>
          <span style={{ fontWeight: 600 }}>({Math.round(confidence * 100)}% conf)</span>
        </div>
      </div>

      {/* Horizontal Bar Chart */}
      <div style={{
        display: "flex", width: "100%", height: "24px", borderRadius: "6px", overflow: "hidden",
        background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", position: "relative"
      }}>
        {historyBlocks.map((block, idx) => {
          const widthPct = `${((block.bars || 1) / totalBars) * 100}%`;
          const isCurrent = idx === historyBlocks.length - 1;
          const regColor = REGIME_COLORS[block.regime] || "#6b7280";

          return (
            <div
              key={idx}
              title={`${block.regime.replace("_", " ")}: ${block.bars} bars`}
              style={{
                width: widthPct,
                height: "100%",
                background: regColor,
                transition: "all 0.3s ease",
                position: "relative",
                cursor: "pointer",
                borderRight: idx < historyBlocks.length - 1 ? "1px solid rgba(0,0,0,0.15)" : "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
            >
              {isCurrent && (
                <div style={{
                  position: "absolute", inset: 0,
                  boxShadow: `0 0 12px ${regColor}`,
                  animation: "pulseGlow 2s infinite ease-in-out",
                  pointerEvents: "none"
                }} />
              )}
            </div>
          );
        })}
      </div>

      {/* Legend Grid */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
        gap: "10px", fontSize: "11px", color: "#a1a1aa", fontWeight: 600
      }}>
        {Object.entries(REGIME_COLORS).map(([name, color]) => (
          <div key={name} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "2px", background: color, display: "inline-block" }} />
            <span>{name.replace("_", " ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
