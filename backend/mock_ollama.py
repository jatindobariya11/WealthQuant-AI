import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer


class OllamaMockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to stdout to keep logs clean
        return

    def do_GET(self):
        if self.path == "/api/tags":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"models": [{"name": "qwen2.5:7b"}]}
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode("utf-8"))

            # Extract user message prompt
            messages = req_data.get("messages", [])
            prompt = ""
            if messages:
                prompt = messages[-1].get("content", "")

            # Parse prompt parameters using safe regex
            symbol_m = re.search(r"symbol ([A-Z0-9]+)", prompt)
            symbol = symbol_m.group(1) if symbol_m else "NIFTY"

            price_m = re.search(r"spot price ₹([0-9]+(?:\.[0-9]+)?)", prompt)
            price = float(price_m.group(1)) if price_m else 24000.0

            p_up_m = re.search(r"P\(UP\): ([0-9]+(?:\.[0-9]+)?)", prompt)
            p_up = float(p_up_m.group(1)) if p_up_m else 0.4

            p_down_m = re.search(r"P\(DOWN\): ([0-9]+(?:\.[0-9]+)?)", prompt)
            p_down = float(p_down_m.group(1)) if p_down_m else 0.4

            signal_m = re.search(r"Signal: ([A-Z_]+)", prompt)
            signal = signal_m.group(1) if signal_m else "NEUTRAL"

            regime_m = re.search(r"Current Regime: ([A-Z_]+)", prompt)
            regime = regime_m.group(1) if regime_m else "TRANSITION"

            kelly_m = re.search(r"Kelly Fraction: ([0-9]+(?:\.[0-9]+)?)", prompt)
            kelly = float(kelly_m.group(1)) if kelly_m else 0.0

            allocation_m = re.search(
                r"Suggested capital allocation: ([0-9]+(?:\.[0-9]+)?)", prompt
            )
            allocation = float(allocation_m.group(1)) if allocation_m else 0.0

            has_cascade = "Hawkes Cascade Detected: True" in prompt

            # Determine Action
            if "STRONG_BUY" in signal or signal == "STRONG_BUY":
                action = "STRONG BUY / ACCUMULATE"
                conviction = "HIGH"
            elif "BUY" in signal:
                action = "BUY / LONG"
                conviction = "MEDIUM"
            elif "STRONG_SELL" in signal:
                action = "STRONG SELL / SHORT"
                conviction = "HIGH"
            elif "SELL" in signal:
                action = "SELL / SHORT"
                conviction = "MEDIUM"
            else:
                action = "HOLD / NEUTRAL"
                conviction = "LOW"

            entry = (
                f"₹{price:.2f} - ₹{(price * 1.002):.2f}" if "BUY" in signal else "N/A"
            )
            sl = f"₹{(price * 0.985):.2f}" if "BUY" in signal else "N/A"
            targets = (
                [f"₹{(price * 1.01):.2f}", f"₹{(price * 1.02):.2f}"]
                if "BUY" in signal
                else []
            )

            # Formulate warnings dynamically
            risk_warnings = []
            if regime == "HIGH_VOLATILITY":
                risk_warnings.append(
                    "⚠️ High volatility regime may trigger wider stops."
                )

            confidence_caveats = ["Local Qwen analyst online — system status nominal."]

            report = {
                "headline": f"{symbol}: {signal.replace('_', ' ')} conviction in {regime} regime",
                "summary": f"Calibrated probability engine suggests {signal} for {symbol}. Probability of upward move is {p_up * 100:.1f}%, while downward probability is {p_down * 100:.1f}%.",
                "conviction_level": conviction,
                "thesis": f"The stock is currently trading under the {regime} regime. {'Hawkes process event cascade detected.' if has_cascade else 'Hawkes process event activity is at baseline.'} Kelly fraction sizing is {kelly * 100:.1f}%.",
                "key_drivers": [
                    f"Regime status: {regime}",
                    f"Calibrated probability skew: P(UP) = {p_up:.2f}",
                    f"kelly_fraction: {kelly:.4f}",
                ],
                "contrarian_risks": [
                    "Potential regime shift back to TRANSITION",
                    "Model disagreement / conflict in underlying estimates",
                ],
                "bull_case": {
                    "target": f"₹{(price * 1.02):.2f}",
                    "probability": float(p_up),
                    "catalysts": ["Buying volume breakout"],
                },
                "base_case": {
                    "target": f"₹{price:.2f}",
                    "probability": float(max(0.0, 1.0 - p_up - p_down)),
                    "catalysts": ["Consolidation in range"],
                },
                "bear_case": {
                    "target": f"₹{(price * 0.98):.2f}",
                    "probability": float(p_down),
                    "catalysts": ["Global index pressure"],
                },
                "recommended_action": action,
                "entry_zone": entry,
                "stop_loss": sl,
                "targets": targets,
                "timeframe": "1-3 trading days",
                "position_sizing": f"Allocate {allocation * 100:.1f}% of capital",
                "risk_warnings": risk_warnings,
                "confidence_caveats": confidence_caveats,
            }

            response = {"message": {"role": "assistant", "content": json.dumps(report)}}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run(server_class=HTTPServer, handler_class=OllamaMockHandler, port=11434):
    server_address = ("127.0.0.1", port)
    httpd = server_class(server_address, handler_class)
    print(f"Mock Ollama server listening on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
