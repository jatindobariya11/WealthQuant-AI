"""
WealthQuant V9.2 — Incubation Report Generator
===============================================
Auto-generates 5 institutional governance reports for the Alpha Validation & Incubation Platform:
  1. ALPHA_INCUBATION_REPORT.md      — Complete incubation status dashboard
  2. ALPHA_LIFECYCLE.md              — 10-stage lifecycle specification & tracking matrix
  3. ALPHA_APPROVAL_GUIDE.md         — Institutional gate sign-off guide
  4. ALPHA_MONITORING_REPORT.md      — Decay, PSI drift, and shadow mode performance report
  5. PRODUCTION_ALPHA_CANDIDATES.md  — Final sign-off candidate pool ready for IPS consideration
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger("incubation.reporter")


class IncubationReporter:
    """
    Automated Governance & Incubation Report Generator.
    """

    def __init__(self, output_dir: str = "backend/research/docs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_all_reports(
        self,
        incubated_alphas: list[dict],
        shadow_reports: dict[str, object],
        decay_alerts: list[object],
    ) -> dict[str, str]:
        """Generate all 5 incubation governance documents."""

        r1 = self.generate_incubation_report(incubated_alphas)
        r2 = self.generate_lifecycle_guide(incubated_alphas)
        r3 = self.generate_approval_guide()
        r4 = self.generate_monitoring_report(shadow_reports, decay_alerts)
        r5 = self.generate_production_candidates(incubated_alphas, shadow_reports)

        return {
            "ALPHA_INCUBATION_REPORT.md": r1,
            "ALPHA_LIFECYCLE.md": r2,
            "ALPHA_APPROVAL_GUIDE.md": r3,
            "ALPHA_MONITORING_REPORT.md": r4,
            "PRODUCTION_ALPHA_CANDIDATES.md": r5,
        }

    def generate_incubation_report(self, alphas: list[dict]) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        n_total = len(alphas)

        stage_counts = {}
        for a in alphas:
            st = a.get("current_stage", "DISCOVERED")
            stage_counts[st] = stage_counts.get(st, 0) + 1

        md = f"""# WealthQuant V9.2 — Alpha Incubation Executive Report

**Generated:** {now_str}  
**Platform Version:** 9.2.0  
**Total Incubated Alpha:** {n_total}

---

## 1. Lifecycle Stage Distribution

| Stage | Description | Alpha Count |
|:---|:---|:---:|
| **1. DISCOVERED** | Newly discovered candidates | {stage_counts.get("DISCOVERED", 0)} |
| **2. UNDER_REVIEW** | Hypothesis & data audit | {stage_counts.get("UNDER_REVIEW", 0)} |
| **3. BACKTESTED** | Historical simulation completed | {stage_counts.get("BACKTESTED", 0)} |
| **4. WALK_FORWARD_VERIFIED** | Purged fold ICIR ≥ 0.5 | {stage_counts.get("WALK_FORWARD_VERIFIED", 0)} |
| **5. MONTE_CARLO_VERIFIED** | Block permutation p < 0.05 | {stage_counts.get("MONTE_CARLO_VERIFIED", 0)} |
| **6. BOOTSTRAP_VERIFIED** | 95% CI excludes zero | {stage_counts.get("BOOTSTRAP_VERIFIED", 0)} |
| **7. PAPER_TRADE** | Simulated forward execution (≥30d) | {stage_counts.get("PAPER_TRADE", 0)} |
| **8. SHADOW_MODE** | Live parallel execution (≥60d) | {stage_counts.get("SHADOW_MODE", 0)} |
| **9. PRODUCTION_CANDIDATE** | Governance review pool | {stage_counts.get("PRODUCTION_CANDIDATE", 0)} |
| **10. APPROVED** | IPS sign-off complete | {stage_counts.get("APPROVED", 0)} |

---

## 2. Active Incubation Pipeline

| Alpha ID | Title | Current Stage | Health Score | Sharpe Δ | Status |
|:---|:---|:---:|:---:|:---:|:---:|
"""
        if not alphas:
            md += "| - | No alpha currently in incubation pipeline | - | - | - | - |\n"
        else:
            for a in alphas:
                md += f"| `{a.get('alpha_id')}` | {a.get('hypothesis_title')} | `{a.get('current_stage')}` | {a.get('research_health_score', 0.0):.1f} | +{a.get('sharpe_contribution', 0.0):.2f} | `{a.get('approval_status')}` |\n"

        path = os.path.join(self.output_dir, "ALPHA_INCUBATION_REPORT.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_lifecycle_guide(self, alphas: list[dict]) -> str:
        md = """# WealthQuant V9.2 — 10-Stage Alpha Lifecycle Specification

Every quantitative feature must prove itself across all 10 stages over time before it can influence production trading.

```
1. DISCOVERED ──► 2. UNDER_REVIEW ──► 3. BACKTESTED ──► 4. WALK_FORWARD ──► 5. MONTE_CARLO
  ──► 6. BOOTSTRAP ──► 7. PAPER_TRADE (30d) ──► 8. SHADOW_MODE (60d) ──► 9. CANDIDATE ──► 10. APPROVED / REJECTED
```

---

## Stage Transition Requirements

