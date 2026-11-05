"""Pinned headline results. Update deliberately together with README / MEMORY."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minigrid.economics import portfolio_summary, site_economics  # noqa: E402
from minigrid.mcda import agreement_with_onsset, load_hexes, load_weight_scenarios, score, shortlist  # noqa: E402


@pytest.fixture(scope="module")
def balanced():
    h = load_hexes()
    w = load_weight_scenarios().loc["Balanced"].drop("description").astype(float).to_dict()
    cand = score(h, w)
    top = site_economics(shortlist(cand, 100))
    return cand, top


def test_headline_numbers(balanced):
    cand, top = balanced
    s = portfolio_summary(top)
    assert len(cand) == 33138
    assert s["people"] == pytest.approx(758_632, rel=0.002)
    assert s["pv_mwp"] == pytest.approx(27.62, rel=0.01)
    assert s["capex_musd"] == pytest.approx(77.2, rel=0.01)
    assert s["median_lcoe"] == pytest.approx(0.262, abs=0.005)
    top3 = top.state.value_counts().index[:3].tolist()
    assert set(top3) == {"Katsina", "Bauchi", "Zamfara"}


def test_onsset_benchmark_documented(balanced):
    cand, top = balanced
    ag = agreement_with_onsset(cand, top)
    assert ag.loc["All eligible", "onsset_minigrid_share"] == pytest.approx(0.365, abs=0.01)
