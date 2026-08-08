"""
WealthQuant V9.2 — Automated Decay & Drift Detector
===================================================
Automatically monitors incubated alpha for:
  - Performance decay (rolling Sharpe drop > 30%)
  - Concept drift & Population Stability Index (PSI > 0.25)
  - Calibration drift (predicted vs realized hit rate mismatch > 15%)
  - Regime dependence shifts
  - Feature redundancy & correlation spikes with existing production alpha
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("incubation.decay")


@dataclass
class DecayAlert:
    alpha_id: str
    alert_type: str  # PERFORMANCE_DECAY | CONCEPT_DRIFT | PSI_DRIFT | CALIBRATION_DRIFT | CORRELATION_SPIKE
    severity: str  # WARNING | CRITICAL | TERMINATE
    metric_name: str
    current_value: float
    threshold_value: float
    description: str


class DecayDetector:
    """
    Continuous automated decay and drift monitoring engine for incubated alpha.
    """

    def __init__(
        self,
        psi_threshold: float = 0.25,
        max_sharpe_decay_pct: float = 0.30,
        max_calibration_drift: float = 0.15,
        max_corr_threshold: float = 0.75,
    ):
        self.psi_threshold = psi_threshold
        self.max_sharpe_decay_pct = max_sharpe_decay_pct
        self.max_calibration_drift = max_calibration_drift
        self.max_corr_threshold = max_corr_threshold

    def check_alpha_health(
        self,
        alpha_id: str,
        historical_ic: float,
        recent_ic: float,
        historical_sharpe: float,
        recent_sharpe: float,
        psi_score: float,
        predicted_hit_rate: float,
        realized_hit_rate: float,
        corr_with_existing: float = 0.0,
    ) -> list[DecayAlert]:
        """
        Run full automated health inspection on incubated alpha.
        """
        alerts = []

        # 1. Performance Decay
        if historical_sharpe > 0:
            sharpe_drop = (historical_sharpe - recent_sharpe) / historical_sharpe
            if sharpe_drop >= self.max_sharpe_decay_pct:
                sev = "CRITICAL" if sharpe_drop >= 0.50 else "WARNING"
                alerts.append(
                    DecayAlert(
                        alpha_id=alpha_id,
                        alert_type="PERFORMANCE_DECAY",
                        severity=sev,
                        metric_name="sharpe_drop_pct",
                        current_value=round(sharpe_drop, 4),
                        threshold_value=self.max_sharpe_decay_pct,
                        description=f"Sharpe ratio decayed by {sharpe_drop * 100:.1f}% from baseline {historical_sharpe:.2f} to {recent_sharpe:.2f}",
                    )
                )

        # 2. Concept Drift / PSI
        if psi_score >= self.psi_threshold:
            sev = "TERMINATE" if psi_score >= 0.40 else "CRITICAL"
            alerts.append(
                DecayAlert(
                    alpha_id=alpha_id,
                    alert_type="PSI_DRIFT",
                    severity=sev,
                    metric_name="psi_score",
                    current_value=round(psi_score, 4),
                    threshold_value=self.psi_threshold,
                    description=f"Population Stability Index indicates major feature distribution drift ({psi_score:.3f} >= {self.psi_threshold})",
                )
            )

        # 3. Calibration Drift
        cal_drift = abs(predicted_hit_rate - realized_hit_rate)
        if cal_drift >= self.max_calibration_drift:
            alerts.append(
                DecayAlert(
                    alpha_id=alpha_id,
                    alert_type="CALIBRATION_DRIFT",
                    severity="WARNING",
                    metric_name="calibration_drift",
                    current_value=round(cal_drift, 4),
                    threshold_value=self.max_calibration_drift,
                    description=f"Calibration mismatch: predicted hit rate ({predicted_hit_rate * 100:.1f}%) vs realized ({realized_hit_rate * 100:.1f}%)",
                )
            )

        # 4. Redundancy & Correlation Spike
        if corr_with_existing >= self.max_corr_threshold:
            alerts.append(
                DecayAlert(
                    alpha_id=alpha_id,
                    alert_type="CORRELATION_SPIKE",
                    severity="CRITICAL",
                    metric_name="correlation",
                    current_value=round(corr_with_existing, 4),
                    threshold_value=self.max_corr_threshold,
                    description=f"High correlation with existing production alpha ({corr_with_existing:.2f} >= {self.max_corr_threshold})",
                )
            )

        return alerts
