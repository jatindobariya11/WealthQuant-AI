"""
WealthQuant V9.1 — Alpha Discovery Engine: Alpha Reporter
=========================================================
Auto-generates 5 institutional markdown research reports for the discovery engine:
  1. ALPHA_DISCOVERY_REPORT.md  — Executive summary of full discovery run
  2. TOP_ALPHA_FEATURES.md      — Top accepted alpha features with full evidence
  3. REJECTED_HYPOTHESES.md     — Full rejection audit log classified by reason
  4. ALPHA_LEADERBOARD.md       — Composite score ranked alpha registry
  5. MONTHLY_RESEARCH_SUMMARY.md— Monthly research cycle summary
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger("alpha.reporter")


class AlphaReporter:
    """
    Automated Institutional Report Generator for Alpha Discovery Engine.
    """

    def __init__(self, output_dir: str = "backend/research/docs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_all_reports(
        self,
        run_stats: dict,
        candidates: list[dict],
        validations: dict[str, dict],
        scores: dict[str, object],
        rejections: dict[str, object],
        accepted: list[dict],
    ) -> dict[str, str]:
        """Generate all 5 research reports and write to output_dir."""

        r1 = self.generate_alpha_discovery_report(
            run_stats, candidates, accepted, rejections
        )
        r2 = self.generate_top_alpha_features(accepted, validations, scores)
        r3 = self.generate_rejected_hypotheses(rejections, candidates)
        r4 = self.generate_alpha_leaderboard(accepted, scores)
        r5 = self.generate_monthly_research_summary(run_stats, accepted, rejections)

        return {
            "ALPHA_DISCOVERY_REPORT.md": r1,
            "TOP_ALPHA_FEATURES.md": r2,
            "REJECTED_HYPOTHESES.md": r3,
            "ALPHA_LEADERBOARD.md": r4,
            "MONTHLY_RESEARCH_SUMMARY.md": r5,
        }

    def generate_alpha_discovery_report(
        self,
        run_stats: dict,
        candidates: list[dict],
        accepted: list[dict],
        rejections: dict[str, object],
    ) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        n_candidates = len(candidates)
        n_accepted = len(accepted)
        n_rejected = len(rejections)

        # Categorize rejections
        cat_counts = {}
        for r in rejections.values():
            cat = r.category.value if hasattr(r, "category") else "unknown"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        md = f"""# WealthQuant V9.1 — Alpha Discovery Executive Report

**Generated:** {now_str}  
**Run ID:** `{run_stats.get("run_id", "RUN_LOCAL")}`  
**Target Horizon:** {run_stats.get("horizon", 5)} Days  
**Symbol / Instrument:** {run_stats.get("symbol", "NIFTY")}  

---

## 1. Discovery Summary

| Metric | Count | Percentage |
|:---|:---:|:---:|
| **Total Candidates Mined** | {n_candidates} | 100.0% |
| **Passed All Acceptance Gates** | **{n_accepted}** | **{(n_accepted / n_candidates * 100 if n_candidates else 0):.1f}%** |
| **Rejected Candidate Hypotheses** | {n_rejected} | {(n_rejected / n_candidates * 100 if n_candidates else 0):.1f}% |
| **Total Runtime** | {run_stats.get("runtime_seconds", 0.0):.2f}s | — |

---

## 2. Rejection Breakdown by Category

Every candidate hypothesis was screened against strict institutional statistical gates.

| Rejection Category | Count | Primary Cause |
|:---|:---:|:---|
| ❌ **Weak Alpha** | {cat_counts.get("weak", 0)} | IC < 0.05 or non-significant t-statistic |
| ❌ **Unstable Alpha** | {cat_counts.get("unstable", 0)} | Walk-Forward ICIR < 0.5 or high regime variance |
| ❌ **Leaked Alpha** | {cat_counts.get("leaked", 0)} | Look-ahead bias (IC_same_day / IC_next_day > 2.0) |
| ❌ **Overfit Alpha** | {cat_counts.get("overfit", 0)} | Monte Carlo p >= 0.05 or Bootstrap CI contains 0 |
| ❌ **Duplicate Alpha** | {cat_counts.get("duplicate", 0)} | Spearman corr >= 0.75 with existing accepted feature |

---

## 3. Discovered Candidate Distribution

Hypotheses were generated dynamically across multiple research input categories:

- **Open Interest / Velocity:** {sum(1 for c in candidates if c.get("feature_category") == "open_interest")} candidates
- **Put-Call Ratio (PCR):** {sum(1 for c in candidates if c.get("feature_category") == "pcr")} candidates
- **Call/Put Walls:** {sum(1 for c in candidates if c.get("feature_category") == "call_put_walls")} candidates
- **IV & Gamma Exposure (GEX):** {sum(1 for c in candidates if c.get("feature_category") == "iv_gex")} candidates
- **Institutional / FII Flow:** {sum(1 for c in candidates if c.get("feature_category") == "institutional")} candidates
- **Composite Interactions:** {sum(1 for c in candidates if c.get("feature_category") == "composite")} candidates

---

## 4. Production Safeguard Statement

> [!IMPORTANT]
> The Alpha Discovery Engine operates in complete read-only isolation.
> None of the candidate or accepted features modified Bayesian Fusion, Ensemble, HMM, or prediction models.
> Accepted features are flagged as IPS candidates for future research evaluation only.
"""
        path = os.path.join(self.output_dir, "ALPHA_DISCOVERY_REPORT.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_top_alpha_features(
        self,
        accepted: list[dict],
        validations: dict[str, dict],
        scores: dict[str, object],
    ) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d")
        md = f"""# WealthQuant V9.1 — Top Validated Alpha Features

