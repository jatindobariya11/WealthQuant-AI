"""
WealthQuant V9.1 — Alpha Discovery Engine: Alpha Registry
=========================================================
PostgreSQL persistence and querying engine for all alpha hypotheses, validation runs,
rejections, scores, and accepted leaderboard entries.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("alpha.registry")


class AlphaStatus:
    GENERATED = "generated"
    VALIDATING = "validating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


@dataclass
class AlphaRecord:
    hypothesis_id: str
    source: str
    generation_method: str
    title: str
    description: str
    null_hypothesis: str
    alternative_hypothesis: str
    symbol: str
    interval: str
    feature_name: str
    feature_formula: str
    feature_category: str
    target_horizon_days: int
    lag_days: int
    candidate_ic: float
    status: str
    created_at: datetime | None = None


class AlphaRegistry:
    """
    Persistence layer for Alpha Discovery Engine using asyncpg.
    """

    def __init__(self, pool):
        self.pool = pool

    async def save_hypothesis(self, hyp: dict, run_id: str | None = None) -> bool:
        if self.pool is None:
            return False

        query = """
            INSERT INTO alpha_hypotheses (
                hypothesis_id, source, generation_method, title, description,
                null_hypothesis, alternative_hypothesis, symbol, interval,
                feature_name, feature_formula, feature_category, target_horizon_days,
                lag_days, candidate_ic, status, discovery_run_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            ON CONFLICT (hypothesis_id) DO UPDATE SET
                status = EXCLUDED.status,
                updated_at = NOW();
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    hyp["hypothesis_id"],
                    hyp.get("source", "auto_discovery"),
                    hyp.get("generation_method", "correlation_mining"),
                    hyp["title"],
                    hyp.get("description", ""),
                    hyp.get("null_hypothesis", ""),
                    hyp.get("alternative_hypothesis", ""),
                    hyp.get("symbol", "NIFTY"),
                    hyp.get("interval", "1d"),
                    hyp["feature_name"],
                    hyp.get("feature_formula", hyp["feature_name"]),
                    hyp.get("feature_category", "general"),
                    hyp.get("target_horizon_days", 5),
                    hyp.get("lag_days", 1),
                    hyp.get("candidate_ic", 0.0),
                    hyp.get("status", AlphaStatus.GENERATED),
                    run_id,
                )
            return True
        except Exception as e:
            logger.error(f"[Registry] Save hypothesis failed: {e}")
            return False

    async def save_validation_result(self, hyp_id: str, val_res: dict) -> bool:
        if self.pool is None:
            return False

        query = """
            INSERT INTO alpha_validation_results (
                hypothesis_id, ic_1d, ic_3d, ic_5d, ic_10d, ic_tstat, ic_pvalue, ic_pvalue_adjusted,
                mutual_information, spearman_corr, pearson_corr, partial_corr, partial_corr_pvalue,
                ic_same_day, ic_next_day, leakage_ratio, leakage_status,
                wf_mean_ic, wf_std_ic, wf_icir, wf_pct_positive, wf_n_folds, wf_passed, wf_ic_per_fold,
                mc_observed_ic, mc_pvalue, mc_pvalue_adjusted, mc_passed,
                boot_ic_lower, boot_ic_upper, boot_ic_mean, boot_passed,
                psi_score, is_drifting, regime_ic, regime_stability, vif_score, validation_seconds
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17,
                $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32,
                $33, $34, $35, $36, $37, $38
            );
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    hyp_id,
                    val_res.get("ic_1d"),
                    val_res.get("ic_3d"),
                    val_res.get("ic_5d"),
                    val_res.get("ic_10d"),
                    val_res.get("ic_tstat"),
                    val_res.get("ic_pvalue"),
                    val_res.get("ic_pvalue_adjusted"),
                    val_res.get("mutual_information"),
                    val_res.get("spearman_corr"),
                    val_res.get("pearson_corr"),
                    val_res.get("partial_corr"),
                    val_res.get("partial_corr_pvalue"),
                    val_res.get("ic_same_day"),
                    val_res.get("ic_next_day"),
                    val_res.get("leakage_ratio"),
                    val_res.get("leakage_status"),
                    val_res.get("wf_mean_ic"),
                    val_res.get("wf_std_ic"),
                    val_res.get("wf_icir"),
                    val_res.get("wf_pct_positive"),
                    val_res.get("wf_n_folds"),
                    val_res.get("wf_passed"),
                    json.dumps(val_res.get("wf_ic_per_fold", [])),
                    val_res.get("mc_observed_ic"),
                    val_res.get("mc_pvalue"),
                    val_res.get("mc_pvalue_adjusted"),
                    val_res.get("mc_passed"),
                    val_res.get("boot_ic_lower"),
                    val_res.get("boot_ic_upper"),
                    val_res.get("boot_ic_mean"),
                    val_res.get("boot_passed"),
                    val_res.get("psi_score"),
                    val_res.get("is_drifting"),
                    json.dumps(val_res.get("regime_ic", {})),
                    val_res.get("regime_stability"),
                    val_res.get("vif_score"),
                    val_res.get("validation_seconds"),
                )
            return True
        except Exception as e:
            logger.error(f"[Registry] Save validation result failed: {e}")
            return False

    async def save_score(self, score_obj) -> bool:
        if self.pool is None:
            return False

        query = """
            INSERT INTO alpha_scores (
                hypothesis_id, novelty_score, predictive_power_score, significance_score,
                regime_stability_score, research_health_score, production_readiness,
                composite_score, novelty_detail, predictive_power_detail, significance_detail,
                stability_detail, health_detail, production_detail, passed_all_gates, recommendation
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            ON CONFLICT (hypothesis_id) DO UPDATE SET
                composite_score = EXCLUDED.composite_score,
                recommendation = EXCLUDED.recommendation,
                scored_at = NOW();
        """
        try:
            d = score_obj.details
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    score_obj.hypothesis_id,
                    score_obj.novelty_score,
                    score_obj.predictive_power_score,
                    score_obj.significance_score,
                    score_obj.regime_stability_score,
                    score_obj.research_health_score,
                    score_obj.production_readiness_score,
                    score_obj.composite_score,
                    json.dumps(d.get("novelty", {})),
                    json.dumps(d.get("predictive_power", {})),
                    json.dumps(d.get("significance", {})),
                    json.dumps(d.get("regime_stability", {})),
                    json.dumps(d.get("research_health", {})),
                    json.dumps(d.get("production_readiness", {})),
                    score_obj.passed_all_gates,
                    score_obj.recommendation,
                )
            return True
        except Exception as e:
            logger.error(f"[Registry] Save score failed: {e}")
            return False

    async def record_acceptance(
        self, hyp_id: str, score_val: float, val_res: dict
    ) -> bool:
        if self.pool is None:
            return False

        # 1. Update hypothesis status
        await self._update_status(hyp_id, AlphaStatus.ACCEPTED)

        # 2. Insert into leaderboard
        query = """
            INSERT INTO alpha_discovery_leaderboard (
                hypothesis_id, composite_score, ic_5d, icir, mc_pvalue, boot_ic_lower,
                leakage_status, regime_stability, production_ready, evidence_summary
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (hypothesis_id) DO UPDATE SET
                composite_score = EXCLUDED.composite_score,
                accepted_at = NOW();
        """
        summary = f"Accepted alpha. IC_5d={val_res.get('ic_5d')}, ICIR={val_res.get('wf_icir')}, MC_p={val_res.get('mc_pvalue')}"
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    hyp_id,
                    score_val,
                    val_res.get("ic_5d"),
                    val_res.get("wf_icir"),
                    val_res.get("mc_pvalue"),
                    val_res.get("boot_ic_lower"),
                    val_res.get("leakage_status"),
                    val_res.get("regime_stability"),
                    True,
                    summary,
                )
            return True
        except Exception as e:
            logger.error(f"[Registry] Record acceptance failed: {e}")
            return False

    async def record_rejection(self, hyp_id: str, rej_res) -> bool:
        if self.pool is None:
            return False

        await self._update_status(hyp_id, AlphaStatus.REJECTED)

        query = """
            INSERT INTO alpha_rejected (
                hypothesis_id, rejection_category, rejection_reasons, gate_failed,
                ic_5d, mc_pvalue, leakage_status, wf_pct_positive, composite_score,
                duplicate_of, correlation_with_dup
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (hypothesis_id) DO NOTHING;
        """
        m = rej_res.metrics_summary
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    hyp_id,
                    rej_res.category.value,
                    json.dumps(rej_res.rejection_reasons),
                    rej_res.failed_gate,
                    m.get("ic_5d"),
                    m.get("mc_pvalue"),
                    val_res.get("leakage_status")
                    if (val_res := m.get("val_res"))
                    else "CLEAN",
                    m.get("wf_pct_positive"),
                    m.get("health_score"),
                    rej_res.duplicate_of,
                    rej_res.duplicate_correlation,
                )
            return True
        except Exception as e:
            logger.error(f"[Registry] Record rejection failed: {e}")
            return False

    async def _update_status(self, hyp_id: str, status: str):
        query = "UPDATE alpha_hypotheses SET status = $1, updated_at = NOW() WHERE hypothesis_id = $2;"
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, status, hyp_id)
        except Exception:
            pass

    async def get_accepted_alphas(self) -> list[dict]:
        if self.pool is None:
            return []
        query = """
            SELECT h.*, l.composite_score, l.ic_5d, l.icir
            FROM alpha_discovery_leaderboard l
            JOIN alpha_hypotheses h ON l.hypothesis_id = h.hypothesis_id
            ORDER BY l.composite_score DESC;
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query)
            return [dict(r) for r in rows]
        except Exception:
            return []
