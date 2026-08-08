"""
Stage 10: LLM Analyst.
Generates natural language reports using local Ollama (Qwen 7B) with rule-based fallback.
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime

from pipeline.base import AnalystReport, PipelineStage
from pipeline.config import LLM_CONFIG

# Optional ollama import
try:
    import ollama  # ruff: noqa: F401

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

logger = logging.getLogger("pipeline.llm_analyst")


class Stage10LLMAnalyst(PipelineStage):
    @property
    def name(self) -> str:
        return "llm_analyst"

    def _generate_fallback_report(
        self, symbol: str, price: float, result_dict: dict
    ) -> AnalystReport:
        """
        Generate a rule-based analyst report when Ollama is unavailable.
        """
        prob_stage = result_dict.get("stages", {}).get("probabilities", {})
        regime_stage = result_dict.get("stages", {}).get("regime", {})
        hawkes_stage = result_dict.get("stages", {}).get("hawkes", {})

        signal = prob_stage.get("signal", "NEUTRAL")
        p_up = prob_stage.get("p_up", 0.0)
        p_down = prob_stage.get("p_down", 0.0)
        regime = regime_stage.get("current_regime", "TRANSITION")

        conviction = "LOW"
        if signal in ["STRONG_BUY", "STRONG_SELL"]:
            conviction = "HIGH"
        elif signal in ["BUY", "SELL"]:
            conviction = "MEDIUM"

        action = "MONITOR"
        if signal == "STRONG_BUY":
            action = "STRONG BUY / ACCUMULATE"
        elif signal == "BUY":
            action = "BUY / LONG"
        elif signal == "STRONG_SELL":
            action = "STRONG SELL / SHORT"
        elif signal == "SELL":
            action = "SELL / SHORT"
        else:
            action = "HOLD / NEUTRAL"

        # Targets using ATR
        atr = (
            result_dict.get("stages", {})
            .get("probabilities", {})
            .get("expected_move_pct", 0.01)
            * price
        )

        if "BUY" in signal:
            entry = f"₹{price:.2f} - ₹{(price * 1.002):.2f}"
            sl = f"₹{(price - 1.5 * atr):.2f}"
            targets = [f"₹{(price + 1.0 * atr):.2f}", f"₹{(price + 2.0 * atr):.2f}"]
        elif "SELL" in signal:
            entry = f"₹{(price * 0.998):.2f} - ₹{price:.2f}"
            sl = f"₹{(price + 1.5 * atr):.2f}"
            targets = [f"₹{(price - 1.0 * atr):.2f}", f"₹{(price - 2.0 * atr):.2f}"]
        else:
            entry = "N/A"
            sl = "N/A"
            targets = []

        is_cascade = hawkes_stage.get("is_cascade", False)
        cascade_txt = (
            "Alert: High intensity event cascade detected in Hawkes process."
            if is_cascade
            else "Event activity remains baseline."
        )

        risk_warnings = []
        if regime == "HIGH_VOLATILITY":
            risk_warnings.append("⚠️ High volatility regime may trigger wider stops.")

        report = AnalystReport(
            headline=f"{symbol}: {signal.replace('_', ' ')} conviction in {regime} regime",
            summary=f"Calibrated probability engine suggests {signal} for {symbol}. Probability of upward move is {p_up * 100:.1f}%, while downward probability is {p_down * 100:.1f}%.",
            conviction_level=conviction,
            thesis=f"The stock is currently trading under the {regime} regime. {cascade_txt} Risk models show 95% Value-at-Risk (VaR) at {prob_stage.get('var_95', 0.0) * 100:.2f}%. Suggested Kelly fraction sizing is {prob_stage.get('kelly_fraction', 0.0) * 100:.1f}%.",
            key_drivers=[
                f"Regime status: {regime}",
                f"Calibrated probability skew: P(UP) = {p_up:.2f}",
                f"Volatility estimate: {prob_stage.get('expected_move_pct', 0.01) * 100:.2f}% expected move",
            ],
            contrarian_risks=[
                "Potential regime shift back to TRANSITION",
                "Model disagreement / conflict in underlying estimates",
                "Sudden macroeconomic spikes affecting the broad index",
            ],
            bull_case={
                "target": f"₹{(price * 1.02):.2f}",
                "probability": float(p_up),
                "catalysts": ["FII net buying flow increases", "Volume spike breakout"],
            },
            base_case={
                "target": f"₹{price:.2f}",
                "probability": float(prob_stage.get("p_sideways", 0.0)),
                "catalysts": ["Consolidation in range", "Low news volatility"],
            },
            bear_case={
                "target": f"₹{(price * 0.98):.2f}",
                "probability": float(p_down),
                "catalysts": [
                    "Global market index decline",
                    "Negative news flow trigger",
                ],
            },
            recommended_action=action,
            entry_zone=entry,
            stop_loss=sl,
            targets=targets,
            timeframe="1-3 trading days",
            position_sizing=f"Allocate {prob_stage.get('suggested_position_size', 0.0) * 100:.1f}% of trading capital",
            risk_warnings=risk_warnings,
            confidence_caveats=[
                "Local Qwen analyst offline — rule-based fallback report active."
            ],
            timestamp=datetime.now(),
        )
        return report

    def process(self, symbol: str, price: float, result_dict: dict) -> AnalystReport:
        """
        Connect to Ollama to generate analyst report, fallback to rule-based on failure.
        """
        base_url = LLM_CONFIG.get("base_url", "http://localhost:11434")
        model = LLM_CONFIG.get("model", "qwen2.5:7b")
        temperature = LLM_CONFIG.get("temperature", 0.3)
        timeout = LLM_CONFIG.get("timeout_seconds", 30)

        # Check if Ollama service is reachable
        ollama_running = False
        try:
            with urllib.request.urlopen(f"{base_url}/api/tags", timeout=2) as response:
                if response.status == 200:
                    ollama_running = True
        except Exception:
            ollama_running = False

        if not ollama_running:
            logger.info(
                "Ollama service not running or unreachable. Generating fallback report."
            )
            return self._generate_fallback_report(symbol, price, result_dict)

        # Construct prompt
        prob_stage = result_dict.get("stages", {}).get("probabilities", {})
        regime_stage = result_dict.get("stages", {}).get("regime", {})
        hawkes_stage = result_dict.get("stages", {}).get("hawkes", {})
        kalman_stage = result_dict.get("stages", {}).get("kalman", {})
        particle_stage = result_dict.get("stages", {}).get("particle", {})
        fusion_stage = result_dict.get("stages", {}).get("fusion", {})

        prompt = f"""
