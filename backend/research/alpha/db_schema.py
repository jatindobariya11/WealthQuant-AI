"""
WealthQuant V9.1 — Alpha Discovery Engine: Database Schema
===========================================================
Creates all PostgreSQL tables required by the Alpha Discovery Engine.
Completely isolated — zero modification to any production table.

New tables:
  alpha_hypotheses          — Auto-generated and manual research hypotheses
  alpha_validation_results  — Full validation result per hypothesis
  alpha_scores              — 6-dimension scoring per validated hypothesis
  alpha_leaderboard         — Accepted alpha ranked by composite score
  alpha_rejected            — Rejected hypotheses with rejection reasons
  alpha_discovery_runs      — Discovery engine run audit log
"""

import asyncio
import logging

logger = logging.getLogger("alpha.db_schema")

# ── DDL Statements ─────────────────────────────────────────────────────────────

DDL_ALPHA_HYPOTHESES = """
CREATE TABLE IF NOT EXISTS alpha_hypotheses (
    hypothesis_id           TEXT PRIMARY KEY,
    source                  TEXT DEFAULT 'auto_discovery',   -- auto_discovery | manual | imported
    generation_method       TEXT,                            -- correlation_mining | mi_screening | interaction | lag_scan | threshold
    title                   TEXT NOT NULL,
    description             TEXT,
    null_hypothesis         TEXT,
    alternative_hypothesis  TEXT,

    -- Research inputs
    symbol                  TEXT DEFAULT 'NIFTY',
    interval                TEXT DEFAULT '1d',
    feature_name            TEXT NOT NULL,
    feature_formula         TEXT,
    feature_category        TEXT,                            -- oi | pcr | wall | iv | microstructure | fii
    target_horizon_days     INT DEFAULT 5,
    lag_days                INT DEFAULT 1,                   -- feature lag applied before IC test

    -- Discovery metadata
    discovery_rank          INT,                             -- rank at time of discovery (by IC)
    candidate_ic            FLOAT8,                          -- raw IC at discovery time
    candidate_pvalue        FLOAT8,                          -- naive p-value (before MHC correction)
    candidate_mi            FLOAT8,                          -- mutual information at discovery
    n_observations          INT,
    discovery_start_date    DATE,
    discovery_end_date      DATE,

    -- Status
    status                  TEXT DEFAULT 'generated',        -- generated | validating | accepted | rejected | archived
    priority                INT DEFAULT 3,

    -- Audit
    generated_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    discovery_run_id        TEXT
);

CREATE INDEX IF NOT EXISTS idx_alpha_hyp_status    ON alpha_hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_alpha_hyp_category  ON alpha_hypotheses(feature_category);
CREATE INDEX IF NOT EXISTS idx_alpha_hyp_ic        ON alpha_hypotheses(candidate_ic DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_alpha_hyp_run       ON alpha_hypotheses(discovery_run_id);
"""

DDL_ALPHA_VALIDATION_RESULTS = """
CREATE TABLE IF NOT EXISTS alpha_validation_results (
    result_id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    hypothesis_id           TEXT REFERENCES alpha_hypotheses(hypothesis_id),
    validated_at            TIMESTAMPTZ DEFAULT NOW(),

    -- IC metrics
    ic_1d                   FLOAT8,
    ic_3d                   FLOAT8,
    ic_5d                   FLOAT8,
    ic_10d                  FLOAT8,
    ic_tstat                FLOAT8,
    ic_pvalue               FLOAT8,
    ic_pvalue_adjusted      FLOAT8,         -- after BH correction

    -- Mutual information
    mutual_information      FLOAT8,

    -- Correlation
    spearman_corr           FLOAT8,
    pearson_corr            FLOAT8,
    partial_corr            FLOAT8,
    partial_corr_pvalue     FLOAT8,

    -- Leakage
    ic_same_day             FLOAT8,
    ic_next_day             FLOAT8,
    leakage_ratio           FLOAT8,
    leakage_status          TEXT DEFAULT 'pending',          -- CLEAN | SUSPECTED | CONFIRMED

    -- Walk-Forward
    wf_mean_ic              FLOAT8,
    wf_std_ic               FLOAT8,
    wf_icir                 FLOAT8,
    wf_pct_positive         FLOAT8,
    wf_n_folds              INT,
    wf_passed               BOOLEAN,
    wf_ic_per_fold          JSONB DEFAULT '[]',

    -- Monte Carlo
    mc_observed_ic          FLOAT8,
    mc_pvalue               FLOAT8,
    mc_pvalue_adjusted      FLOAT8,
    mc_passed               BOOLEAN,
    mc_n_permutations       INT DEFAULT 1000,

    -- Bootstrap
    boot_ic_lower           FLOAT8,
    boot_ic_upper           FLOAT8,
    boot_ic_mean            FLOAT8,
    boot_passed             BOOLEAN,
    boot_n_bootstraps       INT DEFAULT 1000,

    -- SHAP
    shap_importance         FLOAT8,
    shap_rank               INT,

    -- Ablation
    ablation_ic_degradation FLOAT8,
    is_necessary            BOOLEAN,

    -- Sensitivity
    sensitivity_robustness  FLOAT8,         -- IC std / IC mean across param grid
    is_robust               BOOLEAN,

    -- PSI / drift
    psi_score               FLOAT8,
    is_drifting             BOOLEAN,

    -- Regime breakdown
    regime_ic               JSONB DEFAULT '{}',   -- {regime_name: ic}
    regime_stability        FLOAT8,               -- std of IC across regimes

    -- VIF
    vif_score               FLOAT8,

    -- Runtime
    validation_seconds      FLOAT8,
    validation_seed         INT DEFAULT 42
);

CREATE INDEX IF NOT EXISTS idx_alpha_val_hypothesis ON alpha_validation_results(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_alpha_val_wf_passed  ON alpha_validation_results(wf_passed);
CREATE INDEX IF NOT EXISTS idx_alpha_val_mc_pvalue  ON alpha_validation_results(mc_pvalue);
"""

