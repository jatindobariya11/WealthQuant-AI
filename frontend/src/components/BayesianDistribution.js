import React from "react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine } from "recharts";

export default function BayesianDistribution({ distributionData = {}, varValue = -0.02, expectedReturn = 0.005, currentPrice = 100 }) {
  const bins = distributionData.bins || [];
  const density = distributionData.density || [];

  // Transform data for Recharts
  const chartData = bins.map((b, idx) => ({
    x: b,
    xPct: (b * 100).toFixed(2), // display format
    density: density[idx] || 0
  }));

  // Format x-axis labels
  const formatXAxis = (tick) => {
    return `${(tick * 100).toFixed(1)}%`;
  };

  return (
    <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff", letterSpacing: "0.02em" }}>
          Bayesian Return Probability Distribution
        </h4>
        <div style={{ display: "flex", gap: "16px", fontSize: "11px", fontWeight: 600 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#ef4444" }}>
            <span style={{ borderBottom: "1px dashed #ef4444", width: "12px", height: 0 }} />
            <span>VaR (95%): {(varValue * 100).toFixed(2)}%</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#10b981" }}>
            <span style={{ borderBottom: "1px dashed #10b981", width: "12px", height: 0 }} />
            <span>Expected: {(expectedReturn * 100).toFixed(2)}%</span>
          </div>
        </div>
      </div>

      <div style={{ width: "100%", height: 220 }}>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorDensity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="x"
                type="number"
                domain={[Math.min(...bins), Math.max(...bins)]}
                tickFormatter={formatXAxis}
                stroke="rgba(255,255,255,0.3)"
                style={{ fontSize: "10px" }}
              />
              <YAxis
                hide={true}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="glass-panel" style={{ padding: "8px 12px", fontSize: "11px", color: "#fff", border: "1px solid rgba(255,255,255,0.1)" }}>
                        <div>Return: <strong style={{ color: "#3b82f6" }}>{parseFloat(data.xPct)}%</strong></div>
                        <div>Density: <strong>{data.density.toFixed(4)}</strong></div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              {/* Reference Lines */}
              {/* 0% Return (Current Spot) */}
              <ReferenceLine x={0.0} stroke="rgba(255,255,255,0.4)" strokeWidth={1.5} label={{ value: "0%", fill: "rgba(255,255,255,0.4)", position: "top", fontSize: 10 }} />
              {/* Value at Risk (Red dashed) */}
              <ReferenceLine x={varValue} stroke="#ef4444" strokeDasharray="3 3" strokeWidth={1.5} />
              {/* Expected Return (Green dashed) */}
              <ReferenceLine x={expectedReturn} stroke="#10b981" strokeDasharray="3 3" strokeWidth={1.5} />

              <Area
                type="monotone"
                dataKey="density"
                stroke="#8b5cf6"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorDensity)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#a1a1aa", fontSize: "12px" }}>
            No distribution data available
          </div>
        )}
      </div>
    </div>
  );
}
