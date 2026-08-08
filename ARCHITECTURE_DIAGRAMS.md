# WealthQuant Architecture Diagrams

## System Architecture
```mermaid
graph TD
    A[React Frontend] -->|REST API| B(FastAPI Backend)
    B --> C[(PostgreSQL)]
    B --> D[Market Data Sources]
```

## Prediction Pipeline
```mermaid
graph LR
    A[Ingest] --> B[HMM] --> C[Ensemble] --> D[Meta Learning] --> E[Bayesian Fusion] --> F[Signal]
```

## Research Pipeline
```mermaid
graph TD
    A[Historical Data] --> B[Research Environment] --> C[Backtest] --> D[Report]
```

## Replay Flow
```mermaid
graph TD
    A[Tick Data] --> B[Replay Engine] --> C[Prediction Pipeline] --> D[Evaluation]
```

## Scheduler Flow
```mermaid
graph TD
    A[APScheduler] --> B[Market Context Task]
    A --> C[Prediction Task]
    A --> D[Options Chain Task]
```

## Database ER Diagram
```mermaid
erDiagram
    STOCK ||--o{ PREDICTION : has
    PREDICTION {
        string symbol
        string signal
        float confidence
    }
```

## API Flow
```mermaid
sequenceDiagram
    Client->>API: GET /api/dashboard
    API->>Cache: Check TTLCache
    Cache-->>API: Miss
    API->>DB: Fetch
    DB-->>API: Return Data
    API->>Cache: Set TTLCache
    API-->>Client: 200 OK
```

## Thread Pool Diagram
```mermaid
graph TD
    A[Main Event Loop] --> B[DB Pool]
    A --> C[NSE Pool]
    A --> D[Playwright Pool]
```