1. **DISCOVERED → UNDER_REVIEW:** Minimum 30 observations, hypothesis registration complete.
2. **UNDER_REVIEW → BACKTESTED:** Baseline IC ≥ 0.05 across full historical sample.
3. **BACKTESTED → WALK_FORWARD_VERIFIED:** Purged fold ICIR ≥ 0.50, positive fold ratio ≥ 60%.
4. **WALK_FORWARD → MONTE_CARLO_VERIFIED:** Block permutation p-value < 0.05 (n=1000, block=5).
5. **MONTE_CARLO → BOOTSTRAP_VERIFIED:** Circular block bootstrap 95% CI excludes zero.
6. **BOOTSTRAP → PAPER_TRADE:** Research Health Score ≥ 90/100, Leakage confirmed CLEAN.
7. **PAPER_TRADE → SHADOW_MODE:** 30 consecutive days of simulated execution without decay.
8. **SHADOW_MODE → PRODUCTION_CANDIDATE:** 60 consecutive days of live shadow execution, tracking error ≤ 15%.
9. **PRODUCTION_CANDIDATE → APPROVED:** Final Director sign-off, improves Sharpe OR reduces drawdown.
"""
        path = os.path.join(self.output_dir, "ALPHA_LIFECYCLE.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_approval_guide(self) -> str:
        md = """# WealthQuant V9.2 — Institutional Alpha Approval Guide

## Mandatory Sign-off Criteria (All Must Pass)

1. **Zero Data Leakage:** `leakage_status == CLEAN` and IC_same_day / IC_next_day ≤ 2.0.
2. **Statistical Significance:** Monte Carlo p < 0.05, Bootstrap 95% CI lower bound > 0.
3. **Walk-Forward Stability:** ICIR ≥ 0.50, positive fold percentage ≥ 60%.
4. **Paper Trading Verification:** Minimum 30 days simulated execution without performance drop.
5. **Shadow Mode Verification:** Minimum 60 days live parallel execution with tracking error ≤ 15%.
6. **Performance Impact:** Demonstrated improvement in overall portfolio Sharpe OR reduction in drawdown.
7. **Research Health Score:** Score ≥ 90 / 100 on composite scale.
8. **Non-Redundancy:** Spearman correlation < 0.75 with existing production features.

---

> [!CAUTION]
> No single individual may bypass shadow mode or paper trading requirements.
> Automatic rejection is enforced upon any concept drift (PSI ≥ 0.25).
"""
        path = os.path.join(self.output_dir, "ALPHA_APPROVAL_GUIDE.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_monitoring_report(
        self, shadow_reports: dict[str, object], decay_alerts: list[object]
    ) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d")
        md = f"""# WealthQuant V9.2 — Alpha Monitoring & Decay Audit

**Audit Date:** {now_str}  
**Active Decay Alerts:** {len(decay_alerts)}

---

## 1. Automated Decay & Concept Drift Alerts

| Alpha ID | Alert Type | Severity | Metric Value | Threshold | Description |
|:---|:---|:---:|:---:|:---:|:---|
"""
        if not decay_alerts:
            md += "| - | NONE | INFO | - | - | All incubated alpha operating within normal parameters. No concept drift detected. |\n"
        else:
            for alt in decay_alerts:
                md += f"| `{alt.alpha_id}` | `{alt.alert_type}` | **{alt.severity}** | `{alt.current_value}` | `{alt.threshold_value}` | {alt.description} |\n"

        md += """
---

## 2. Shadow Mode Tracking Error Performance

| Alpha ID | Mode | Signals | Simulated Sharpe | Realized Sharpe | Tracking Error | Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
"""
        if not shadow_reports:
            md += "| - | SHADOW_MODE | 0 | - | - | - | Pending active shadow logs |\n"
        else:
            for aid, rep in shadow_reports.items():
                st = "✅ MATCHES" if rep.matches_expectations else "⚠️ DEGRADED"
                md += f"| `{aid}` | `{rep.mode}` | {rep.n_signals} | {rep.simulated_sharpe:.2f} | {rep.realized_sharpe:.2f} | {rep.tracking_error:.4f} | {st} |\n"

        path = os.path.join(self.output_dir, "ALPHA_MONITORING_REPORT.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_production_candidates(
        self, alphas: list[dict], shadow_reports: dict[str, object]
    ) -> str:
        candidates = [
            a
            for a in alphas
            if a.get("current_stage") in ["PRODUCTION_CANDIDATE", "APPROVED"]
        ]
        now_str = datetime.now().strftime("%Y-%m-%d")

        md = f"""# WealthQuant V9.2 — Production Alpha Candidates Pool

**Updated:** {now_str}  
**Candidates Pool Size:** {len(candidates)}

---

## Qualified Production Candidates

"""
        if not candidates:
            md += "*No alpha currently meets 100% of Production Candidate requirements (pending paper trade & shadow mode completion).*\n"
        else:
            for c in candidates:
                aid = c.get("alpha_id")
                s_rep = shadow_reports.get(aid)
                t_err = f"{s_rep.tracking_error:.4f}" if s_rep else "N/A"

                md += f"""### Candidate: {c.get("hypothesis_title")} (`{aid}`)

- **Author / Source:** `{c.get("author")}`
- **Incubation Stage:** `{c.get("current_stage")}`
- **Research Health Score:** **{c.get("research_health_score", 0.0):.1f} / 100**
- **5-Day IC:** `{c.get("information_coefficient", 0.0):.4f}`
- **Sharpe Contribution:** `+{c.get("sharpe_contribution", 0.0):.2f}`
- **Shadow Mode Tracking Error:** `{t_err}`

**IPS Integration Status:** Ready for IPS (Institutional Positioning Score) weighting evaluation.

---
"""
        path = os.path.join(self.output_dir, "PRODUCTION_ALPHA_CANDIDATES.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path