DDL_ALPHA_SCORES = """
CREATE TABLE IF NOT EXISTS alpha_scores (
    score_id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    hypothesis_id           TEXT UNIQUE REFERENCES alpha_hypotheses(hypothesis_id),
    scored_at               TIMESTAMPTZ DEFAULT NOW(),

    -- 6 dimensions (each 0-100)
    novelty_score           FLOAT8 DEFAULT 0,
    predictive_power_score  FLOAT8 DEFAULT 0,
    significance_score      FLOAT8 DEFAULT 0,
    regime_stability_score  FLOAT8 DEFAULT 0,
    research_health_score   FLOAT8 DEFAULT 0,
    production_readiness    FLOAT8 DEFAULT 0,

    -- Composite
    composite_score         FLOAT8 DEFAULT 0,    -- weighted sum

    -- Component details
    novelty_detail          JSONB DEFAULT '{}',
    predictive_power_detail JSONB DEFAULT '{}',
    significance_detail     JSONB DEFAULT '{}',
    stability_detail        JSONB DEFAULT '{}',
    health_detail           JSONB DEFAULT '{}',
    production_detail       JSONB DEFAULT '{}',

    -- Overall verdict
    passed_all_gates        BOOLEAN DEFAULT FALSE,
    recommendation          TEXT DEFAULT 'REJECT'   -- ACCEPT | WATCH | REJECT
);

CREATE INDEX IF NOT EXISTS idx_alpha_scores_composite ON alpha_scores(composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_alpha_scores_rec       ON alpha_scores(recommendation);
"""

DDL_ALPHA_LEADERBOARD = """
CREATE TABLE IF NOT EXISTS alpha_discovery_leaderboard (
    leaderboard_id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    hypothesis_id           TEXT REFERENCES alpha_hypotheses(hypothesis_id),
    accepted_at             TIMESTAMPTZ DEFAULT NOW(),
    rank                    INT,

    -- Key metrics snapshot
    composite_score         FLOAT8,
    ic_5d                   FLOAT8,
    icir                    FLOAT8,
    mc_pvalue               FLOAT8,
    boot_ic_lower           FLOAT8,
    leakage_status          TEXT,
    regime_stability        FLOAT8,
    production_ready        BOOLEAN DEFAULT FALSE,

    -- Production candidate details
    production_notes        TEXT,
    ips_candidate           BOOLEAN DEFAULT FALSE,
    ips_integration_date    DATE,

    -- Evidence
    evidence_summary        TEXT,
    failure_modes           JSONB DEFAULT '[]',
    regime_dependence       TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alpha_lb_hypothesis ON alpha_discovery_leaderboard(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_alpha_lb_rank             ON alpha_discovery_leaderboard(rank ASC);
CREATE INDEX IF NOT EXISTS idx_alpha_lb_score            ON alpha_discovery_leaderboard(composite_score DESC);
"""

