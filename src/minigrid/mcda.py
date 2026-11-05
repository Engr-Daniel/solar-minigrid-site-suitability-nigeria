"""Multi-criteria decision analysis (weighted linear combination) for mini-grid siting.

Steps
  1. Eligibility screen (hard exclusions): population band, mostly rural, minimum distance to the
     existing grid, valid solar data.
  2. Normalise each criterion to 0-1 *within the eligible set* (benefit or cost direction; log,
     min-max or capped-linear transforms - see data/reference/criteria.csv).
  3. Weighted sum -> suitability score 0-100.
  4. Robustness: Monte Carlo over weights (Dirichlet around the chosen weights) -> how often each
     site stays in the top N.
  5. Shortlist with spatial de-duplication (no two neighbouring hexagons).
"""
from __future__ import annotations

from dataclasses import dataclass

import h3
import numpy as np
import pandas as pd

from .paths import HEXES, REFERENCE


@dataclass(frozen=True)
class Screen:
    min_pop: int = 800        # ESMAP typical 3rd-gen mini-grid: 800-4,000 people
    max_pop: int = 10000      # village scale; larger towns -> grid extension or town-scale interconnected mini-grids
    max_urban_share: float = 0.5
    min_grid_km: float = 5.0  # closer than this, grid extension is usually least-cost


def load_hexes():
    return pd.read_parquet(HEXES)


def load_criteria() -> pd.DataFrame:
    return pd.read_csv(REFERENCE / "criteria.csv")


def load_weight_scenarios() -> pd.DataFrame:
    return pd.read_csv(REFERENCE / "weight_scenarios.csv").set_index("scenario")


def eligible(hexes: pd.DataFrame, s: Screen = Screen()) -> pd.Series:
    return (hexes.pop_2030.between(s.min_pop, s.max_pop) & (hexes.urban_share <= s.max_urban_share)
            & (hexes.grid_km >= s.min_grid_km) & hexes.ghi.notna())


def normalise(values: pd.Series, direction: str, transform: str, cap: float | None = None) -> pd.Series:
    """Scale a criterion to 0-1 (1 = best)."""
    v = values.astype(float)
    if transform == "log":
        v = np.log1p(v.clip(lower=0))
        lo, hi = v.min(), v.max()
        z = (v - lo) / (hi - lo) if hi > lo else v * 0 + 1
    elif transform == "log_cap":
        if not cap or cap <= 0:
            raise ValueError("log_cap needs a positive cap")
        v = np.log1p(v.clip(lower=0, upper=cap))
        lo, hi = v.min(), v.max()
        z = (v - lo) / (hi - lo) if hi > lo else v * 0 + 1
    elif transform == "minmax":
        lo, hi = v.min(), v.max()
        z = (v - lo) / (hi - lo) if hi > lo else v * 0 + 1
    elif transform == "linear_cap":
        if not cap or cap <= 0:
            raise ValueError("linear_cap needs a positive cap")
        z = v.clip(lower=0, upper=cap) / cap
    else:
        raise ValueError(f"Unknown transform {transform}")
    z = z.fillna(0.0)
    return 1 - z if direction == "cost" else z


def criteria_matrix(cand: pd.DataFrame, criteria: pd.DataFrame) -> pd.DataFrame:
    cols = {}
    for c in criteria.itertuples():
        cap = None if pd.isna(c.cap) else float(c.cap)
        cols[c.criterion] = normalise(cand[c.column], c.direction, c.transform, cap)
    return pd.DataFrame(cols, index=cand.index)


def check_weights(weights: dict[str, float], criteria: pd.DataFrame) -> pd.Series:
    w = pd.Series(weights, dtype=float).reindex(criteria.criterion).fillna(0.0)
    if (w < 0).any() or w.sum() <= 0:
        raise ValueError("Weights must be non-negative and not all zero.")
    return w / w.sum()


def score(hexes: pd.DataFrame, weights: dict[str, float], screen: Screen = Screen(),
          criteria: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return eligible hexagons with normalised criteria (n_*), score (0-100) and rank."""
    criteria = load_criteria() if criteria is None else criteria
    cand = hexes[eligible(hexes, screen)].copy()
    if cand.empty:
        raise ValueError("No hexagons pass the eligibility screen.")
    w = check_weights(weights, criteria)
    m = criteria_matrix(cand, criteria)
    cand["score"] = 100 * m.values @ w.values
    for col in m.columns:
        cand[f"n_{col}"] = m[col].values
    cand["rank"] = cand["score"].rank(ascending=False, method="first").astype(int)
    return cand.sort_values("rank")


def robustness(cand: pd.DataFrame, weights: dict[str, float], criteria: pd.DataFrame | None = None,
               n_draws: int = 1000, top_n: int = 100, concentration: float = 20.0, seed: int = 42) -> pd.Series:
    """Share of random weight draws (Dirichlet around `weights`) in which each site stays in the top N.

    concentration controls spread: higher = draws closer to the chosen weights.
    Criteria with zero weight stay at zero.
    """
    criteria = load_criteria() if criteria is None else criteria
    w = check_weights(weights, criteria)
    active = w[w > 0]
    m = cand[[f"n_{c}" for c in active.index]].values
    rng = np.random.default_rng(seed)
    draws = rng.dirichlet(active.values * concentration, size=n_draws)  # (draws, k)
    scores = m @ draws.T                                               # (sites, draws)
    k = min(top_n, len(cand))
    thresh = np.partition(scores, -k, axis=0)[-k]                      # k-th best per draw
    return pd.Series((scores >= thresh).mean(axis=1), index=cand.index, name="top_n_frequency")


def shortlist(cand: pd.DataFrame, n: int = 100, min_ring: int = 1) -> pd.DataFrame:
    """Greedy pick by rank, skipping hexagons within `min_ring` H3 rings of an already chosen site."""
    chosen, blocked = [], set()
    for idx, h in zip(cand.index, cand.h3):
        if h in blocked:
            continue
        chosen.append(idx)
        blocked.update(h3.grid_disk(h, min_ring))
        if len(chosen) >= n:
            break
    return cand.loc[chosen]


def agreement_with_onsset(cand: pd.DataFrame, top: pd.DataFrame) -> pd.DataFrame:
    """Share of sites for which OnSSET-2016's least-cost technology (Tier 3, low diesel price) is a mini-grid.

    Historical benchmark: the 2016 run used 2016 PV/battery costs and chose almost only *diesel*
    mini-grids for small, sparse villages, preferring grid extension for larger compact settlements.
    """
    is_mg = lambda d: d.onsset_tech_code.between(4, 7)  # noqa: E731
    rows = {"Top shortlist": top, "All eligible": cand}
    return pd.DataFrame({k: {"sites": len(v), "onsset_minigrid_share": is_mg(v).mean(),
                             "onsset_minigrid_pop_share": v.pop_2030[is_mg(v)].sum() / v.pop_2030.sum()}
                         for k, v in rows.items()}).T
