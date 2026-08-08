"""
WealthQuant V9.0 — Research Laboratory Database Schema Bootstrap
================================================================
Creates all PostgreSQL tables required by the Research Laboratory.
This is completely isolated from the production prediction pipeline.
Run once on first launch, idempotent (CREATE TABLE IF NOT EXISTS).

Tables created:
  research_experiments          — Experiment records and results
  research_hypotheses           — Hypothesis registry
  research_feature_evaluations  — Feature evaluation results
  research_validation_runs      — WF/MC/Bootstrap audit trail
  research_reports              — Generated report metadata

DO NOT run migrations on production tables. This only creates new research tables.
"""

import asyncio
import logging

logger = logging.getLogger("research.db_schema")

# ── Research table DDL ────────────────────────────────────────────────────────

DDL_RESEARCH_EXPERIMENTS = """
CREATE TABLE IF NOT EXISTS research_experiments (
    experiment_id           TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    research_question       TEXT,
    hypothesis              TEXT,
    null_hypothesis         TEXT,
    alternative_hypothesis  TEXT,
    category                TEXT,
    researcher              TEXT DEFAULT 'wealthquant_research',
    status                  TEXT DEFAULT 'draft',

    -- Data configuration
    symbol                  TEXT,
    interval                TEXT DEFAULT '1d',
    data_start              DATE,
    data_end                DATE,
    features_used           JSONB DEFAULT '[]',

    -- Walk-Forward results
    wf_mean_ic              FLOAT8,
    wf_std_ic               FLOAT8,
    wf_icir                 FLOAT8,
    wf_pct_positive         FLOAT8,
    wf_n_folds              INT,
    wf_passed               BOOLEAN,

    -- Monte Carlo results
    mc_observed_ic          FLOAT8,
    mc_pvalue               FLOAT8,
    mc_n_permutations       INT DEFAULT 1000,
    mc_passed               BOOLEAN,

    -- Bootstrap results
    boot_ic_lower           FLOAT8,
    boot_ic_upper           FLOAT8,
    boot_n_bootstraps       INT DEFAULT 1000,
    boot_passed             BOOLEAN,

    -- Leakage
    leakage_status          TEXT DEFAULT 'pending',
    ic_same_day             FLOAT8,
    ic_next_day             FLOAT8,

    -- Performance impact
    baseline_sharpe         FLOAT8,
    enhanced_sharpe         FLOAT8,
    sharpe_improvement      FLOAT8,
    baseline_max_drawdown   FLOAT8,
    enhanced_max_drawdown   FLOAT8,
    drawdown_improvement    FLOAT8,

    -- Feature metrics
    information_coefficient FLOAT8,
    feature_importance      JSONB DEFAULT '{}',

    -- Research health
    research_health_score   FLOAT8,
    recommendation          TEXT,
    rejection_reasons       JSONB DEFAULT '[]',
    notes                   TEXT,

    -- Audit
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    version                 INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_research_experiments_status
    ON research_experiments(status);
CREATE INDEX IF NOT EXISTS idx_research_experiments_category
    ON research_experiments(category);
CREATE INDEX IF NOT EXISTS idx_research_experiments_health_score
    ON research_experiments(research_health_score DESC);
CREATE INDEX IF NOT EXISTS idx_research_experiments_created
    ON research_experiments(created_at DESC);
"""

DDL_RESEARCH_HYPOTHESES = """
CREATE TABLE IF NOT EXISTS research_hypotheses (
    hypothesis_id           TEXT PRIMARY KEY,
    title                   TEXT NOT NULL,
    description             TEXT,
    null_hypothesis         TEXT,
    alternative_hypothesis  TEXT,
    category                TEXT,
    rationale               TEXT,
    academic_references     JSONB DEFAULT '[]',
    expected_ic_low         FLOAT8,
    expected_ic_high        FLOAT8,
    expected_horizon_days   INT,
    required_data_days      INT,
    priority                INT DEFAULT 3,
    status                  TEXT DEFAULT 'proposed',
    linked_experiment_ids   JSONB DEFAULT '[]',
    tags                    JSONB DEFAULT '[]',
    leakage_risk            TEXT DEFAULT 'low',
    complexity              TEXT DEFAULT 'moderate',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_hypotheses_category
    ON research_hypotheses(category);
CREATE INDEX IF NOT EXISTS idx_research_hypotheses_status
    ON research_hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_research_hypotheses_priority
    ON research_hypotheses(priority ASC);
"""

DDL_RESEARCH_FEATURE_EVALUATIONS = """
CREATE TABLE IF NOT EXISTS research_feature_evaluations (
    evaluation_id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    feature_name            TEXT NOT NULL,
    evaluated_at            TIMESTAMPTZ DEFAULT NOW(),
    symbol                  TEXT,
    interval                TEXT,
    data_start              DATE,
    data_end                DATE,
    n_observations          INT,

    -- IC metrics
    ic_1d                   FLOAT8,
    ic_3d                   FLOAT8,
    ic_5d                   FLOAT8,
    ic_10d                  FLOAT8,
    ic_decay_halflife       FLOAT8,

    -- Distributional
    mean_val                FLOAT8,
    std_val                 FLOAT8,
    skewness                FLOAT8,
    kurtosis                FLOAT8,
    pct_missing             FLOAT8,

    -- Redundancy
    max_correlation         FLOAT8,
    vif_score               FLOAT8,
    mutual_information      FLOAT8,

    -- Drift
    psi_score               FLOAT8,
    ks_pvalue               FLOAT8,
    is_drifting             BOOLEAN DEFAULT FALSE,

    -- Leakage
    leakage_suspected       BOOLEAN DEFAULT FALSE,
    ic_same_day             FLOAT8,
    ic_next_day             FLOAT8,

    -- Verdict
    research_grade          TEXT,
    recommendation          TEXT,
    rejection_reasons       JSONB DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_feature_evaluations_name
    ON research_feature_evaluations(feature_name);
CREATE INDEX IF NOT EXISTS idx_feature_evaluations_grade
    ON research_feature_evaluations(research_grade);
CREATE INDEX IF NOT EXISTS idx_feature_evaluations_ic5d
    ON research_feature_evaluations(ic_5d DESC NULLS LAST);
"""

