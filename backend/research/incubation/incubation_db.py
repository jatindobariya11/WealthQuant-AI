"""
WealthQuant V9.2 — Incubation Database Schema
==============================================
Creates isolated PostgreSQL tables for the Alpha Validation & Incubation Platform:
  - alpha_incubation_records : Main lifecycle tracking per incubated alpha
  - alpha_shadow_logs        : Paper trade and shadow mode execution logs
  - alpha_decay_alerts       : Automated decay and concept drift alerts
  - alpha_governance_audit   : Stage transition and sign-off audit trail
"""

import logging

logger = logging.getLogger("incubation.db")

DDL_INCUBATION_RECORDS = """
CREATE TABLE IF NOT EXISTS alpha_incubation_records (
    incubation_id           TEXT PRIMARY KEY,
    alpha_id                TEXT UNIQUE NOT NULL,
    hypothesis_title        TEXT NOT NULL,
    author                  TEXT DEFAULT 'quant_research_team',
    discovery_date          DATE DEFAULT CURRENT_DATE,
    
    -- 10-Stage Lifecycle
    current_stage           TEXT DEFAULT 'DISCOVERED',
    approval_status         TEXT DEFAULT 'PENDING',        -- PENDING | APPROVED | REJECTED | ON_HOLD
    production_status       TEXT DEFAULT 'NOT_DEPLOYED',   -- NOT_DEPLOYED | SHADOW_ACTIVE | PRODUCTION_CANDIDATE | REJECTED
    
    -- Research Metrics Snapshot
    sample_size             INT,
    research_health_score   FLOAT8 DEFAULT 0.0,
    information_coefficient FLOAT8 DEFAULT 0.0,
    sharpe_contribution     FLOAT8 DEFAULT 0.0,
    drawdown_impact         FLOAT8 DEFAULT 0.0,
    regime_stability        FLOAT8 DEFAULT 0.0,
    calibration_score       FLOAT8 DEFAULT 0.0,
    
    -- Validation Checklist (JSON)
    validation_checklist    JSONB DEFAULT '{}',
    failure_modes           JSONB DEFAULT '[]',
    supporting_features    JSONB DEFAULT '[]',
    
    -- Incubation Milestones
    paper_trade_start_date  DATE,
    shadow_mode_start_date  DATE,
    candidate_date          DATE,
    approval_date           DATE,
    
    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incub_stage ON alpha_incubation_records(current_stage);
CREATE INDEX IF NOT EXISTS idx_incub_status ON alpha_incubation_records(approval_status);
"""

DDL_SHADOW_LOGS = """
CREATE TABLE IF NOT EXISTS alpha_shadow_logs (
    log_id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    alpha_id                TEXT REFERENCES alpha_incubation_records(alpha_id),
    timestamp               TIMESTAMPTZ DEFAULT NOW(),
    mode                    TEXT NOT NULL,               -- PAPER_TRADE | SHADOW_MODE
    symbol                  TEXT DEFAULT 'NIFTY',
    
    signal_direction        INT,                         -- +1 (CALL), -1 (PUT), 0 (NEUTRAL)
    signal_strength         FLOAT8,
    simulated_entry_price   FLOAT8,
    simulated_exit_price    FLOAT8,
    realized_pnl            FLOAT8,
    expected_pnl            FLOAT8,
    tracking_error          FLOAT8,
    
    regime_label            TEXT
);

CREATE INDEX IF NOT EXISTS idx_shadow_alpha ON alpha_shadow_logs(alpha_id);
CREATE INDEX IF NOT EXISTS idx_shadow_time ON alpha_shadow_logs(timestamp DESC);
"""

DDL_DECAY_ALERTS = """
CREATE TABLE IF NOT EXISTS alpha_decay_alerts (
    alert_id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    alpha_id                TEXT REFERENCES alpha_incubation_records(alpha_id),
    detected_at             TIMESTAMPTZ DEFAULT NOW(),
    alert_type              TEXT NOT NULL,               -- PERFORMANCE_DECAY | CONCEPT_DRIFT | PSI_DRIFT | CALIBRATION_DRIFT | REGIME_BREAK
    severity                TEXT DEFAULT 'WARNING',      -- WARNING | CRITICAL | TERMINATE
    metrics_snapshot        JSONB DEFAULT '{}',
    description             TEXT,
    action_taken            TEXT DEFAULT 'UNRESOLVED'
);

CREATE INDEX IF NOT EXISTS idx_decay_alpha ON alpha_decay_alerts(alpha_id);
CREATE INDEX IF NOT EXISTS idx_decay_sev ON alpha_decay_alerts(severity);
"""

DDL_GOVERNANCE_AUDIT = """
CREATE TABLE IF NOT EXISTS alpha_governance_audit (
    audit_id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    alpha_id                TEXT REFERENCES alpha_incubation_records(alpha_id),
    transition_timestamp    TIMESTAMPTZ DEFAULT NOW(),
    from_stage              TEXT,
    to_stage                TEXT,
    action_by               TEXT DEFAULT 'quant_director',
    gate_checks_passed      BOOLEAN,
    gate_details            JSONB DEFAULT '{}',
    comments                TEXT
);

CREATE INDEX IF NOT EXISTS idx_gov_alpha ON alpha_governance_audit(alpha_id);
"""

ALL_DDL = [
    ("alpha_incubation_records", DDL_INCUBATION_RECORDS),
    ("alpha_shadow_logs", DDL_SHADOW_LOGS),
    ("alpha_decay_alerts", DDL_DECAY_ALERTS),
    ("alpha_governance_audit", DDL_GOVERNANCE_AUDIT),
]


class IncubationDB:
    def __init__(self, pool):
        self.pool = pool

    async def create_tables(self) -> dict:
        if self.pool is None:
            return {"status": "skipped", "reason": "no_pool"}

        results = {}
        async with self.pool.acquire() as conn:
            for table_name, ddl in ALL_DDL:
                try:
                    await conn.execute(ddl)
                    results[table_name] = "ready"
                except Exception as e:
                    results[table_name] = f"error: {e}"
        return results