You are a Senior Quantitative Analyst at a premium wealth management firm. 
Generate a structured, professional analyst report for symbol {symbol} at current spot price ₹{price:.2f}.

Use the following pipeline outputs as context:
- CALIBRATED PROBABILITIES:
  P(UP): {prob_stage.get("p_up", 0.0):.4f}
  P(DOWN): {prob_stage.get("p_down", 0.0):.4f}
  P(SIDEWAYS): {prob_stage.get("p_sideways", 0.0):.4f}
  Signal: {prob_stage.get("signal", "NEUTRAL")}
  Signal Confidence: {prob_stage.get("signal_confidence", 0.0):.4f}
  Kelly Fraction: {prob_stage.get("kelly_fraction", 0.0):.4f}
  Suggested capital allocation: {prob_stage.get("suggested_position_size", 0.0):.4f}

- MARKET REGIME:
  Current Regime: {regime_stage.get("current_regime", "TRANSITION")}
  Regime Confidence: {regime_stage.get("regime_confidence", 0.0):.4f}
  Duration: {regime_stage.get("regime_duration_bars", 0)} bars
  Regime Changepoint Probability: {regime_stage.get("transition_probability", 0.0):.4f}

- STATISTICAL FILTERS:
  Hawkes Event Intensity Ratio: {hawkes_stage.get("excitation_ratio", 1.0):.4f}
  Hawkes Branching Ratio: {hawkes_stage.get("branching_ratio", 0.0):.4f}
  Hawkes Cascade Detected: {hawkes_stage.get("is_cascade", False)}
  Kalman Filter Velocity (price momentum): {kalman_stage.get("estimated_velocity", 0.0):.4f}
  Kalman Filter Acceleration: {kalman_stage.get("estimated_acceleration", 0.0):.4f}
  Kalman Innovation Z-Score (surprise): {kalman_stage.get("innovation_zscore", 0.0):.4f}
  Particle Skewness: {particle_stage.get("skewness", 0.0):.4f}
  Particle Bimodality: {particle_stage.get("bimodality_score", 0.0):.4f}
  Particle Tail Risk Left (crash): {particle_stage.get("tail_risk_left", 0.0):.4f}
  Particle Tail Risk Right (breakout): {particle_stage.get("tail_risk_right", 0.0):.4f}

