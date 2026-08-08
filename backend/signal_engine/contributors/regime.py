from signal_engine.base import SignalContributor
from typing import Dict, Any
from signaldesk_engine import (
    _compute_options_sentiment, _compute_breadth_metrics, 
    _compute_risk_metrics, _compute_market_context, 
    _compute_regime_signal, _compute_trade_levels
)

class RegimeContributor(SignalContributor):
    def compute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sig_data, is_long, fii_aligned = _compute_regime_signal(
                data.get('ts'), data.get('mtf_data'), data.get('vix_data'), data.get('global_data'), data.get('fii_data'),
                context.get('options_sentiment', {}).get('oi_score'),
                context.get('breadth_metrics'), data.get('quant_conf'), data.get('quant_data')
            )
            return {'regime': {'sig_data': sig_data, 'is_long': is_long, 'fii_aligned': fii_aligned}}
        except: return {}
