import React from "react";

const STAGES = [
  { id: 1, name: "Market Adapter", key: "market_adapter" },
  { id: 2, name: "Hawkes Process", key: "hawkes" },
  { id: 3, name: "Kalman Filter", key: "kalman" },
  { id: 4, name: "Particle Filter", key: "particle" },
  { id: 5, name: "Regime Detect", key: "regime" },
  { id: 6, name: "Ensemble Predict", key: "ensemble" },
  { id: 7, name: "Meta Learning", key: "meta_learning" },
  { id: 8, name: "Bayesian Fusion", key: "bayesian_fusion" },
  { id: 9, name: "Probability", key: "probability_engine" },
  { id: 10, name: "LLM Analyst", key: "llm_analyst" }
];

export default function PipelineFlow({ stageLatencies = {}, stageErrors = {}, activeStage = 10 }) {
  return (
    <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff", letterSpacing: "0.02em" }}>
          Pipeline Execution Flow
        </h4>
        <span style={{ fontSize: "11px", color: "#3b82f6", fontWeight: 700, textTransform: "uppercase" }}>
          Real-time Engine
        </span>
      </div>

      {/* Responsive Grid Flow */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
        gap: "12px",
        width: "100%"
      }}>
        {STAGES.map((stg, idx) => {
          const latency = stageLatencies[stg.key];
          const error = stageErrors[stg.key];
          
          let status = "completed";
          let statusColor = "#10b981"; // green
          let statusIcon = "✓";

          if (error) {
            status = "failed";
            statusColor = "#ef4444"; // red
            statusIcon = "✗";
          } else if (idx >= activeStage) {
            status = "pending";
            statusColor = "rgba(255,255,255,0.15)";
            statusIcon = "⏳";
          }

          const isActive = idx === activeStage - 1;

          return (
            <div
              key={stg.id}
              className="glass-panel"
              style={{
                padding: "12px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "space-between",
                textAlign: "center",
                minHeight: "100px",
                position: "relative",
                border: isActive ? "1px solid #8b5cf6" : "1px solid rgba(255, 255, 255, 0.08)",
                boxShadow: isActive ? "0 0 15px rgba(139, 92, 246, 0.2)" : "none",
                background: isActive ? "rgba(139, 92, 246, 0.05)" : "rgba(255,255,255,0.015)",
                transition: "all 0.3s ease"
              }}
            >
              {/* Connection particles indicator for active stage */}
              {isActive && (
                <div style={{
                  position: "absolute",
                  top: "-4px",
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: "#8b5cf6",
                  animation: "pulseGlow 1.5s infinite"
                }} />
              )}

              {/* Header: Circle with status */}
              <div style={{
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: status === "completed" ? "rgba(16, 185, 129, 0.1)" : 
                            status === "failed" ? "rgba(239, 44, 68, 0.1)" : "rgba(255,255,255,0.03)",
                border: `1px solid ${statusColor}`,
                color: statusColor,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "13px",
                fontWeight: 700,
                marginBottom: "8px"
              }}>
                {statusIcon}
              </div>

              {/* Title */}
              <div style={{ fontSize: "11px", fontWeight: 700, color: "#fff", marginBottom: "4px" }}>
                {stg.name}
              </div>

              {/* Latency / Error label */}
              <div style={{ fontSize: "9px", color: error ? "#ef4444" : "#a1a1aa", fontWeight: 600 }}>
                {error ? "Error" : latency ? `${latency.toFixed(1)} ms` : status === "pending" ? "Waiting" : "0.0 ms"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
