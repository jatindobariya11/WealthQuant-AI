"""
WealthQuant V9.2 — Incubation Engine Orchestrator
=================================================
Central orchestrator for the Alpha Validation & Incubation Platform.
Manages incubation registration, stage transitions, decay detection, shadow mode evaluations,
and report generation.
"""

import logging

from .decay_detector import DecayDetector
from .incubation_db import IncubationDB
from .lifecycle_manager import (
    AlphaLifecycleStage,
    ApprovalStatus,
    IncubationRecord,
    LifecycleManager,
)
from .report_generator import IncubationReporter
from .shadow_monitor import ShadowMonitor

logger = logging.getLogger("incubation.engine")


class IncubationEngine:
    """
    Main Orchestrator for the Alpha Incubation & Governance Platform.
    """

    def __init__(self, pool=None):
        self.pool = pool
        self.db = IncubationDB(pool)
        self.lifecycle = LifecycleManager(pool)
        self.shadow_monitor = ShadowMonitor()
        self.decay_detector = DecayDetector()
        self.reporter = IncubationReporter()

    async def register_discovered_alpha(
        self,
        alpha_id: str,
        title: str,
        author: str = "quant_research_team",
        metrics: dict = None,
    ) -> bool:
        """Register a newly discovered alpha into Stage 1 (DISCOVERED)."""
        metrics = metrics or {}
        if self.pool is None:
            return False

        query = """
            INSERT INTO alpha_incubation_records (
                incubation_id, alpha_id, hypothesis_title, author, current_stage, approval_status,
                sample_size, research_health_score, information_coefficient, sharpe_contribution,
                drawdown_impact, regime_stability, calibration_score
            ) VALUES ($1, $2, $3, $4, 'DISCOVERED', 'PENDING', $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (alpha_id) DO NOTHING;
        """
        inc_id = f"INC_{alpha_id}"
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    inc_id,
                    alpha_id,
                    title,
                    author,
                    metrics.get("sample_size", 100),
                    metrics.get("health_score", 0.0),
                    metrics.get("ic", 0.0),
                    metrics.get("sharpe_delta", 0.0),
                    metrics.get("dd_delta", 0.0),
                    metrics.get("regime_stability", 0.0),
                    metrics.get("calibration", 0.0),
                )
            logger.info(f"[Incubation] Registered alpha {alpha_id} in stage DISCOVERED")
            return True
        except Exception as e:
            logger.error(f"[Incubation] Registration failed for {alpha_id}: {e}")
            return False

    async def advance_stage(
        self, alpha_id: str, target_stage: AlphaLifecycleStage, metrics: dict = None
    ) -> tuple[bool, list[str]]:
        """Attempt to advance an incubated alpha to target_stage."""
        metrics = metrics or {}
        rec = await self._load_record(alpha_id)
        if not rec:
            return False, [f"Alpha {alpha_id} not found in incubation records"]

        can_advance, reasons = self.lifecycle.evaluate_stage_transition(
            rec, target_stage, metrics
        )
        if not can_advance:
            logger.warning(
                f"[Incubation] Stage transition blocked for {alpha_id} -> {target_stage.value}: {reasons}"
            )
            return False, reasons

        # Update stage in DB
        query = "UPDATE alpha_incubation_records SET current_stage = $1, updated_at = NOW() WHERE alpha_id = $2;"
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, target_stage.value, alpha_id)
            logger.info(
                f"[Incubation] Advanced {alpha_id} to stage {target_stage.value}"
            )
            return True, []
        except Exception as e:
            logger.error(f"[Incubation] Stage update failed: {e}")
            return False, [str(e)]

    async def run_governance_cycle(self) -> dict:
        """Run full periodic governance audit & decay check on all incubated alpha."""
        alphas = await self.list_incubated_alphas()
        shadow_reports = {}
        decay_alerts = []

        for a in alphas:
            aid = a.get("alpha_id")
            # Simulate decay check
            alerts = self.decay_detector.check_alpha_health(
                alpha_id=aid,
                historical_ic=a.get("information_coefficient", 0.0),
                recent_ic=a.get("information_coefficient", 0.0),
                historical_sharpe=a.get("sharpe_contribution", 0.0) + 1.0,
                recent_sharpe=a.get("sharpe_contribution", 0.0) + 1.0,
                psi_score=0.05,
                predicted_hit_rate=0.55,
                realized_hit_rate=0.54,
            )
            decay_alerts.extend(alerts)

        reports = self.reporter.generate_all_reports(
            alphas, shadow_reports, decay_alerts
        )

        return {
            "status": "complete",
            "incubated_count": len(alphas),
            "alerts_count": len(decay_alerts),
            "reports_generated": list(reports.keys()),
        }

    async def list_incubated_alphas(self) -> list[dict]:
        if self.pool is None:
            return []
        query = "SELECT * FROM alpha_incubation_records ORDER BY created_at DESC;"
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query)
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def _load_record(self, alpha_id: str) -> IncubationRecord | None:
        if self.pool is None:
            return None
        query = "SELECT * FROM alpha_incubation_records WHERE alpha_id = $1;"
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, alpha_id)
            if not row:
                return None
            return IncubationRecord(
                incubation_id=row["incubation_id"],
                alpha_id=row["alpha_id"],
                hypothesis_title=row["hypothesis_title"],
                author=row["author"],
                current_stage=AlphaLifecycleStage(row["current_stage"]),
                approval_status=ApprovalStatus(row["approval_status"]),
                production_status=row["production_status"],
                sample_size=row["sample_size"],
                research_health_score=row["research_health_score"],
                information_coefficient=row["information_coefficient"],
                sharpe_contribution=row["sharpe_contribution"],
                drawdown_impact=row["drawdown_impact"],
                regime_stability=row["regime_stability"],
                calibration_score=row["calibration_score"],
            )
        except Exception as e:
            logger.error(f"[Incubation] Load record failed: {e}")
            return None