DDL_ALPHA_REJECTED = """
CREATE TABLE IF NOT EXISTS alpha_rejected (
    rejection_id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    hypothesis_id           TEXT REFERENCES alpha_hypotheses(hypothesis_id),
    rejected_at             TIMESTAMPTZ DEFAULT NOW(),

    -- Rejection classification
    rejection_category      TEXT NOT NULL,   -- weak | unstable | leaked | overfit | duplicate
    rejection_reasons       JSONB DEFAULT '[]',
    gate_failed             TEXT,            -- which acceptance gate failed first

    -- Evidence
    ic_5d                   FLOAT8,
    mc_pvalue               FLOAT8,
    leakage_status          TEXT,
    wf_pct_positive         FLOAT8,
    composite_score         FLOAT8,

    -- Duplicate detection (if applicable)
    duplicate_of            TEXT,           -- hypothesis_id of the duplicate target
    correlation_with_dup    FLOAT8,

    -- Notes
    notes                   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alpha_rej_hypothesis ON alpha_rejected(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_alpha_rej_category         ON alpha_rejected(rejection_category);
"""

DDL_ALPHA_DISCOVERY_RUNS = """
CREATE TABLE IF NOT EXISTS alpha_discovery_runs (
    run_id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    started_at              TIMESTAMPTZ DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    status                  TEXT DEFAULT 'running',   -- running | complete | failed

    -- Configuration
    symbol                  TEXT,
    interval                TEXT,
    data_start              DATE,
    data_end                DATE,
    n_features_scanned      INT DEFAULT 0,
    generation_methods      JSONB DEFAULT '[]',

    -- Results
    n_candidates_generated  INT DEFAULT 0,
    n_validated             INT DEFAULT 0,
    n_accepted              INT DEFAULT 0,
    n_rejected              INT DEFAULT 0,

    -- Breakdown by rejection category
    rejected_weak           INT DEFAULT 0,
    rejected_unstable       INT DEFAULT 0,
    rejected_leaked         INT DEFAULT 0,
    rejected_overfit        INT DEFAULT 0,
    rejected_duplicate      INT DEFAULT 0,

    -- Performance
    runtime_seconds         FLOAT8,
    error_message           TEXT
);

CREATE INDEX IF NOT EXISTS idx_alpha_runs_started ON alpha_discovery_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_alpha_runs_status  ON alpha_discovery_runs(status);
"""

ALL_DDL = [
    ("alpha_hypotheses", DDL_ALPHA_HYPOTHESES),
    ("alpha_validation_results", DDL_ALPHA_VALIDATION_RESULTS),
    ("alpha_scores", DDL_ALPHA_SCORES),
    ("alpha_discovery_leaderboard", DDL_ALPHA_LEADERBOARD),
    ("alpha_rejected", DDL_ALPHA_REJECTED),
    ("alpha_discovery_runs", DDL_ALPHA_DISCOVERY_RUNS),
]


async def create_alpha_tables(pool) -> dict:
    """
    Create all alpha discovery tables in PostgreSQL.
    Idempotent — safe to run on every startup.

    Args:
        pool: asyncpg connection pool

    Returns:
        dict with status per table
    """
    results = {}
    if pool is None:
        logger.warning("[AlphaDB] No pool — skipping alpha table creation")
        return {"status": "skipped", "reason": "no_pool"}

    async with pool.acquire() as conn:
        for table_name, ddl in ALL_DDL:
            try:
                await conn.execute(ddl)
                results[table_name] = "ready"
                logger.info(f"[AlphaDB] Table ready: {table_name}")
            except Exception as e:
                results[table_name] = f"error: {e}"
                logger.error(f"[AlphaDB] Failed to create {table_name}: {e}")

    results["status"] = "complete"
    ready = sum(1 for v in results.values() if v == "ready")
    logger.info(f"[AlphaDB] Schema bootstrap: {ready}/{len(ALL_DDL)} tables ready")
    return results


async def get_alpha_db_stats(pool) -> dict:
    """Return row counts for all alpha tables."""
    if pool is None:
        return {"status": "offline"}

    stats = {}
    async with pool.acquire() as conn:
        for table_name, _ in ALL_DDL:
            try:
                row = await conn.fetchrow(f"SELECT COUNT(*) AS n FROM {table_name};")
                stats[table_name] = {"rows": int(row["n"]), "status": "ok"}
            except Exception as e:
                stats[table_name] = {"rows": 0, "status": f"error: {e}"}
    return stats


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )

    async def _bootstrap():
        from pipeline.config import POSTGRES_CONFIG

        try:
            import asyncpg

            pool = await asyncpg.create_pool(**POSTGRES_CONFIG)
            result = await create_alpha_tables(pool)
            print(f"Bootstrap: {result}")
            stats = await get_alpha_db_stats(pool)
            print(f"Stats: {stats}")
            await pool.close()
        except ImportError:
            print("asyncpg not installed")
        except Exception as e:
            print(f"Failed: {e}")

    asyncio.run(_bootstrap())
