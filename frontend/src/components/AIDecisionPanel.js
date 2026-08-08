import React, { useEffect, useRef, useState } from "react";

/* ─────────────────────────────────────────────────
   AI Final Decision Panel — WealthQuant V7.4
   Full-width cinematic trade decision card with:
   • Pipeline flow waterfall (live animated)
   • Trade decision chip (BUY CALL / BUY PUT / NO TRADE)
   • Animated confidence arc
   • Live probability bars
   • Target / SL / RR metrics
   • Decision reason bullets
───────────────────────────────────────────────── */

const css = `
@keyframes wq-pulse-border {
  0%,100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); }
  50%      { box-shadow: 0 0 0 6px rgba(16,185,129,0.18); }
}
@keyframes wq-slide-up {
  from { opacity:0; transform:translateY(14px); }
  to   { opacity:1; transform:translateY(0);    }
}
@keyframes wq-bar-fill {
  from { width:0%; }
}
@keyframes wq-arc-fill {
  from { stroke-dashoffset: 314; }
}
@keyframes wq-node-pop {
  0%   { transform:scale(0); opacity:0; }
  60%  { transform:scale(1.3); }
  100% { transform:scale(1);  opacity:1; }
}
@keyframes wq-flow-line {
  from { stroke-dashoffset: 80; }
  to   { stroke-dashoffset: 0;  }
}
@keyframes wq-shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}
@keyframes wq-blink {
  0%,100% { opacity:1; }
  50%     { opacity:0.4; }
}
@keyframes wq-rotate {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
`;

/* ── Helpers ── */
const fmt = (v, d = 2) => (typeof v === "number" ? v.toFixed(d) : "—");
const pct = (v) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "—");
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/* ── Signal colour tokens ── */
const sigColor = (signal) => {
  if (!signal) return { text: "#a1a1aa", bg: "rgba(161,161,170,0.12)", glow: "transparent", border: "rgba(161,161,170,0.25)" };
  const s = signal.toUpperCase();
  if (s.includes("BUY") || s.includes("BULL"))
    return { text: "#10b981", bg: "rgba(16,185,129,0.12)", glow: "rgba(16,185,129,0.35)", border: "rgba(16,185,129,0.35)" };
  if (s.includes("SELL") || s.includes("PUT") || s.includes("BEAR"))
    return { text: "#f43f5e", bg: "rgba(244,63,94,0.12)", glow: "rgba(244,63,94,0.35)", border: "rgba(244,63,94,0.35)" };
  return { text: "#a1a1aa", bg: "rgba(161,161,170,0.1)", glow: "transparent", border: "rgba(161,161,170,0.2)" };
};

const tradeLabel = (signal) => {
  if (!signal) return { icon: "⚪", label: "NO TRADE", sublabel: "Insufficient edge" };
  const s = signal.toUpperCase();
  if (s === "STRONG_BUY" || s === "BUY")
    return { icon: "🟢", label: "BUY CALL", sublabel: "Long momentum detected" };
  if (s === "STRONG_SELL" || s === "SELL")
    return { icon: "🔴", label: "BUY PUT", sublabel: "Short momentum detected" };
  return { icon: "⚪", label: "NO TRADE", sublabel: "Market is neutral — wait" };
};

