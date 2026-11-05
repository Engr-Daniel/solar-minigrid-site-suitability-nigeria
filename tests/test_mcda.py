import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minigrid.mcda import (Screen, check_weights, eligible, load_criteria, load_hexes,  # noqa: E402
                           load_weight_scenarios, normalise, robustness, score, shortlist)


def toy():
    base = h3.latlng_to_cell(10.0, 8.0, 7)
    cells = list(h3.grid_disk(base, 2))[:6]
    return pd.DataFrame({
        "h3": cells,
        "pop_2030": [500, 1000, 3000, 6000, 9000, 30000],
        "urban_share": [0, 0, 0, 0, 0.8, 0],
        "grid_km": [20, 3, 10, 60, 40, 80],
        "planned_km": [20, 3, 10, 30, 40, 50],
        "road_km": [1, 1, 15, 0.5, 2, 1],
        "ghi": [2100, 2200, 2000, 2300, np.nan, 2250],
        "peak_density": [300, 600, 1500, 4000, 6000, 20000],
        "poverty_index": [0.5, 0.4, 0.6, 0.7, 0.2, 0.3],
        "onsset_tech_code": [4, 1, 4, 1, 1, 1],
    })


def test_normalise_directions_and_caps():
    v = pd.Series([0, 10, 20, 100])
    assert normalise(v, "benefit", "linear_cap", 20).tolist() == [0, 0.5, 1, 1]
    assert normalise(v, "cost", "linear_cap", 20).tolist() == [1, 0.5, 0, 0]
    z = normalise(pd.Series([800, 4000, 9000]), "benefit", "log_cap", 4000)
    assert z.tolist() == pytest.approx([0, 1, 1])
    with pytest.raises(ValueError):
        normalise(v, "benefit", "linear_cap", None)


def test_eligibility_screen():
    e = eligible(toy(), Screen(min_pop=800, max_pop=10000, max_urban_share=0.5, min_grid_km=5))
    # 500 too small; grid 3 km too close; urban + missing GHI; 30000 too large
    assert e.tolist() == [False, False, True, True, False, False]


def test_weights_validated_and_normalised():
    crit = load_criteria()
    w = check_weights({"demand": 2, "remoteness": 2}, crit)
    assert w.sum() == pytest.approx(1) and w["demand"] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        check_weights({"demand": -1}, crit)


def test_score_orders_better_site_first():
    s = score(toy(), {"demand": 1, "remoteness": 1}, Screen())
    assert s.iloc[0].pop_2030 == 6000  # bigger and further from grid
    assert s.score.between(0, 100).all()
    assert s["rank"].tolist() == [1, 2]


def test_shortlist_skips_neighbours():
    base = h3.latlng_to_cell(10.0, 8.0, 7)
    nb = [c for c in h3.grid_disk(base, 1) if c != base][0]
    far = h3.latlng_to_cell(12.0, 6.0, 7)
    cand = pd.DataFrame({"h3": [base, nb, far], "rank": [1, 2, 3]}, index=[0, 1, 2])
    assert shortlist(cand, n=3).index.tolist() == [0, 2]


def test_robustness_bounds_and_determinism():
    h = load_hexes()
    w = load_weight_scenarios().loc["Balanced"].drop("description").astype(float).to_dict()
    c = score(h, w)
    r1 = robustness(c, w, n_draws=200, top_n=50, seed=1)
    r2 = robustness(c, w, n_draws=200, top_n=50, seed=1)
    assert r1.between(0, 1).all() and r1.equals(r2)
    assert r1.sum() == pytest.approx(50, abs=1)  # each draw selects ~top_n sites


def test_real_data_sanity():
    h = load_hexes()
    assert len(h) > 180_000 and h.state.nunique() == 37
    assert h.pop_2030.sum() == pytest.approx(262.07e6, rel=0.001)
    assert h.h3.is_unique
