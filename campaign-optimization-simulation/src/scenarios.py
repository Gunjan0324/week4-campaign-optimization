"""Scenario definitions. Every scenario returns (allocation matrix, Params)."""
from __future__ import annotations

from dataclasses import replace

from .model import TOTAL_BUDGET, load_params, make_alloc, optimise

CRO_COST = 4_000.0      # landing-page / conversion-rate-optimisation programme (non-media)
CRO_UPLIFT = 0.12       # +12% conversion rate on every channel


def build_scenarios(p=None):
    p = p or load_params()
    ch = list(p.channels)   # Search, Social, Email, Display, Video

    def mix(**w):
        return [w[c] for c in ch]

    sc = {}
    sc["S0 Baseline (equal split)"] = (make_alloc(p, TOTAL_BUDGET), p)
    sc["S1 Budget +25%"] = (make_alloc(p, TOTAL_BUDGET * 1.25), p)
    sc["S2 Budget -25%"] = (make_alloc(p, TOTAL_BUDGET * 0.75), p)
    sc["S3 Performance-heavy mix"] = (make_alloc(
        p, TOTAL_BUDGET, channel_w=mix(Search=.35, Social=.30, Email=.10, Display=.10, Video=.15)), p)
    sc["S4 Awareness-heavy mix"] = (make_alloc(
        p, TOTAL_BUDGET, channel_w=mix(Search=.15, Social=.25, Email=.05, Display=.25, Video=.30)), p)
    sc["S5 Channel-optimised"] = (optimise(p, TOTAL_BUDGET, "channel"), p)
    sc["S6 Segment-targeted"] = (optimise(p, TOTAL_BUDGET, "segment"), p)
    sc["S7 Jointly optimised"] = (optimise(p, TOTAL_BUDGET, "joint"), p)
    p_cro = replace(p, cvr=p.cvr * (1 + CRO_UPLIFT), fixed_cost=CRO_COST)
    sc["S8 Joint + CRO"] = (optimise(p_cro, TOTAL_BUDGET - CRO_COST, "joint"), p_cro)
    return sc