/* ── Animated confidence arc ── */
function ConfidenceArc({ value = 0 }) {
  const radius = 52;
  const circ = 2 * Math.PI * radius;
  const filled = circ * clamp(value, 0, 1);
  const empty = circ - filled;
  const col = value >= 0.75 ? "#10b981" : value >= 0.5 ? "#f59e0b" : "#f43f5e";

  return (
    <svg width="128" height="128" viewBox="0 0 128 128" style={{ transform: "rotate(-90deg)" }}>
      {/* Track */}
      <circle cx="64" cy="64" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
      {/* Fill */}
      <circle
        cx="64" cy="64" r={radius}
        fill="none"
        stroke={col}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${filled} ${empty}`}
        style={{
          filter: `drop-shadow(0 0 6px ${col})`,
          animation: "wq-arc-fill 1.2s cubic-bezier(0.22,1,0.36,1) forwards"
        }}
      />
      {/* Glow ring */}
      <circle cx="64" cy="64" r={radius} fill="none" stroke={col} strokeWidth="1" opacity="0.2" />
    </svg>
  );
}

/* ── Pipeline waterfall nodes ── */
const PIPELINE_NODES = [
  { id: "data",     label: "Market Data",        icon: "📡" },
  { id: "feat",     label: "Feature Eng.",        icon: "⚙️" },
  { id: "regime",   label: "Regime Detection",    icon: "🗺️" },
  { id: "ensemble", label: "Ensemble Models",     icon: "🧩" },
  { id: "struct",   label: "Market Structure",    icon: "🏗️" },
  { id: "bayes",    label: "Bayesian Fusion",     icon: "🎲" },
  { id: "meta",     label: "Meta Learning",       icon: "🧠" },
  { id: "decision", label: "AI Decision",         icon: "⚡" },
];

function PipelineWaterfall({ activeStage = 8, latencies = {} }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: "0",
      overflowX: "auto", paddingBottom: "4px",
    }}>
      {PIPELINE_NODES.map((node, i) => {
        const done = i < activeStage;
        const active = i === activeStage - 1;
        const lat = latencies[node.id] || latencies[Object.keys(latencies)[i]] || null;

        return (
          <React.Fragment key={node.id}>
            {/* Node */}
            <div style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              gap: "5px", minWidth: "72px",
              animation: done ? `wq-node-pop 0.4s ${i * 0.06}s cubic-bezier(0.22,1,0.36,1) both` : "none",
            }}>
              {/* Circle */}
              <div style={{
                width: "36px", height: "36px", borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "14px",
                background: active
                  ? "linear-gradient(135deg, #3b82f6, #8b5cf6)"
                  : done
                    ? "rgba(16,185,129,0.2)"
                    : "rgba(255,255,255,0.04)",
                border: active
                  ? "1.5px solid rgba(139,92,246,0.6)"
                  : done
                    ? "1.5px solid rgba(16,185,129,0.5)"
                    : "1.5px solid rgba(255,255,255,0.08)",
                boxShadow: active
                  ? "0 0 12px rgba(99,102,241,0.4)"
                  : done
                    ? "0 0 8px rgba(16,185,129,0.2)"
                    : "none",
                transition: "all 0.4s",
              }}>
                {active ? (
                  <div style={{
                    width: "14px", height: "14px", border: "2px solid #8b5cf6",
                    borderTopColor: "transparent", borderRadius: "50%",
                    animation: "wq-rotate 0.8s linear infinite",
                  }} />
                ) : (
                  <span style={{ filter: done ? "none" : "grayscale(1) opacity(0.3)" }}>{node.icon}</span>
                )}
              </div>
              {/* Label */}
              <span style={{
                fontSize: "9px", fontWeight: 600, textAlign: "center",
                color: active ? "#c4b5fd" : done ? "#10b981" : "#52525b",
                lineHeight: 1.2, maxWidth: "68px",
                transition: "color 0.4s",
              }}>
                {node.label}
              </span>
              {lat && done && (
                <span style={{ fontSize: "8px", color: "#52525b" }}>{lat.toFixed(0)}ms</span>
              )}
            </div>

            {/* Connector line */}
            {i < PIPELINE_NODES.length - 1 && (
              <div style={{
                flex: 1, height: "2px", minWidth: "12px",
                background: i < activeStage - 1
                  ? "linear-gradient(90deg, rgba(16,185,129,0.6), rgba(16,185,129,0.2))"
                  : "rgba(255,255,255,0.06)",
                borderRadius: "1px",
                transition: "background 0.4s",
              }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

/* ── Probability bar ── */
function ProbBar({ label, value = 0, color, delay = 0 }) {
  const pctVal = Math.round(clamp(value, 0, 1) * 100);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px" }}>
        <span style={{ color: "#a1a1aa", fontWeight: 500 }}>{label}</span>
        <span style={{ fontWeight: 700, color }}>{pctVal}%</span>
      </div>
      <div style={{ height: "5px", background: "rgba(255,255,255,0.06)", borderRadius: "99px", overflow: "hidden" }}>
        <div style={{
          width: `${pctVal}%`, height: "100%",
          background: color,
          borderRadius: "99px",
          boxShadow: `0 0 8px ${color}`,
          animation: `wq-bar-fill 1s ${delay}s cubic-bezier(0.22,1,0.36,1) both`,
        }} />
      </div>
    </div>
  );
}

/* ── Metric chip ── */
function MetricChip({ label, value, color = "#fff", accent = false }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", gap: "3px", padding: "10px 14px",
      background: accent ? "rgba(59,130,246,0.08)" : "rgba(255,255,255,0.04)",
      border: `1px solid ${accent ? "rgba(59,130,246,0.2)" : "rgba(255,255,255,0.06)"}`,
      borderRadius: "10px", minWidth: "80px",
    }}>
      <span style={{ fontSize: "9px", fontWeight: 700, color: "#52525b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </span>
      <span style={{ fontSize: "15px", fontWeight: 800, color, fontFamily: "'Outfit',sans-serif", lineHeight: 1 }}>
        {value}
      </span>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════ */
export default function AIDecisionPanel({ pipelineData, symbol = "NIFTY", loading = false }) {
  const [revealed, setRevealed] = useState(false);
  const styleRef = useRef(null);

  /* Inject CSS once */
  useEffect(() => {
    if (styleRef.current) return;
    const el = document.createElement("style");
    el.textContent = css;
    document.head.appendChild(el);
    styleRef.current = el;
    return () => { try { document.head.removeChild(el); } catch {} };
  }, []);

  /* Trigger entrance animation on data arrival */
  useEffect(() => {
    setRevealed(false);
    const t = setTimeout(() => setRevealed(true), 80);
    return () => clearTimeout(t);
  }, [pipelineData]);

  /* ── Data extraction ── */
  const prob    = pipelineData?.stages?.probabilities || {};
  const regime  = pipelineData?.stages?.regime || {};
  const fusion  = pipelineData?.stages?.fusion || {};
  const kalman  = pipelineData?.stages?.kalman || {};
  const meta    = pipelineData?.stages?.meta_learning || {};
  const report  = pipelineData?.stages?.analyst_report || {};
  const hawkes  = pipelineData?.stages?.hawkes || {};

  const signal      = prob.signal || "NEUTRAL";
  const confidence  = prob.signal_confidence || 0;
  const pUp         = prob.p_up || 0;
  const pDown       = prob.p_down || 0;
  const pSide       = prob.p_sideways ?? (1 - pUp - pDown);
  const expReturn   = prob.expected_return || 0;
  const spotPrice   = kalman.filtered_price || 0;
  const modelAgree  = fusion.model_agreement || 0;
  const activeRegime = regime.current_regime || "TRANSITION";
  const latencies   = pipelineData?.stage_latencies || {};

  /* Derived trade params */
  const isBuy = signal.toUpperCase().includes("BUY") || signal.toUpperCase().includes("STRONG_BUY");
  const isSell = signal.toUpperCase().includes("SELL") || signal.toUpperCase().includes("STRONG_SELL");
  const move = Math.abs(expReturn) * spotPrice;
  const target = isBuy
    ? (spotPrice + move).toFixed(0)
    : isSell
      ? (spotPrice - move).toFixed(0)
      : "—";
  const sl = isBuy
    ? (spotPrice - move * 0.5).toFixed(0)
    : isSell
      ? (spotPrice + move * 0.5).toFixed(0)
      : "—";
  const rr = move > 0 ? `1 : ${(move / (move * 0.5)).toFixed(1)}` : "—";

  const sc    = sigColor(signal);
  const trade = tradeLabel(signal);

  /* Decision reasons (LLM or fallback) */
  const reasons = report.key_drivers?.slice(0, 5) || [
    modelAgree > 0 && `Ensemble Agreement ${Math.round(modelAgree * 100)}%`,
    activeRegime && `Regime: ${activeRegime.replace(/_/g, " ")}`,
    pUp > 0.5 && `Bullish Probability ${Math.round(pUp * 100)}%`,
    pDown > 0.5 && `Bearish Probability ${Math.round(pDown * 100)}%`,
    hawkes.is_cascade && "⚡ Event Cascade Detected",
  ].filter(Boolean);

  const holdbars = meta.adaptation_status === "FAST" ? "1–3 candles" : "2–5 candles";

  if (loading && !pipelineData) {
    return (
      <div style={{
        borderRadius: "20px", overflow: "hidden",
        background: "rgba(18,18,22,0.65)", border: "1px solid rgba(255,255,255,0.08)",
        padding: "28px",
        backgroundImage: "linear-gradient(90deg, transparent 25%, rgba(255,255,255,0.04) 50%, transparent 75%)",
        backgroundSize: "800px 100%",
        animation: "wq-shimmer 1.6s infinite",
        minHeight: "360px",
      }} />
    );
  }

  return (
    <div
      id="ai-decision-panel"
      style={{
        display: "flex", flexDirection: "column", gap: "0",
        borderRadius: "20px", overflow: "hidden",
        border: `1px solid ${sc.border}`,
        boxShadow: `0 0 0 1px ${sc.border}, 0 8px 40px -8px ${sc.glow}, inset 0 1px 0 rgba(255,255,255,0.06)`,
        background: "rgba(10,10,14,0.88)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        animation: revealed ? "wq-slide-up 0.5s cubic-bezier(0.22,1,0.36,1) both" : "none",
        transition: "box-shadow 0.6s, border-color 0.6s",
      }}
    >
      {/* ── TOP GLOW BAR ── */}
      <div style={{
        height: "3px",
        background: isBuy
          ? "linear-gradient(90deg, transparent, #10b981, #34d399, transparent)"
          : isSell
            ? "linear-gradient(90deg, transparent, #f43f5e, #fb7185, transparent)"
            : "linear-gradient(90deg, transparent, #6b7280, transparent)",
        opacity: 0.9,
      }} />

      {/* ── PIPELINE WATERFALL ── */}
      <div style={{ padding: "20px 28px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: "5px",
              fontSize: "10px", fontWeight: 700, letterSpacing: "0.1em",
              color: "#6366f1", textTransform: "uppercase",
              padding: "3px 10px", borderRadius: "99px",
              background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)",
            }}>
              <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: "#10b981", animation: "wq-blink 1.4s ease-in-out infinite" }} />
              AI PIPELINE — LIVE
            </span>
            <span style={{ fontSize: "11px", color: "#52525b" }}>
              {symbol} · {pipelineData?.latency_ms ? `${pipelineData.latency_ms.toFixed(0)}ms` : ""}
            </span>
          </div>
          <span style={{ fontSize: "11px", color: "#3f3f46" }}>
            {pipelineData?.timestamp ? new Date(pipelineData.timestamp).toLocaleTimeString("en-IN") : ""}
          </span>
        </div>

        <PipelineWaterfall activeStage={8} latencies={latencies} />
      </div>

      {/* ── DECISION CORE ── */}
      <div style={{ padding: "24px 28px", display: "flex", gap: "28px", flexWrap: "wrap" }}>

        {/* LEFT: Trade signal + confidence arc */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", minWidth: "160px" }}>
          {/* Signal chip */}
          <div style={{
            padding: "10px 22px", borderRadius: "12px",
            background: sc.bg, border: `1.5px solid ${sc.border}`,
            boxShadow: `0 0 24px -4px ${sc.glow}`,
            textAlign: "center",
            animation: revealed ? "wq-pulse-border 2.5s ease-in-out infinite" : "none",
          }}>
            <div style={{ fontSize: "28px", lineHeight: 1 }}>{trade.icon}</div>
            <div style={{
              fontSize: "18px", fontWeight: 900, color: sc.text,
              fontFamily: "'Outfit',sans-serif", letterSpacing: "0.03em", marginTop: "4px",
            }}>
              {trade.label}
            </div>
            <div style={{ fontSize: "10px", color: "#a1a1aa", marginTop: "2px" }}>{trade.sublabel}</div>
          </div>

          {/* Confidence arc */}
          <div style={{ position: "relative", width: "128px", height: "128px" }}>
            <ConfidenceArc value={confidence} />
            <div style={{
              position: "absolute", inset: 0,
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            }}>
              <span style={{ fontSize: "22px", fontWeight: 900, fontFamily: "'Outfit',sans-serif", color: "#fff" }}>
                {Math.round(confidence * 100)}%
              </span>
              <span style={{ fontSize: "9px", color: "#52525b", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Confidence
              </span>
            </div>
          </div>
        </div>

        {/* MIDDLE: Trade metrics */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "14px", minWidth: "220px" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, color: "#52525b", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Trade Parameters
          </div>

          {/* Metric row 1 */}
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <MetricChip label="Expected Move" value={move > 0 ? `+${move.toFixed(0)} pts` : "—"} color="#c4b5fd" accent />
            <MetricChip label="Target" value={`₹${target}`} color="#10b981" />
            <MetricChip label="Stop Loss" value={`₹${sl}`} color="#f43f5e" />
            <MetricChip label="Risk : Reward" value={rr} color="#f59e0b" />
            <MetricChip label="Holding" value={holdbars} color="#a1a1aa" />
          </div>

          {/* Prob bars */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <ProbBar label="Bullish Probability" value={pUp}   color="#10b981" delay={0}    />
            <ProbBar label="Bearish Probability" value={pDown} color="#f43f5e" delay={0.08} />
            <ProbBar label="Neutral Probability" value={pSide} color="#6366f1" delay={0.16} />
          </div>

          {/* Regime + Model agreement row */}
          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
            <div style={{
              padding: "5px 12px", borderRadius: "6px", fontSize: "11px", fontWeight: 700,
              background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.25)",
              color: "#c4b5fd",
            }}>
              📊 {activeRegime.replace(/_/g, " ")}
            </div>
            <div style={{
              padding: "5px 12px", borderRadius: "6px", fontSize: "11px", fontWeight: 700,
              background: modelAgree >= 0.8 ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
              border: `1px solid ${modelAgree >= 0.8 ? "rgba(16,185,129,0.3)" : "rgba(245,158,11,0.3)"}`,
              color: modelAgree >= 0.8 ? "#10b981" : "#f59e0b",
            }}>
              🤝 Ensemble Agreement {Math.round(modelAgree * 100)}%
            </div>
          </div>
        </div>

        {/* RIGHT: Decision Reasons */}
        <div style={{
          minWidth: "200px", maxWidth: "280px", flex: "0 0 auto",
          display: "flex", flexDirection: "column", gap: "10px",
        }}>
          <div style={{ fontSize: "11px", fontWeight: 700, color: "#52525b", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Decision Reasons
          </div>

          {/* Separator */}
          <div style={{
            flex: 1, display: "flex", flexDirection: "column", gap: "6px",
            padding: "14px",
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: "12px",
          }}>
            {reasons.length > 0 ? reasons.map((r, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "flex-start", gap: "8px",
                fontSize: "12px", lineHeight: 1.45,
                animation: `wq-slide-up 0.4s ${i * 0.07}s cubic-bezier(0.22,1,0.36,1) both`,
              }}>
                <span style={{
                  width: "6px", height: "6px", borderRadius: "50%",
                  background: sc.text, flexShrink: 0, marginTop: "5px",
                  boxShadow: `0 0 6px ${sc.glow}`,
                }} />
                <span style={{ color: "#d4d4d8" }}>{r}</span>
              </div>
            )) : (
              <div style={{ color: "#52525b", fontSize: "12px" }}>
                Awaiting first pipeline run…
              </div>
            )}
          </div>

          {/* Spot price */}
          {spotPrice > 0 && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 14px", borderRadius: "10px",
              background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)",
            }}>
              <span style={{ fontSize: "11px", color: "#6b7280", fontWeight: 600 }}>Spot (Kalman)</span>
              <span style={{ fontSize: "15px", fontWeight: 800, color: "#93c5fd", fontFamily: "'Outfit',sans-serif" }}>
                ₹{spotPrice.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ── BOTTOM RISK STRIP ── */}
      {(prob.var_95 || prob.tail_risk_score) && (
        <div style={{
          padding: "10px 28px",
          borderTop: "1px solid rgba(255,255,255,0.04)",
          display: "flex", gap: "24px", flexWrap: "wrap", alignItems: "center",
          background: "rgba(0,0,0,0.2)",
        }}>
          <span style={{ fontSize: "10px", fontWeight: 700, color: "#3f3f46", textTransform: "uppercase", letterSpacing: "0.07em" }}>
            Risk
          </span>
          {prob.var_95 != null && (
            <div style={{ fontSize: "11px", color: "#a1a1aa" }}>
              VaR 95%: <strong style={{ color: "#f43f5e" }}>{(prob.var_95 * 100).toFixed(2)}%</strong>
            </div>
          )}
          {prob.cvar_95 != null && (
            <div style={{ fontSize: "11px", color: "#a1a1aa" }}>
              CVaR 95%: <strong style={{ color: "#f43f5e" }}>{(prob.cvar_95 * 100).toFixed(2)}%</strong>
            </div>
          )}
          {prob.tail_risk_score != null && (
            <div style={{ fontSize: "11px", color: "#a1a1aa" }}>
              Tail Risk: <strong style={{ color: prob.tail_risk_score > 40 ? "#f59e0b" : "#10b981" }}>
                {prob.tail_risk_score.toFixed(1)}/100
              </strong>
            </div>
          )}
          {prob.kelly_fraction != null && (
            <div style={{ fontSize: "11px", color: "#a1a1aa" }}>
              Kelly Size: <strong style={{ color: "#c4b5fd" }}>{Math.round(prob.kelly_fraction * 100)}%</strong>
            </div>
          )}
          {hawkes.is_cascade && (
            <div style={{
              marginLeft: "auto", fontSize: "10px", fontWeight: 700,
              padding: "3px 10px", borderRadius: "99px",
              background: "rgba(244,63,94,0.15)", border: "1px solid rgba(244,63,94,0.3)",
              color: "#f43f5e", animation: "wq-blink 1.2s infinite",
            }}>
              🚨 CASCADE EVENT
            </div>
          )}
        </div>
      )}

      {/* ── BOTTOM GLOW BAR ── */}
      <div style={{
        height: "2px",
        background: isBuy
          ? "linear-gradient(90deg, transparent, rgba(16,185,129,0.4), transparent)"
          : isSell
            ? "linear-gradient(90deg, transparent, rgba(244,63,94,0.4), transparent)"
            : "none",
      }} />
    </div>
  );
}
