"""
Core simulation model for marketing campaign optimisation.

Model summary (per channel c, segment s, spend x[c,s]):
    impressions = imp_ref * (x / x_ref) ** alpha_c          (diminishing returns)
    imp_ref     = x_ref / (CPM_c * cpm_mult_s) * 1000
    clicks      = impressions * CTR_c * affinity[c,s]
    conversions = clicks * CVR_c * cvr_mult_s * (1 + halo if c == Search)
    revenue     = conversions * AOV * aov_mult_s
Uncertainty: CPM, CTR, CVR of each channel and overall market demand are
log-normal random shocks (mean 1). Common random numbers are used across
scenarios so scenario differences are paired and low-noise.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# ----------------------------------------------------------------------------
# Global business assumptions (documented in the report, Section 3)
# ----------------------------------------------------------------------------
TOTAL_BUDGET = 100_000.0      # USD, 90-day campaign
AOV = 130.0                   # average order value, USD
GROSS_MARGIN = 0.55           # share of revenue kept after COGS
HALO_MAX = 0.20               # max uplift of search conversions from brand awareness
HALO_SATURATION = 0.30        # awareness (display+video) budget share at which halo saturates
SIGMA = dict(cpm=0.10, ctr=0.12, cvr=0.15, market=0.05)   # log-normal std-devs
N_SIMS = 5_000
SEED = 42


@dataclass(frozen=True)
class Params:
    channels: tuple
    segments: tuple
    cpm: np.ndarray
    ctr: np.ndarray
    cvr: np.ndarray
    alpha: np.ndarray
    cpm_mult: np.ndarray
    cvr_mult: np.ndarray
    aov_mult: np.ndarray
    affinity: np.ndarray
    aov: float = AOV
    margin: float = GROSS_MARGIN
    halo_max: float = HALO_MAX
    halo_sat: float = HALO_SATURATION
    ref_budget: float = TOTAL_BUDGET      # budget at which x_ref (even split) is defined
    fixed_cost: float = 0.0               # non-media cost (e.g. CRO tooling)
    sigma: tuple = tuple(SIGMA.items())

    @property
    def n_c(self):
        return len(self.channels)

    @property
    def n_s(self):
        return len(self.segments)


def load_params() -> Params:
    ch = pd.read_csv(DATA / "channel_benchmarks.csv")
    sg = pd.read_csv(DATA / "segment_multipliers.csv")
    af = pd.read_csv(DATA / "channel_segment_affinity.csv").set_index("channel")
    af = af.loc[ch["channel"], sg["segment"]]
    return Params(
        channels=tuple(ch["channel"]),
        segments=tuple(sg["segment"]),
        cpm=ch["cpm_usd"].to_numpy(float),
        ctr=ch["ctr"].to_numpy(float),
        cvr=ch["cvr"].to_numpy(float),
        alpha=ch["alpha"].to_numpy(float),
        cpm_mult=sg["cpm_mult"].to_numpy(float),
        cvr_mult=sg["cvr_mult"].to_numpy(float),
        aov_mult=sg["aov_mult"].to_numpy(float),
        affinity=af.to_numpy(float),
    )


# ----------------------------------------------------------------------------
# Randomness
# ----------------------------------------------------------------------------
def draw_shocks(p: Params, n: int = N_SIMS, seed: int = SEED) -> dict:
    """Mean-one log-normal shocks. Same seed => same draws (common random numbers)."""
    rng = np.random.default_rng(seed)
    sig = dict(p.sigma)

    def ln(s, size):
        return np.exp(s * rng.standard_normal(size) - 0.5 * s * s)

    return dict(
        cpm=ln(sig["cpm"], (n, p.n_c)),
        ctr=ln(sig["ctr"], (n, p.n_c)),
        cvr=ln(sig["cvr"], (n, p.n_c)),
        market=ln(sig["market"], n),
    )


def no_shocks(p: Params) -> dict:
    return dict(cpm=np.ones((1, p.n_c)), ctr=np.ones((1, p.n_c)),
                cvr=np.ones((1, p.n_c)), market=np.ones(1))


# ----------------------------------------------------------------------------
# Allocation helpers
# ----------------------------------------------------------------------------
def make_alloc(p: Params, budget: float, channel_w=None, segment_w=None) -> np.ndarray:
    """Build a (channel x segment) spend matrix from channel and segment weights."""
    cw = np.full(p.n_c, 1 / p.n_c) if channel_w is None else np.asarray(channel_w, float)
    sw = np.full(p.n_s, 1 / p.n_s) if segment_w is None else np.asarray(segment_w, float)
    cw, sw = cw / cw.sum(), sw / sw.sum()
    return budget * np.outer(cw, sw)


# ----------------------------------------------------------------------------
# Core evaluation
# ----------------------------------------------------------------------------
def evaluate(alloc: np.ndarray, p: Params, shocks: dict | None = None) -> dict:
    """Vectorised evaluation of one allocation over N simulated worlds."""
    shocks = no_shocks(p) if shocks is None else shocks
    alloc = np.maximum(np.asarray(alloc, float), 0.0)
    x_ref = p.ref_budget / (p.n_c * p.n_s)

    cpm = p.cpm[None, :, None] * shocks["cpm"][:, :, None] * p.cpm_mult[None, None, :]
    imp_ref = x_ref / cpm * 1000.0
    imp = imp_ref * (alloc / x_ref)[None] ** p.alpha[None, :, None]

    ctr = np.minimum(p.ctr[None, :, None] * shocks["ctr"][:, :, None] * p.affinity[None], 1.0)
    clicks = imp * ctr
    cvr = np.minimum(
        p.cvr[None, :, None] * shocks["cvr"][:, :, None] * p.cvr_mult[None, None, :], 1.0)
    conv = clicks * cvr

    # Brand-awareness halo on paid search
    total = alloc.sum()
    aware = 0.0
    if total > 0:
        idx = [i for i, c in enumerate(p.channels) if c in ("Display", "Video")]
        aware = alloc[idx].sum() / total
    halo = 1.0 + p.halo_max * min(1.0, aware / p.halo_sat)
    s_idx = p.channels.index("Search")
    conv[:, s_idx, :] *= halo
    conv *= shocks["market"][:, None, None]

    rev_cell = conv * p.aov * p.aov_mult[None, None, :]
    revenue = rev_cell.sum(axis=(1, 2))
    media = float(total)
    cost = media + p.fixed_cost
    n_conv = conv.sum(axis=(1, 2))
    n_click = clicks.sum(axis=(1, 2))
    n_imp = imp.sum(axis=(1, 2))
    gross_profit = revenue * p.margin
    return dict(
        media_spend=np.full_like(revenue, media),
        total_cost=np.full_like(revenue, cost),
        impressions=n_imp, clicks=n_click, conversions=n_conv, revenue=revenue,
        gross_profit=gross_profit, net_profit=gross_profit - cost,
        roas=revenue / max(cost, 1e-9), roi=(gross_profit - cost) / max(cost, 1e-9),
        cpa=cost / np.maximum(n_conv, 1e-9),
        ctr=n_click / np.maximum(n_imp, 1e-9),
        cvr=n_conv / np.maximum(n_click, 1e-9),
        channel_revenue=rev_cell.sum(axis=2).mean(axis=0),   # mean revenue per channel
    )


# ----------------------------------------------------------------------------
# Optimisation (deterministic expected-value model, SLSQP, multi-start)
# ----------------------------------------------------------------------------
MIN_CELL_SHARE = 0.005       # every channel x segment cell gets >= 0.5% of budget
CH_MIN, CH_MAX = 0.05, 0.40  # practical channel share limits
SEG_MIN, SEG_MAX = 0.10, 0.45


def optimise(p: Params, budget: float, mode: str = "joint", n_starts: int = 12,
             seed: int = 0) -> np.ndarray:
    """mode: 'channel' (equal segments), 'segment' (equal channels), or 'joint'."""
    rng = np.random.default_rng(seed)
    n_c, n_s = p.n_c, p.n_s

    if mode == "channel":
        n = n_c
        build = lambda v: make_alloc(p, budget, channel_w=v)
        bounds = [(CH_MIN, CH_MAX)] * n
    elif mode == "segment":
        n = n_s
        build = lambda v: make_alloc(p, budget, segment_w=v)
        bounds = [(SEG_MIN, SEG_MAX)] * n
    elif mode == "joint":
        n = n_c * n_s
        build = lambda v: budget * v.reshape(n_c, n_s)
        bounds = [(MIN_CELL_SHARE, 1.0)] * n
    else:
        raise ValueError(mode)

    def neg_profit(v):
        return -evaluate(build(v), p)["net_profit"][0] / 1e4

    cons = [{"type": "eq", "fun": lambda v: v.sum() - 1.0}]
    if mode == "joint":
        for c in range(n_c):   # channel share limits
            sl = slice(c * n_s, (c + 1) * n_s)
            cons.append({"type": "ineq", "fun": lambda v, sl=sl: v[sl].sum() - CH_MIN})
            cons.append({"type": "ineq", "fun": lambda v, sl=sl: CH_MAX - v[sl].sum()})
        for s in range(n_s):   # segment share limits
            cols = [c * n_s + s for c in range(n_c)]
            cons.append({"type": "ineq", "fun": lambda v, cols=cols: v[cols].sum() - SEG_MIN})
            cons.append({"type": "ineq", "fun": lambda v, cols=cols: SEG_MAX - v[cols].sum()})

    best, best_val = None, np.inf
    for _ in range(n_starts):
        v0 = rng.dirichlet(np.ones(n) * 5)
        res = minimize(neg_profit, v0, method="SLSQP", bounds=bounds, constraints=cons,
                       options=dict(maxiter=400, ftol=1e-10))
        if res.success and res.fun < best_val:
            best, best_val = res.x, res.fun
    if best is None:
        raise RuntimeError("Optimisation failed for all starts")
    best = np.clip(best, 0, None)
    best = best / best.sum()
    return build(best)


# ----------------------------------------------------------------------------
# Summaries
# ----------------------------------------------------------------------------
METRICS = ["revenue", "net_profit", "roas", "roi", "cpa", "conversions"]


def summarise(results: dict, baseline: str) -> pd.DataFrame:
    """Per-scenario mean / 5th / 95th percentile plus paired comparison vs baseline."""
    rows = []
    base = results[baseline]
    for name, r in results.items():
        row = {"scenario": name, "total_cost": r["total_cost"][0]}
        for m in METRICS:
            v = r[m]
            row[f"{m}_mean"] = v.mean()
            row[f"{m}_p5"] = np.percentile(v, 5)
            row[f"{m}_p95"] = np.percentile(v, 95)
        d = r["net_profit"] - base["net_profit"]
        se = d.std(ddof=1) / np.sqrt(len(d))
        row["d_profit_vs_base"] = d.mean()
        row["d_profit_ci_lo"] = d.mean() - 1.96 * se
        row["d_profit_ci_hi"] = d.mean() + 1.96 * se
        row["prob_beats_base"] = float((d > 0).mean())
        row["prob_loss"] = float((r["net_profit"] < 0).mean())
        rows.append(row)
    return pd.DataFrame(rows)
