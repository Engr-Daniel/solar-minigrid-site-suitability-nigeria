"""Indicative site economics: demand, PV sizing, capex, LCOE and CO2 avoided vs diesel gensets.

Screening-level only - not a feasibility study. All inputs live in
data/reference/economic_assumptions.csv with their sources.
"""
from __future__ import annotations

import pandas as pd

from .paths import REFERENCE


def load_assumptions() -> dict[str, float]:
    a = pd.read_csv(REFERENCE / "economic_assumptions.csv")
    return dict(zip(a.parameter, a.value.astype(float)))


def crf(rate: float, years: int) -> float:
    if years <= 0:
        raise ValueError("years must be positive")
    if rate == 0:
        return 1 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def site_economics(sites: pd.DataFrame, a: dict[str, float] | None = None) -> pd.DataFrame:
    """Add demand, sizing, cost, LCOE and CO2 columns to a table with pop_2030 and ghi."""
    a = load_assumptions() if a is None else a
    out = sites.copy()
    households = out.pop_2030 / a["household_size"]
    out["connections"] = (households * a["uptake"]).round()
    out["demand_mwh_yr"] = out.connections * a["tier_kwh"] * (1 + a["productive_uplift"]) / 1000
    out["yield_kwh_per_kwp"] = out.ghi * a["performance_ratio"]
    out["pv_kwp"] = out.demand_mwh_yr * 1000 / out.yield_kwh_per_kwp
    out["capex_usd"] = out.pv_kwp * a["generation_capex_per_kwp"] + out.connections * a["distribution_capex_per_connection"]
    out["capex_per_connection"] = out.capex_usd / out.connections
    annual = out.capex_usd * (crf(a["discount_rate"], int(a["lifetime_years"])) + a["om_share"])
    out["lcoe_usd_kwh"] = annual / (out.demand_mwh_yr * 1000)
    grant_annual = out.connections * a["grant_per_connection"] * crf(a["discount_rate"], int(a["lifetime_years"]))
    out["lcoe_with_grant_usd_kwh"] = (annual - grant_annual) / (out.demand_mwh_yr * 1000)
    out["co2_avoided_t_yr"] = out.demand_mwh_yr * 1000 * a["diesel_l_per_kwh"] * a["diesel_kgco2e_per_l"] / 1000
    return out


def portfolio_summary(sites: pd.DataFrame) -> dict[str, float]:
    return {
        "sites": len(sites),
        "people": float(sites.pop_2030.sum()),
        "connections": float(sites.connections.sum()),
        "pv_mwp": float(sites.pv_kwp.sum() / 1000),
        "capex_musd": float(sites.capex_usd.sum() / 1e6),
        "co2_avoided_kt_yr": float(sites.co2_avoided_t_yr.sum() / 1000),
        "median_lcoe": float(sites.lcoe_usd_kwh.median()),
        "median_lcoe_grant": float(sites.lcoe_with_grant_usd_kwh.median()),
    }


def lcoe_range(sites: pd.DataFrame, a: dict[str, float] | None = None) -> dict[str, dict[str, float]]:
    """Portfolio median LCOE under central, low-cost and high-cost assumption sets (from the CSV ranges)."""
    a = load_assumptions() if a is None else a
    rng = pd.read_csv(REFERENCE / "economic_assumptions.csv").set_index("parameter")[["low", "high"]]
    favourable_low = ["generation_capex_per_kwp", "distribution_capex_per_connection", "om_share", "discount_rate"]
    favourable_high = ["performance_ratio"]
    cases = {"central": dict(a), "low": dict(a), "high": dict(a)}
    for p in favourable_low:
        cases["low"][p], cases["high"][p] = rng.loc[p, "low"], rng.loc[p, "high"]
    for p in favourable_high:
        cases["low"][p], cases["high"][p] = rng.loc[p, "high"], rng.loc[p, "low"]
    out = {}
    for k, case in cases.items():
        e = site_economics(sites, case)
        out[k] = {"lcoe": float(e.lcoe_usd_kwh.median()), "lcoe_grant": float(e.lcoe_with_grant_usd_kwh.median())}
    return out
