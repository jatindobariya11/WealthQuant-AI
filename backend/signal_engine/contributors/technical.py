from signal_engine.base import SignalContributor
from typing import Dict, Any
from signaldesk_engine import (
    _compute_options_sentiment, _compute_breadth_metrics, 
    _compute_risk_metrics, _compute_market_context, 
    _compute_regime_signal, _compute_trade_levels
)

class TechnicalContributor(SignalContributor):
    def compute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            regime = context.get('regime', {})
            entry_exit, sr_zone, ns, nr = _compute_trade_levels(data.get('price'), data.get('levels'), data.get('atr_v'), regime.get('sig_data', {}).get('signal'))
            return {'technical': {'entry_exit': entry_exit, 'sr_zone': sr_zone, 'ns': ns, 'nr': nr}}
        except: return {}
