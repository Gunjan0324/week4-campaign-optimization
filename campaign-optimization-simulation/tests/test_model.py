"""Basic correctness tests. Run with:  pytest -q   (from the repo root)"""
import numpy as np

from src.model import (TOTAL_BUDGET, draw_shocks, evaluate, load_params, make_alloc,
                       no_shocks, optimise)


def test_allocation_sums_to_budget():
    p = load_params()
    a = make_alloc(p, 50_000, channel_w=[3, 1, 1, 1, 1], segment_w=[1, 2, 3, 4])
    assert np.isclose(a.sum(), 50_000)
    assert a.shape == (p.n_c, p.n_s)


def test_zero_spend_gives_zero_revenue():
    p = load_params()
    r = evaluate(np.zeros((p.n_c, p.n_s)), p)
    assert r["revenue"][0] == 0 and r["conversions"][0] == 0


def test_diminishing_returns():
    """Doubling spend must less-than-double revenue (alpha < 1)."""
    p = load_params()
    r1 = evaluate(make_alloc(p, 100_000), p)["revenue"][0]
    r2 = evaluate(make_alloc(p, 200_000), p)["revenue"][0]
    assert r1 < r2 < 2 * r1


def test_shocks_have_mean_one_and_are_reproducible():
    p = load_params()
    a, b = draw_shocks(p, 20_000, 1), draw_shocks(p, 20_000, 1)
    assert np.allclose(a["cvr"], b["cvr"])
    assert abs(a["cvr"].mean() - 1) < 0.01


def test_optimiser_respects_budget_and_beats_baseline():
    p = load_params()
    base = evaluate(make_alloc(p, TOTAL_BUDGET), p)["net_profit"][0]
    a = optimise(p, TOTAL_BUDGET, "joint", n_starts=4)
    assert np.isclose(a.sum(), TOTAL_BUDGET, rtol=1e-6)
    assert evaluate(a, p)["net_profit"][0] > base
    assert (a.sum(axis=1) / a.sum() <= 0.40 + 1e-6).all()   # channel cap respected


def test_monte_carlo_mean_close_to_deterministic():
    p = load_params()
    a = make_alloc(p, TOTAL_BUDGET)
    det = evaluate(a, p, no_shocks(p))["revenue"][0]
    mc = evaluate(a, p, draw_shocks(p, 20_000, 7))["revenue"].mean()
    assert abs(mc / det - 1) < 0.03