- BAYESIAN FUSION:
  Dominant model driving forecast: {fusion_stage.get("dominant_model", "None")}
  Model agreement score: {fusion_stage.get("model_agreement", 0.0):.4f}
  Model conflict alert: {fusion_stage.get("conflict_alert", False)}

Respond strictly in JSON format. Do not write any preamble or extra text.
The JSON must follow this exact schema:
{{
  "headline": "Professional title summary of the report",
  "summary": "2-3 sentence executive summary",
  "conviction_level": "HIGH" or "MEDIUM" or "LOW",
  "thesis": "Paragraph explaining the analytical thesis",
  "key_drivers": ["driver 1", "driver 2", "driver 3"],
  "contrarian_risks": ["risk 1", "risk 2"],
  "bull_case": {{ "target": "₹X", "probability": 0.X, "catalysts": ["catalyst 1"] }},
  "base_case": {{ "target": "₹X", "probability": 0.X, "catalysts": ["catalyst 1"] }},
  "bear_case": {{ "target": "₹X", "probability": 0.X, "catalysts": ["catalyst 1"] }},
  "recommended_action": "Actionable trade instruction",
  "entry_zone": "Price range to enter, e.g., ₹X - ₹Y",
  "stop_loss": "Suggested stop loss price",
  "targets": ["Target 1 Price", "Target 2 Price"],
  "timeframe": "Suggested trade duration",
  "position_sizing": "Capital allocation recommendation",
  "risk_warnings": ["warning 1", "warning 2"],
  "confidence_caveats": ["caveat 1"]
}}
"""

        try:
            req_data = json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": temperature, "num_predict": 3000},
                    "stream": False,
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/api/chat",
                data=req_data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_obj = json.loads(response.read().decode("utf-8"))
                text = res_obj["message"]["content"]
                data = json.loads(text) if isinstance(text, str) else text

                return AnalystReport(
                    headline=data.get("headline", ""),
                    summary=data.get("summary", ""),
                    conviction_level=data.get("conviction_level", "LOW"),
                    thesis=data.get("thesis", ""),
                    key_drivers=data.get("key_drivers", []),
                    contrarian_risks=data.get("contrarian_risks", []),
                    bull_case=data.get("bull_case", {}),
                    base_case=data.get("base_case", {}),
                    bear_case=data.get("bear_case", {}),
                    recommended_action=data.get("recommended_action", ""),
                    entry_zone=data.get("entry_zone", ""),
                    stop_loss=data.get("stop_loss", ""),
                    targets=data.get("targets", []),
                    timeframe=data.get("timeframe", ""),
                    position_sizing=data.get("position_sizing", ""),
                    risk_warnings=data.get("risk_warnings", []),
                    confidence_caveats=data.get(
                        "confidence_caveats",
                        ["Local Qwen analyst online — system status nominal."],
                    ),
                    timestamp=datetime.now(),
                )
        except Exception as chat_err:
            logger.error(f"Ollama chat execution failed: {chat_err}. Using fallback.")
            return self._generate_fallback_report(symbol, price, result_dict)
