"""
Pipeline configuration — all hyperparameters in one place.
Tuned for Indian equity markets (NSE / Nifty 50).
"""

import os

# ─── Database ─────────────────────────────────────────────────────────

POSTGRES_CONFIG = {
    "host": os.getenv("PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("PG_PORT", 5432)),
    "database": os.getenv("PG_DATABASE", "wealthquant"),
    "user": os.getenv("PG_USER", "wealthquant"),
    "password": os.getenv("PG_PASSWORD", "wealthquant"),
    "min_connections": 5,
    "max_connections": 20,
}

# ─── Stage 2: Hawkes Process ─────────────────────────────────────────

HAWKES_CONFIG = {
    # Event detection thresholds
    "price_jump_sigma": 2.0,  # standard deviations for price jump
    "volume_spike_multiplier": 3.0,  # × rolling median for volume spike
    "oi_change_threshold": 0.05,  # 5% OI change = event
    # Model parameters
    "max_events": 500,  # max events to fit on
    "min_events": 10,  # minimum events for valid fit
    "decay_prior_beta": 0.1,  # prior for decay rate β
    "cascade_threshold": 0.8,  # branching ratio threshold for cascade
    # Prediction
    "forecast_window_seconds": 300,  # 5-min forecast horizon
}

# ─── Stage 3: Kalman Filter ──────────────────────────────────────────

KALMAN_CONFIG = {
    # State: [price, velocity, acceleration, log_volatility]
    "dt": 1.0,  # timestep (normalized to 1 bar)
    # Process noise (Q diagonal)
    "process_noise_price": 0.01,
    "process_noise_velocity": 0.05,
    "process_noise_acceleration": 0.1,
    "process_noise_volatility": 0.02,
    # Observation noise per data source (R)
    "obs_noise": {
        "truedata": 0.001,
        "breeze": 0.005,
        "nse": 0.01,
        "yfinance": 0.05,
        "default": 0.01,
    },
    # Volatility mean reversion
    "volatility_mean_reversion": 0.95,  # ρ < 1 for mean reversion
    "volatility_long_run_mean": 0.02,  # long-run log-volatility
}

# ─── Stage 4: Particle Filter ────────────────────────────────────────

PARTICLE_CONFIG = {
    "n_particles": 1000,
    "resample_threshold": 0.5,  # ESS/N threshold for resampling
    # Dynamics
    "trend_momentum_decay": 0.95,
    "mean_reversion_theta": 0.1,  # O-U speed
    "jump_probability": 0.01,  # P(jump) per bar
    "jump_mean": 0.0,
    "jump_std": 0.02,  # 2% average jump size
    # Observation model
    "obs_df": 5,  # Student-t degrees of freedom (fat tails)
    "obs_scale": 0.01,
}

# ─── Stage 5: Regime Detection ───────────────────────────────────────

REGIME_CONFIG = {
    "n_regimes": 6,
    "regime_names": [
        "TRENDING_BULL",
        "TRENDING_BEAR",
        "MEAN_REVERTING",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "TRANSITION",
    ],
    # HMM training
    "lookback_bars": 504,  # 2 years of daily bars
    "n_hmm_iterations": 100,
    "hmm_covariance_type": "full",
    # BOCPD (Online Changepoint Detection)
    "changepoint_hazard": 1 / 250,  # ~1 change per year
    "bocpd_lookback": 100,  # bars for run-length distribution
    # Feature engineering
    "features": [
        "returns_5d",
        "volatility_20d",
        "volume_ratio",
        "adx",
        "rsi_14",
        "bb_width",
    ],
}

# ─── Stage 6: XGBoost Ensemble ───────────────────────────────────────

ENSEMBLE_CONFIG = {
    "models": {
        "xgboost": {
            "n_estimators": 200,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "objective": "reg:squarederror",
            "tree_method": "hist",
        },
        "random_forest": {
            "n_estimators": 150,
            "max_depth": 8,
            "min_samples_split": 10,
            "min_samples_leaf": 5,
            "max_features": "sqrt",
        },
        "gradient_boosting": {
            "n_estimators": 150,
            "max_depth": 5,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "min_samples_leaf": 10,
        },
    },
    # Feature engineering
    "lookback_bars": 60,
    "forecast_horizons": [1, 3, 5, 10],  # bars ahead
    "quantiles": [0.10, 0.25, 0.50, 0.75, 0.90],
    # Model blending weights (initial, updated by Bayesian Fusion)
    "initial_weights": {
        "xgboost": 0.5,
        "random_forest": 0.3,
        "gradient_boosting": 0.2,
    },
    # Training
    "train_test_split": 0.2,
    "cv_folds": 5,
    "retrain_interval_bars": 100,  # retrain every 100 bars
    "model_dir": "pipeline/models",
}

# ─── Stage 7: Meta-Learning ──────────────────────────────────────────

META_LEARNING_CONFIG = {
    # Regime-conditioned model pool
    "regime_model_blend_alpha_start": 0.3,
    "regime_model_blend_alpha_max": 0.9,
    "regime_model_blend_ramp_bars": 20,  # bars to reach alpha_max
    # Adaptation triggers
    "regime_change_confidence_threshold": 0.7,
    "min_bars_for_adaptation": 5,
    # Ensemble selection
    "max_active_models": 3,
    "model_selection_metric": "sharpe",  # 'accuracy', 'sharpe', 'calmar'
}

# ─── Stage 8: Bayesian Fusion ────────────────────────────────────────

FUSION_CONFIG = {
    # Initial model weights (for the fusion across pipeline stages)
    "initial_weights": {
        "hawkes": 0.10,
        "kalman": 0.15,
        "particle": 0.15,
        "ensemble": 0.40,
        "meta_learning": 0.20,
        "institutional": 0.15,
    },
    # Regime-specific weight overrides
    "regime_weights": {
        "TRENDING_BULL": {
            "hawkes": 0.05,
            "kalman": 0.10,
            "particle": 0.10,
            "ensemble": 0.50,
            "meta_learning": 0.25,
            "institutional": 0.15,
        },
        "TRENDING_BEAR": {
            "hawkes": 0.10,
            "kalman": 0.10,
            "particle": 0.15,
            "ensemble": 0.45,
            "meta_learning": 0.20,
            "institutional": 0.15,
        },
        "MEAN_REVERTING": {
            "hawkes": 0.05,
            "kalman": 0.25,
            "particle": 0.10,
            "ensemble": 0.40,
            "meta_learning": 0.20,
            "institutional": 0.15,
        },
        "HIGH_VOLATILITY": {
            "hawkes": 0.15,
            "kalman": 0.10,
            "particle": 0.25,
            "ensemble": 0.30,
            "meta_learning": 0.20,
            "institutional": 0.15,
        },
        "LOW_VOLATILITY": {
            "hawkes": 0.05,
            "kalman": 0.20,
            "particle": 0.10,
            "ensemble": 0.45,
            "meta_learning": 0.20,
            "institutional": 0.15,
        },
        "TRANSITION": {
            "hawkes": 0.15,
            "kalman": 0.15,
            "particle": 0.20,
            "ensemble": 0.30,
            "meta_learning": 0.20,
            "institutional": 0.15,
        },
    },
    # Weight update
    "weight_learning_rate": 0.01,
    "weight_min": 0.02,  # no model weight drops below 2%
    # Distribution
    "n_bins": 200,  # discretization bins for PDF
    "return_range": (-0.10, 0.10),  # ±10% return range
    # Conflict detection
    "agreement_threshold": 0.6,  # below this = conflict alert
}

# ─── Stage 9: Probability Engine ─────────────────────────────────────

PROBABILITY_CONFIG = {
    # Thresholds for directional classification
    "up_threshold": 0.005,  # 0.5% move = meaningful
    "down_threshold": -0.005,
    # Kelly criterion
    "kelly_cap": 0.25,  # max 25% of capital
    "use_half_kelly": True,
    # Signal thresholds
    "strong_buy_threshold": 0.65,
    "buy_threshold": 0.55,
    "strong_sell_threshold": 0.65,
    "sell_threshold": 0.55,
    # Calibration (Platt scaling)
    "calibration_window": 100,  # last 100 predictions
    "min_calibration_samples": 20,
    # VaR
    "var_confidence": 0.95,
}

# ─── Stage 10: LLM Analyst ───────────────────────────────────────────

LLM_CONFIG = {
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "temperature": 0.3,
    "max_tokens": 3000,
    "timeout_seconds": 30,
    # Fallback if Ollama is unavailable
    "fallback_enabled": True,
    "fallback_provider": None,  # set to 'gemini' or 'openai' if desired
}

# ─── Research & Validation ───────────────────────────────────────────

RESEARCH_CONFIG = {
    # Classification Threshold Mode: 'STATIC' or 'VOLATILITY_ADAPTIVE'
    "target_mode": "VOLATILITY_ADAPTIVE",
    "classification_threshold": 0.005,  # Used if target_mode == 'STATIC'
    "rolling_window": 20,
    "std_multiplier": 1.5,
    "prediction_horizon": 5,
}

# ─── Pipeline-level settings ─────────────────────────────────────────

PIPELINE_CONFIG = {
    "default_interval": "15m",
    "cache_ttl_seconds": 30,  # pipeline result cache TTL
    "max_concurrent_symbols": 10,
    "enable_postgres_logging": True,
    "enable_stage_timing": True,
}

# ─── Download / Training ─────────────────────────────────────────────

DOWNLOAD_CONFIG = {
    "history_years": 2,
    "symbols_nifty50": [
        "RELIANCE",
        "TCS",
        "HDFCBANK",
        "INFY",
        "ICICIBANK",
        "HINDUNILVR",
        "ITC",
        "SBIN",
        "BHARTIARTL",
        "KOTAKBANK",
        "LT",
        "AXISBANK",
        "ASIANPAINT",
        "MARUTI",
        "TITAN",
        "SUNPHARMA",
        "BAJFINANCE",
        "WIPRO",
        "ULTRACEMCO",
        "NESTLEIND",
        "HCLTECH",
        "TATAMOTORS",
        "POWERGRID",
        "NTPC",
        "M&M",
        "TECHM",
        "INDUSINDBK",
        "TATASTEEL",
        "BAJAJFINSV",
        "ONGC",
        "JSWSTEEL",
        "ADANIENT",
        "ADANIPORTS",
        "COALINDIA",
        "GRASIM",
        "CIPLA",
        "DRREDDY",
        "BPCL",
        "DIVISLAB",
        "EICHERMOT",
        "HEROMOTOCO",
        "APOLLOHOSP",
        "SBILIFE",
        "BRITANNIA",
        "TATACONSUM",
        "HINDALCO",
        "BAJAJ-AUTO",
        "HDFCLIFE",
        "UPL",
        "SHRIRAMFIN",
    ],
    "indices": [
        "^NSEI",  # NIFTY 50
        "^NSEBANK",  # BANK NIFTY
    ],
    "timeframes": ["1d", "1h", "15m"],
    "batch_size": 10,  # download N symbols concurrently
}
