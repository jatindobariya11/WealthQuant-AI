from signal_engine.base import SignalContributor
from typing import Dict, Any
from signaldesk_engine import (
    _compute_options_sentiment, _compute_breadth_metrics, 
    _compute_risk_metrics, _compute_market_context, 
    _compute_regime_signal, _compute_trade_levels
)

class OptionsContributor(SignalContributor):
    def compute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return {'options_sentiment': _compute_options_sentiment(data.get('opts_data'))}