DDL_RESEARCH_VALIDATION_RUNS = """
CREATE TABLE IF NOT EXISTS research_validation_runs (
    run_id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    experiment_id           TEXT REFERENCES research_experiments(experiment_id),
    validation_type         TEXT NOT NULL,  -- walk_forward | monte_carlo | bootstrap | leakage
    ran_at                  TIMESTAMPTZ DEFAULT NOW(),
    parameters              JSONB DEFAULT '{}',
    results                 JSONB DEFAULT '{}',
    passed                  BOOLEAN,
    runtime_seconds         FLOAT8,
    seed                    INT DEFAULT 42
);

CREATE INDEX IF NOT EXISTS idx_validation_runs_experiment
    ON research_validation_runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_validation_runs_type
    ON research_validation_runs(validation_type);
"""

DDL_RESEARCH_REPORTS = """
CREATE TABLE IF NOT EXISTS research_reports (
    report_id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    experiment_id           TEXT REFERENCES research_experiments(experiment_id),
    report_type             TEXT NOT NULL,  -- experiment | weekly | leaderboard | hypothesis_catalog
    generated_at            TIMESTAMPTZ DEFAULT NOW(),
    file_path               TEXT,
    content_hash            TEXT,
    version                 INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_research_reports_experiment
    ON research_reports(experiment_id);
"""

ALL_DDL = [
    ("research_experiments", DDL_RESEARCH_EXPERIMENTS),
    ("research_hypotheses", DDL_RESEARCH_HYPOTHESES),
    ("research_feature_evaluations", DDL_RESEARCH_FEATURE_EVALUATIONS),
    ("research_validation_runs", DDL_RESEARCH_VALIDATION_RUNS),
    ("research_reports", DDL_RESEARCH_REPORTS),
]


async def create_research_tables(pool) -> dict:
    """
    Create all research laboratory PostgreSQL tables.
    Idempotent — safe to run on every startup.

    Args:
        pool: asyncpg connection pool

    Returns:
        dict with table names and creation status
    """
    results = {}
    if pool is None:
        logger.warning("No DB pool — skipping research table creation")
        return {"status": "skipped", "reason": "no_pool"}

    async with pool.acquire() as conn:
        for table_name, ddl in ALL_DDL:
            try:
                await conn.execute(ddl)
                results[table_name] = "ready"
                logger.info(f"[ResearchDB] Table ready: {table_name}")
            except Exception as e:
                results[table_name] = f"error: {e}"
                logger.error(f"[ResearchDB] Failed to create {table_name}: {e}")

    results["status"] = "complete"
    created = sum(1 for v in results.values() if v == "ready")
    logger.info(
        f"[ResearchDB] Schema bootstrap complete: {created}/{len(ALL_DDL)} tables ready"
    )
    return results


async def drop_research_tables(pool, confirm: bool = False) -> dict:
    """
    Drop all research tables. DESTRUCTIVE — requires confirm=True.
    Only for development/reset purposes.
    """
    if not confirm:
        raise ValueError("Pass confirm=True to drop research tables.")

    tables = [t for t, _ in ALL_DDL]
    results = {}
    async with pool.acquire() as conn:
        for table in reversed(tables):  # reverse order for FK constraints
            try:
                await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                results[table] = "dropped"
            except Exception as e:
                results[table] = f"error: {e}"
    return results


async def get_research_db_stats(pool) -> dict:
    """
    Return row counts and status for all research tables.
    """
    if pool is None:
        return {"status": "offline"}

    stats = {}
    tables = [t for t, _ in ALL_DDL]
    async with pool.acquire() as conn:
        for table in tables:
            try:
                row = await conn.fetchrow(f"SELECT COUNT(*) as n FROM {table};")
                stats[table] = {"rows": row["n"], "status": "ok"}
            except Exception as e:
                stats[table] = {"rows": 0, "status": f"error: {e}"}
    return stats


if __name__ == "__main__":
    # Standalone bootstrap script
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    async def _bootstrap():
        from pipeline.config import POSTGRES_CONFIG

        try:
            import asyncpg

            pool = await asyncpg.create_pool(**POSTGRES_CONFIG)
            result = await create_research_tables(pool)
            print(f"Bootstrap result: {result}")
            stats = await get_research_db_stats(pool)
            print(f"Table stats: {stats}")
            await pool.close()
        except ImportError:
            print("asyncpg not installed — install with: pip install asyncpg")
        except Exception as e:
            print(f"Bootstrap failed: {e}")

    asyncio.run(_bootstrap())
