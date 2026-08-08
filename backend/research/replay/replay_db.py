"""
WealthQuant V10.0 — Replay Database Schema
===========================================
Creates isolated PostgreSQL tables for the Deterministic Market Replay Engine:
  - replay_sessions      : Metadata for historical replay runs
  - replay_candle_step   : Candle-by-candle step record of predictions, confidence, SHAP, regime & features
"""

import logging

logger = logging.getLogger("replay.db")

DDL_REPLAY_SESSIONS = """
CREATE TABLE IF NOT EXISTS replay_sessions (
    session_id              TEXT PRIMARY KEY,
    symbol                  TEXT NOT NULL DEFAULT 'NIFTY',
    timeframe               TEXT NOT NULL DEFAULT '5m',
    start_timestamp         TIMESTAMPTZ NOT NULL,
    end_timestamp           TIMESTAMPTZ NOT NULL,
    
    total_candles           INT DEFAULT 0,
    processed_candles       INT DEFAULT 0,
    runtime_seconds         FLOAT8 DEFAULT 0.0,
    is_deterministic        BOOLEAN DEFAULT TRUE,
    
    status                  TEXT DEFAULT 'running',      -- running | complete | failed
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replay_symbol ON replay_sessions(symbol);
CREATE INDEX IF NOT EXISTS idx_replay_status ON replay_sessions(status);
"""

DDL_REPLAY_CANDLE_STEP = """
CREATE TABLE IF NOT EXISTS replay_candle_step (
    step_id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    session_id              TEXT REFERENCES replay_sessions(session_id),
    timestamp               TIMESTAMPTZ NOT NULL,
    candle_index            INT NOT NULL,
    
    -- OHLCV Snapshot
    open_price              FLOAT8,
    high_price              FLOAT8,
    low_price               FLOAT8,
    close_price             FLOAT8,
    volume                  FLOAT8,
    
    -- Pipeline Outputs Recorded Step-by-Step
    prediction              TEXT,                        -- CALL | PUT | NEUTRAL
    probability_call        FLOAT8,
    probability_put         FLOAT8,
    confidence_score        FLOAT8,
    regime_label            TEXT,
    
    -- Options & Feature State Snapshot
    pcr_val                 FLOAT8,
    call_wall               FLOAT8,
    put_wall                FLOAT8,
    atm_iv                  FLOAT8,
    gex_val                 FLOAT8,
    
    -- Explainability & Metrics (JSON)
    shap_top_features       JSONB DEFAULT '{}',
    feature_values_snapshot JSONB DEFAULT '{}',
    execution_decision      TEXT,                        -- LONG_ENTRY | SHORT_ENTRY | NO_TRADE | EXIT
    
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_step_session ON replay_candle_step(session_id);
CREATE INDEX IF NOT EXISTS idx_step_time ON replay_candle_step(timestamp ASC);
"""

ALL_DDL = [
    ("replay_sessions", DDL_REPLAY_SESSIONS),
    ("replay_candle_step", DDL_REPLAY_CANDLE_STEP),
]


class ReplayDB:
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
