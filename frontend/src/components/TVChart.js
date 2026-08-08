import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, LineSeries, HistogramSeries } from "lightweight-charts";

/**
 * TradingView Lightweight Chart component.
 * Renders real OHLCV candlesticks + EMA 9/20/50/200 overlays + Volume bars.
 * Data shape expected: array of { Datetime, Open, High, Low, Close, Volume, EMA_9, EMA_20, EMA_50, EMA_200 }
 */
export default function TVChart({ data = [], height = 420 }) {
  const containerRef = useRef(null);
  const chartRef     = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !data.length) return;

    // --- Create chart ---
    const chart = createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height,
      layout: {
        background:  { color: "rgba(0,0,0,0)" },
        textColor:   "#9ca3af",
        fontFamily:  "'Inter', 'Outfit', sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: {
        borderColor:  "rgba(255,255,255,0.1)",
        textColor:    "#9ca3af",
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
      timeScale: {
        borderColor:     "rgba(255,255,255,0.1)",
        timeVisible:     true,
        secondsVisible:  false,
      },
    });
    chartRef.current = chart;

    // --- Prepare data ---
    const toTs = (d) => {
      const raw = d.Datetime || d.Date || "";
      const date = new Date(raw);
      return isNaN(date.getTime()) ? null : Math.floor(date.getTime() / 1000);
    };

    const sorted = [...data]
      .map(d => ({ ...d, _ts: toTs(d) }))
      .filter(d => d._ts && d.Close)
      .sort((a, b) => a._ts - b._ts);

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:          "#10b981",
      downColor:        "#ef4444",
      borderUpColor:    "#10b981",
      borderDownColor:  "#ef4444",
      wickUpColor:      "#10b981",
      wickDownColor:    "#ef4444",
    });
    candleSeries.setData(sorted.map(d => ({
      time:  d._ts,
      open:  d.Open,
      high:  d.High,
      low:   d.Low,
      close: d.Close,
    })));

    const markers = sorted
      .filter(d => d.Pattern && d.Pattern !== "NEUTRAL" && d.Pattern !== "FLAT")
      .map(d => {
        const isBull = d.Pattern.includes("BULL") || d.Pattern === "HAMMER";
        const isBear = d.Pattern.includes("BEAR") || d.Pattern === "SHOOTING_STAR";
        return {
          time: d._ts,
          position: isBull ? "belowBar" : isBear ? "aboveBar" : "aboveBar",
          color: isBull ? "#10b981" : isBear ? "#ef4444" : "#f59e0b",
          shape: isBull ? "arrowUp" : isBear ? "arrowDown" : "circle",
          text: d.Pattern.replace(/_/g, " "),
          size: 1
        };
      });
    if (markers.length > 0) {
      candleSeries.setMarkers(markers);
    }

    // Volume histogram (separate pane via priceScaleId)
    const volSeries = chart.addSeries(HistogramSeries, {
      color:        "#3b82f680",
      priceFormat:  { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volSeries.setData(sorted
      .filter(d => d.Volume != null)
      .map(d => ({
        time:  d._ts,
        value: d.Volume,
        color: d.Close >= d.Open ? "#10b98140" : "#ef444440",
      }))
    );

    // EMA overlays
    const emaConfigs = [
      { key: "EMA_9",  color: "#f59e0b", label: "EMA 9"  },
      { key: "EMA_20", color: "#ec4899", label: "EMA 20" },
      { key: "EMA_50", color: "#8b5cf6", label: "EMA 50" },
      { key: "EMA_200", color: "#06b6d4", label: "EMA 200" },
    ];
    emaConfigs.forEach(({ key, color }) => {
      const series = chart.addSeries(LineSeries, {
        color, lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false,
      });
      series.setData(
        sorted.filter(d => d[key] != null).map(d => ({ time: d._ts, value: d[key] }))
      );
    });

    // Fit content on mount
    chart.timeScale().fitContent();

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height]);

  return (
    <div style={{ position: "relative", width: "100%" }}>
      {!data.length && (
        <div style={{
          position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(18, 18, 22, 0.5)", color: "#9ca3af",
          fontSize: "0.9rem", zIndex: 20, borderRadius: "8px"
        }}>
          No chart data available
        </div>
      )}
      {/* Legend */}
      <div style={{
        position: "absolute", top: 8, left: 12, zIndex: 10,
        display: "flex", gap: "12px", fontSize: "11px", fontWeight: 600,
        fontFamily: "'Inter', sans-serif",
      }}>
        <span style={{ color: "#f59e0b" }}>● EMA 9</span>
        <span style={{ color: "#ec4899" }}>● EMA 20</span>
        <span style={{ color: "#8b5cf6" }}>● EMA 50</span>
        <span style={{ color: "#06b6d4" }}>● EMA 200</span>
        <span style={{ color: "#10b981" }}>▲ Bull</span>
        <span style={{ color: "#ef4444" }}>▼ Bear</span>
      </div>
      <div ref={containerRef} style={{ width: "100%", height }} />
    </div>
  );
}