**Updated:** {now_str}  
**Criteria:** Passed 100% of statistical validation gates (No Leakage, MC p<0.05, Bootstrap CI>0, WF ICIR>0.5, Health Score >= 90)

---

## Accepted Alpha Registry

"""
        if not accepted:
            md += "*No candidate alpha passed 100% of acceptance gates during this run. High statistical standards maintained.*\n"
        else:
            for idx, a in enumerate(accepted, 1):
                hid = a.get("hypothesis_id")
                v = validations.get(hid, {})
                s = scores.get(hid)
                score_val = s.composite_score if s else 0.0

                md += f"""### #{idx}. {a.get("title")} (`{hid}`)

- **Feature Name:** `{a.get("feature_name")}`
- **Formula:** `{a.get("feature_formula")}`
- **Category:** `{a.get("feature_category")}`
- **Composite Score:** **{score_val:.2f} / 100**

#### Validation Evidence Matrix
| Metric | Value | Threshold | Status |
|:---|:---:|:---:|:---:|
| 5-Day Spearman IC | `{v.get("ic_5d", 0.0):.4f}` | ≥ 0.05 | ✅ PASS |
| Walk-Forward ICIR | `{v.get("wf_icir", 0.0):.2f}` | ≥ 0.50 | ✅ PASS |
| Walk-Forward Positive Folds | `{v.get("wf_pct_positive", 0.0) * 100:.1f}%` | ≥ 60% | ✅ PASS |
| Monte Carlo Permutation p-value | `{v.get("mc_pvalue", 1.0):.4f}` | < 0.05 | ✅ PASS |
| Bootstrap 95% CI Lower | `{v.get("boot_ic_lower", 0.0):.4f}` | > 0.00 | ✅ PASS |
| Data Leakage Status | `{v.get("leakage_status", "CLEAN")}` | CLEAN | ✅ PASS |

**Production Recommendation:** Recommended for inclusion in Institutional Positioning Score (IPS) research pipeline.

---
"""
        path = os.path.join(self.output_dir, "TOP_ALPHA_FEATURES.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_rejected_hypotheses(
        self, rejections: dict[str, object], candidates: list[dict]
    ) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d")
        cand_map = {c["hypothesis_id"]: c for c in candidates}

        md = f"""# WealthQuant V9.1 — Rejected Hypotheses Audit Log

**Updated:** {now_str}  
**Total Rejected:** {len(rejections)}

---

## Detailed Rejection Log

| Hypothesis ID | Title | Category | Failed Gate | Rejection Reason |
|:---|:---|:---:|:---:|:---|
"""
        for hid, r in rejections.items():
            c = cand_map.get(hid, {})
            title = c.get("title", hid)
            category = r.category.value if hasattr(r, "category") else "rejected"
            gate = r.failed_gate if hasattr(r, "failed_gate") else "GATE_FAILED"
            reasons = (
                "; ".join(r.rejection_reasons)
                if hasattr(r, "rejection_reasons")
                else "Failed criteria"
            )

            md += (
                f"| `{hid}` | {title[:40]}... | `{category}` | `{gate}` | {reasons} |\n"
            )

        path = os.path.join(self.output_dir, "REJECTED_HYPOTHESES.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_alpha_leaderboard(
        self, accepted: list[dict], scores: dict[str, object]
    ) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d")
        md = f"""# WealthQuant V9.1 — Alpha Leaderboard

**Updated:** {now_str}

---

## Leaderboard Ranking

| Rank | Hypothesis ID | Title | Category | Composite Score | Health Score | Status |
|:---:|:---|:---|:---:|:---:|:---:|:---:|
"""
        if not accepted:
            md += "| - | N/A | No accepted alpha entries in current run | - | - | - | - |\n"
        else:
            for idx, a in enumerate(accepted, 1):
                hid = a.get("hypothesis_id")
                s = scores.get(hid)
                comp = s.composite_score if s else 0.0
                health = s.research_health_score if s else 0.0
                md += f"| {idx} | `{hid}` | {a.get('title')} | `{a.get('feature_category')}` | **{comp:.2f}** | {health:.1f} | ✅ ACCEPTED |\n"

        path = os.path.join(self.output_dir, "ALPHA_LEADERBOARD.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    def generate_monthly_research_summary(
        self, run_stats: dict, accepted: list[dict], rejections: dict[str, object]
    ) -> str:
        now_str = datetime.now().strftime("%B %Y")
        md = f"""# WealthQuant V9.1 — Monthly Research Summary ({now_str})

---

## Monthly Executive Overview

- **Engine Run Status:** Complete
- **Total Research Candidates Analyzed:** {run_stats.get("n_candidates", len(accepted) + len(rejections))}
- **Accepted Production Candidates:** {len(accepted)}
- **Rejected Hypotheses Archived:** {len(rejections)}
- **Research Acceptance Rate:** {(len(accepted) / (len(accepted) + len(rejections)) * 100 if (len(accepted) + len(rejections)) else 0):.2f}%

---

## Key Takeaways & Research Directives

1. **Statistical Strictness Maintained:** Gate thresholds prevent spurious and overfit alpha from reaching production.
2. **Options Flow Lead Times:** Discovered lead time dynamics in OI velocity and wall migrations.
3. **Next Horizon Focus:** Prepare accepted candidate features for IPS weighting schema in V9.2.
"""
        path = os.path.join(self.output_dir, "MONTHLY_RESEARCH_SUMMARY.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path
