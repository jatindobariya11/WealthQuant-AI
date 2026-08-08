from signal_engine.base import SignalContributor
from typing import Dict, Any
from signaldesk_engine import (
    _compute_options_sentiment, _compute_breadth_metrics, 
    _compute_risk_metrics, _compute_market_context, 
    _compute_regime_signal, _compute_trade_levels
)

class MacroContributor(SignalContributor):
    def compute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return {'macro_context': _compute_market_context(data.get('df'), data.get('price')) if 'df' in data else {}}
