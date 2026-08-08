# Research Dashboard User Guide

## 1. Overview
The Research Dashboard provides a UI for tracking, launching, and analyzing quant experiments. It visualizes IC, walk-forward results, and health scores.
**Access**: `http://localhost:8000/api/research/*`

## 2. API Reference
- `GET /api/research/experiments`: Fetch all logged experiments.
- `GET /api/research/experiments/{id}`: Fetch detailed metrics and charts for an experiment.
- `POST /api/research/experiments`: Register a new experiment.
- `POST /api/research/experiments/{id}/run`: Trigger the research pipeline asynchronously.
- `GET /api/research/leaderboard`: View top-performing features ranked by Health Score.
- `GET /api/research/hypotheses`: Browse the hypothesis catalog.
- `GET /api/research/health`: Get system health and database status.
- `GET /api/research/validate`: Run the pre-flight statistical validation checks on a payload.

## 3. Creating an Experiment
1. Navigate to the "New Experiment" tab.
2. Select a Hypothesis from the catalog or define a custom one.
3. Upload or link the feature generation code.
4. Set hyper-parameters (horizon, data universe).
5. Click "Initialize Pipeline".

## 4. Reading Experiment Reports
Reports are generated automatically. Key sections:
- **Tearsheet**: Top-level metrics (IC, ICIR, p-value).
- **Cumulative Return**: The theoretical cumulative return of a long/short portfolio based on the feature.
- **Drawdown Plot**: Visualizing historical failure periods.

## 5. Interpreting Health Scores
- **90-100**: Production-ready. High IC, zero leakage, robust across regimes.
- **70-89**: Promising. May need parameter tuning or combination with other features.
- **<70**: Rejected. Fails critical statistical thresholds.

## 6. Leaderboard Interpretation
The leaderboard ranks features globally. Researchers should look for low-correlation features to add to the top of the leaderboard to build diversified ensembles.

## 7. Feature Evaluation Workflow
Select a feature from the leaderboard -> Run Correlation Matrix against existing production features -> Run Ablation Study -> Propose for IPS integration.

## 8. Integration with Feature Store
Accepted features are automatically registered in the central Feature Store, tagged with their semantic version and available for the Production Trading Engine to consume.
