import React from "react";

export default function ProbabilityGauge({ pUp = 0, pDown = 0, pSideways = 0, signal = "NEUTRAL", confidence = 0 }) {
  // Concentric circle settings
  const size = 180;
  const strokeWidth = 10;
  const center = size / 2;

  // Radii for concentric circles: outer, middle, inner
  const rUp = 65;
  const rSide = 48;
  const rDown = 31;

  // Circumferences
  const cUp = 2 * Math.PI * rUp;
  const cSide = 2 * Math.PI * rSide;
  const cDown = 2 * Math.PI * rDown;

  // Stroke offsets corresponding to probabilities (0 to 1)
  const offsetUp = cUp * (1 - pUp);
  const offsetSide = cSide * (1 - pSideways);
  const offsetDown = cDown * (1 - pDown);

  // Determine label and color based on signal
  let signalColor = "#a1a1aa"; // neutral
  if (signal === "STRONG_BUY") signalColor = "#10b981"; // success green
  else if (signal === "BUY") signalColor = "#34d399"; // light green
  else if (signal === "STRONG_SELL") signalColor = "#ef4444"; // danger red
  else if (signal === "SELL") signalColor = "#f87171"; // light red

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: "16px", height: "100%", position: "relative"
    }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        {/* Track Backdrops */}
        <circle cx={center} cy={center} r={rUp} fill="transparent" stroke="rgba(16, 185, 129, 0.08)" strokeWidth={strokeWidth} />
        <circle cx={center} cy={center} r={rSide} fill="transparent" stroke="rgba(161, 161, 170, 0.08)" strokeWidth={strokeWidth} />
        <circle cx={center} cy={center} r={rDown} fill="transparent" stroke="rgba(239, 44, 68, 0.08)" strokeWidth={strokeWidth} />

        {/* Outer Ring: P(UP) - Green */}
        <circle
          cx={center}
          cy={center}
          r={rUp}
          fill="transparent"
          stroke="#10b981"
          strokeWidth={strokeWidth}
          strokeDasharray={cUp}
          strokeDashoffset={offsetUp}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)" }}
        />

        {/* Middle Ring: P(SIDEWAYS) - Gray */}
        <circle
          cx={center}
          cy={center}
          r={rSide}
          fill="transparent"
          stroke="#71717a"
          strokeWidth={strokeWidth}
          strokeDasharray={cSide}
          strokeDashoffset={offsetSide}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)" }}
        />

        {/* Inner Ring: P(DOWN) - Red */}
        <circle
          cx={center}
          cy={center}
          r={rDown}
          fill="transparent"
          stroke="#ef4444"
          strokeWidth={strokeWidth}
          strokeDasharray={cDown}
          strokeDashoffset={offsetDown}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)" }}
        />
      </svg>

      {/* Center Labels */}
      <div style={{
        position: "absolute", top: "50%", left: "50%",
        transform: "translate(-50%, -50%)", textAlign: "center",
        pointerEvents: "none", marginTop: "-4px"
      }}>
        <div style={{ fontSize: "11px", color: "#a1a1aa", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
          {signal.replace("_", " ")}
        </div>
        <div style={{ fontSize: "24px", fontWeight: 800, color: "#fff", margin: "2px 0", fontFamily: "Outfit, sans-serif" }}>
          {Math.round(confidence * 100)}%
        </div>
        <div style={{ fontSize: "10px", color: signalColor, fontWeight: 700, letterSpacing: "0.02em" }}>
          CONFIDENCE
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: "16px", marginTop: "12px", fontSize: "11px", fontWeight: 600 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#10b981" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10b981" }} />
          <span>UP: {Math.round(pUp * 100)}%</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#a1a1aa" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#71717a" }} />
          <span>SIDE: {Math.round(pSideways * 100)}%</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#ef4444" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#ef4444" }} />
          <span>DOWN: {Math.round(pDown * 100)}%</span>
        </div>
      </div>
    </div>
  );
}
