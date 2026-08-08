# Experiment Registry

## 1. Experiment Record Schema
| Field | Type | Description |
|-------|------|-------------|
| `exp_id` | String | Unique identifier (e.g., EXP-2026-001) |
| `hypothesis_id` | String | Foreign key to hypothesis catalog |
| `author` | String | Researcher name |
| `status` | Enum | DRAFT, RUNNING, COMPLETED, ACCEPTED, REJECTED |
| `start_date` | Date | Experiment start date |
| `end_date` | Date | Experiment completion date |
| `universe` | String | Asset universe (e.g., NIFTY50_OPTIONS) |
| `horizon` | Int | Target horizon in days |
| `ic_mean` | Float | Out-of-sample Mean IC |
| `ic_ir` | Float | Information Ratio of IC |
| `p_value` | Float | Permutation p-value |
| `bootstrap_lower` | Float | 95% CI Lower Bound |
| `health_score` | Float | Computed 0-100 score |
| `is_leaky` | Boolean | Leakage detection flag |

*(Includes 11 more operational and metadata fields)*

## 2. Experiment Status Lifecycle
`DRAFT` -> `RUNNING` -> `COMPLETED` -> `VALIDATING` -> (`ACCEPTED` | `REJECTED`)

## 3. Experiment ID Naming Convention
`EXP-[YYYY]-[3-digit Sequence]-[Category Code]`
Example: `EXP-2026-042-OF` (42nd experiment of 2026, Options Flow category)

## 4. Database Schema
```sql
CREATE TABLE experiments (
    exp_id VARCHAR(50) PRIMARY KEY,
    hypothesis_id VARCHAR(50),
    author VARCHAR(100),
    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metrics JSONB,
    health_score DECIMAL(5,2)
);
```

## 5. API Reference
- `GET /api/v1/registry/experiments`: List all
- `POST /api/v1/registry/experiments`: Create new
- `GET /api/v1/registry/experiments/{id}`: Get details
- `PUT /api/v1/registry/experiments/{id}/status`: Update status

## 6. Query Examples
```sql
-- Find accepted momentum experiments
SELECT exp_id, health_score FROM experiments 
WHERE status = 'ACCEPTED' AND exp_id LIKE '%-MO' 
ORDER BY health_score DESC;
```

## 7. Retention Policy
All experiment metadata and logs are retained infinitely. Artifacts (large backtest result files) are purged after 2 years if REJECTED.

## 8. Backup and Reproducibility
Every experiment commits the exact `git` hash of the research repository at the time of execution to ensure 100% reproducibility.

## 9. Sample Experiment Records

### Example 1: Accepted
- **ID**: EXP-2026-001-DP
- **Hypothesis**: GEX predicts intraday volatility.
- **Status**: ACCEPTED
- **IC**: 0.08
- **Health**: 94/100

### Example 2: Rejected
- **ID**: EXP-2026-002-TR
- **Hypothesis**: MACD crossover predicts 1-day return.
- **Status**: REJECTED
- **IC**: 0.015
- **Health**: 45/100 (Failed IC threshold, failed p-value)

### Example 3: In Progress
- **ID**: EXP-2026-003-OF
- **Hypothesis**: Block trade imbalance predicts weekly return.
- **Status**: RUNNING
- **IC**: null
