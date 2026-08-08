import logging
from typing import Any

logger = logging.getLogger("backend.core.health_monitor")


class HealthMonitor:
    @staticmethod
    def calculate_system_status(metrics: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate Institutional Health Score (0-100) and dashboard status.
        `metrics` contains raw data from accuracy, calibration, drift, db, scheduler, options, etc.
        """
        score = 100
        dashboard = {
            "Prediction Engine": "Green",
            "Calibration": "Green",
            "Market Regime": "Green",
            "Feature Drift": "Green",
            "Options Feed": "Green",
            "Database": "Green",
            "Scheduler": "Green",
            "AI Analyst": "Green",
        }

        # Prediction Accuracy logic
        acc = metrics.get("accuracy", 0.0)
        if acc < 0.4:
            dashboard["Prediction Engine"] = "Red"
            score -= 15
        elif acc < 0.5:
            dashboard["Prediction Engine"] = "Yellow"
            score -= 5

        # Calibration logic
        calibration_status = metrics.get("calibration_status", "Learning")
        if calibration_status == "Learning":
            dashboard["Calibration"] = "Yellow"
            score -= 5
        elif calibration_status == "Unreliable":
            dashboard["Calibration"] = "Red"
            score -= 10

        # Feature Drift logic
        drift_status = metrics.get("drift_status", "Healthy")
        if drift_status == "Critical":
            dashboard["Feature Drift"] = "Red"
            score -= 15
        elif drift_status == "Warning":
            dashboard["Feature Drift"] = "Yellow"
            score -= 5

        # Database Health
        if not metrics.get("db_connected", True):
            dashboard["Database"] = "Red"
            score -= 20

        # Scheduler
        if not metrics.get("scheduler_active", True):
            dashboard["Scheduler"] = "Red"
            score -= 15

        # Options Feed
        options_health = metrics.get("options_health", "ok")
        if options_health != "ok":
            dashboard["Options Feed"] = "Red"
            score -= 10

        return {"institutional_health_score": max(0, score), "system_status": dashboard}
