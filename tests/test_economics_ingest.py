import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minigrid.economics import crf, load_assumptions, portfolio_summary, site_economics  # noqa: E402
from minigrid.ingest import topojson_to_geojson  # noqa: E402
from minigrid.mcda import load_hexes, load_weight_scenarios, score, shortlist  # noqa: E402


def test_crf():
    assert crf(0, 10) == pytest.approx(0.1)
    assert crf(0.10, 20) == pytest.approx(0.117460, rel=1e-5)


def test_site_economics_hand_calc():
    a = {"household_size": 5, "uptake": 1.0, "tier_kwh": 400, "productive_uplift": 0.0, "performance_ratio": 0.8,
         "generation_capex_per_kwp": 1000, "distribution_capex_per_connection": 500, "om_share": 0.0,
         "discount_rate": 0.0, "lifetime_years": 20, "grant_per_connection": 0, "diesel_l_per_kwh": 0.3,
         "diesel_kgco2e_per_l": 2.5}
    e = site_economics(pd.DataFrame({"pop_2030": [5000], "ghi": [2000]}), a).iloc[0]
    assert e.connections == 1000
    assert e.demand_mwh_yr == pytest.approx(400)          # 1000 x 400 kWh
    assert e.pv_kwp == pytest.approx(250)                 # 400,000 / (2000 x 0.8)
    assert e.capex_usd == pytest.approx(750_000)          # 250 x 1000 + 1000 x 500
    assert e.lcoe_usd_kwh == pytest.approx(750_000 / 20 / 400_000)
    assert e.co2_avoided_t_yr == pytest.approx(300)       # 400,000 x 0.3 x 2.5 / 1000


def test_capex_per_connection_within_esmap_range():
    h = load_hexes()
    w = load_weight_scenarios().loc["Balanced"].drop("description").astype(float).to_dict()
    e = site_economics(shortlist(score(h, w), 100), load_assumptions())
    assert e.capex_per_connection.between(500, 2100).all()   # ESMAP (2019) US$500-2,100
    assert e.lcoe_usd_kwh.median() < 0.35                     # below diesel genset LCOE floor
    s = portfolio_summary(e)
    assert s["sites"] == 100 and s["pv_mwp"] > 0


def test_topojson_decoder():
    topo = {"type": "Topology", "transform": {"scale": [1, 1], "translate": [0, 0]},
            "arcs": [[[0, 0], [1, 0], [0, 1]], [[1, 1], [1, 1]]],
            "objects": {"lines": {"type": "GeometryCollection", "geometries": [
                {"type": "LineString", "arcs": [0]}, {"type": "MultiLineString", "arcs": [[0], [~1]]}]}}}
    gj = topojson_to_geojson(topo, "lines")
    assert gj["features"][0]["geometry"]["coordinates"] == [[0, 0], [1, 0], [1, 1]]
    assert gj["features"][1]["geometry"]["coordinates"][1] == [[2, 2], [1, 1]]
