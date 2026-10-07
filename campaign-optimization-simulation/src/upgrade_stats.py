# Statistical diagnostics used by the Week 4 report.
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats


def _holm(pvals):
    pvals = np.asarray(pvals, float)
    order = np.argsort(pvals)
    adj = np.empty_like(pvals)
    m = len(pvals)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * pvals[idx]
        running = max(running, val)
        adj[idx] = min(running, 1.0)
    return adj


def statistical_tests(results, baseline):
    names = list(results)
    # Global tests across scenario ROAS distributions.
    roas_groups = [results[n]["roas"] for n in names]
    anova = stats.f_oneway(*roas_groups)
    kw = stats.friedmanchisquare(*roas_groups)
    rows = [
        {"test": "One-way ANOVA (ROAS)", "comparison": "All scenarios",
         "statistic": float(anova.statistic), "p_value": float(anova.pvalue),
         "effect_or_note": "Tests equality of scenario mean ROAS; simulation distributions are independent across scenarios only conceptually, so this is descriptive."},
        {"test": "Friedman test (ROAS, paired)", "comparison": "All scenarios",
         "statistic": float(kw.statistic), "p_value": float(kw.pvalue),
         "effect_or_note": "Non-parametric global check that paired scenario ROAS distributions differ."},
    ]
    pvals = []
    pair_rows = []
    b = results[baseline]["net_profit"]
    for n in names:
        if n == baseline:
            continue
        d = results[n]["net_profit"] - b
        tt = stats.ttest_rel(results[n]["net_profit"], b)
        pvals.append(tt.pvalue)
        se = d.std(ddof=1) / np.sqrt(len(d))
        ci_lo, ci_hi = d.mean() - 1.96 * se, d.mean() + 1.96 * se
        sd = d.std(ddof=1)
        dz = d.mean() / sd if sd else np.nan
        pair_rows.append({"test": "Paired t-test (net profit)", "comparison": n,
                          "statistic": float(tt.statistic), "p_value": float(tt.pvalue),
                          "mean_difference": float(d.mean()), "ci95_lo": float(ci_lo),
                          "ci95_hi": float(ci_hi), "cohens_dz": float(dz)})
    adj = _holm(pvals)
    for row, a in zip(pair_rows, adj):
        row["holm_adjusted_p"] = float(a)
        row["significant_0_05_after_holm"] = bool(a < 0.05)
        rows.append(row)
    return pd.DataFrame(rows)
