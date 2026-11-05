"""Static figures for the README and report.  Run: python src/minigrid/figures.py"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from minigrid.economics import lcoe_range, load_assumptions, site_economics  # noqa: E402
from minigrid.mcda import (agreement_with_onsset, load_hexes, load_weight_scenarios, robustness,  # noqa: E402
                           score, shortlist)
from minigrid.paths import FIGURES, GRID_EXISTING, GRID_PLANNED, STATES  # noqa: E402

INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e7e5e0", "#fcfcfb"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
NOTE = ("Data: World Bank ESMAP / KTH-dESA OnSSET Nigeria settlement layer (2016, MIT); geoBoundaries (CC BY 4.0). "
        "Population = 2030 projection. Screening analysis, not a feasibility study.")


def _base(ax, states):
    states.plot(ax=ax, color="#f3f2ef", edgecolor="#c9c7c0", linewidth=0.5)
    ax.set_axis_off()


def _lines(ax):
    gpd.read_file(GRID_EXISTING).plot(ax=ax, color=INK, linewidth=0.9, label="Existing transmission")
    gpd.read_file(GRID_PLANNED).plot(ax=ax, color=INK2, linewidth=0.9, linestyle="--", label="Planned transmission")


def _save(fig, name):
    fig.text(0.01, -0.04, NOTE, fontsize=6.5, color="grey", va="top", transform=fig.transFigure)
    fig.savefig(FIGURES / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return FIGURES / name


def suitability_map(cand, top, states):
    fig, ax = plt.subplots(figsize=(9, 8))
    _base(ax, states)
    sc = ax.scatter(cand.lon, cand.lat, c=cand.score, cmap="Blues", s=1.2, vmin=cand.score.quantile(0.05),
                    vmax=cand.score.max(), linewidths=0)
    _lines(ax)
    ax.scatter(top.lon, top.lat, s=28, color=ORANGE, edgecolor="white", linewidth=0.8, zorder=5, label="Top 100 sites")
    cb = fig.colorbar(sc, ax=ax, shrink=0.45, pad=0.01)
    cb.set_label("Suitability score (eligible areas)", color=INK2)
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.set_title("Where solar mini-grids fit best: top 100 village-scale sites", loc="left", fontsize=13,
                 fontweight="bold", color=INK)
    return _save(fig, "01_suitability_map.png")


def criteria_maps(h, states):
    layers = [("pop_2030", "Population 2030 (per hexagon)", "Blues", True),
              ("grid_km", "Distance to existing grid (km)", "Oranges", False),
              ("ghi", "Solar GHI (kWh/m²/yr)", "YlOrBr", False),
              ("road_km", "Distance to road (km)", "Greens", False)]
    fig, axes = plt.subplots(2, 2, figsize=(10, 9))
    sample = h.sample(min(len(h), 120_000), random_state=1)
    for ax, (col, title, cmap, log) in zip(axes.flat, layers):
        _base(ax, states)
        v = sample[col]
        norm = matplotlib.colors.LogNorm(vmin=max(v.quantile(0.02), 1), vmax=v.quantile(0.995)) if log else None
        kw = {} if log else {"vmin": v.quantile(0.02), "vmax": v.quantile(0.98)}
        s = ax.scatter(sample.lon, sample.lat, c=v, cmap=cmap, s=0.4, linewidths=0, norm=norm, **kw)
        fig.colorbar(s, ax=ax, shrink=0.6, pad=0.01)
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    fig.suptitle("Input layers (H3 hexagons, ~5 km²)", x=0.02, ha="left", fontsize=13, fontweight="bold")
    return _save(fig, "02_criteria_layers.png")


def scenario_comparison(h):
    W = load_weight_scenarios()
    rows = []
    for sc_name in W.index:
        w = W.loc[sc_name].drop("description").astype(float).to_dict()
        top = shortlist(score(h, w), 100)
        rows.append(top.state.value_counts().rename(sc_name))
    df = pd.concat(rows, axis=1).fillna(0)
    df = df.loc[df.sum(axis=1).sort_values(ascending=True).index].tail(12)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [BLUE, ORANGE, AQUA]
    y = range(len(df))
    hgt = 0.26
    for i, (col, c) in enumerate(zip(df.columns, colors)):
        ax.barh([v + (i - 1) * hgt for v in y], df[col], height=hgt, color=c, label=col)
    ax.set_yticks(list(y), df.index)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color=GRID)
    ax.set_xlabel("Sites in the top 100")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Top-100 sites by state under three weighting scenarios", loc="left", fontsize=12,
                 fontweight="bold", color=INK)
    return _save(fig, "03_scenarios_by_state.png")


def onsset_benchmark(cand, top):
    order = ["Grid", "Mini-grid diesel", "Mini-grid PV", "Mini-grid hydro", "Stand-alone diesel", "Stand-alone PV"]
    colors = {"Grid": "#8a8984", "Mini-grid diesel": ORANGE, "Mini-grid PV": YELLOW, "Mini-grid hydro": BLUE,
              "Stand-alone diesel": "#e87ba4", "Stand-alone PV": AQUA}
    shares = pd.DataFrame({"All eligible areas": cand.onsset_tech.value_counts(normalize=True),
                           "Top 100 sites": top.onsset_tech.value_counts(normalize=True)}).reindex(order).fillna(0)
    fig, ax = plt.subplots(figsize=(8, 2.8))
    left = pd.Series(0.0, index=shares.columns)
    for t in order:
        if shares.loc[t].sum() == 0:
            continue
        ax.barh(shares.columns, shares.loc[t], left=left, color=colors[t], label=t, edgecolor="white", linewidth=2)
        left += shares.loc[t]
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.set_title("Benchmark: least-cost technology in the World Bank/KTH OnSSET 2016 run (Tier 3)", loc="left",
                 fontsize=11, fontweight="bold", color=INK, pad=26)
    return _save(fig, "04_onsset_benchmark.png")


def lcoe_chart(top, a):
    r = lcoe_range(top, a)
    rows = [("Diesel generator", a["diesel_lcoe_low"], a["diesel_lcoe_high"], None, "#d03b3b"),
            ("Solar mini-grid", r["low"]["lcoe"], r["high"]["lcoe"], r["central"]["lcoe"], BLUE),
            ("Solar mini-grid + US$350 grant", r["low"]["lcoe_grant"], r["high"]["lcoe_grant"],
             r["central"]["lcoe_grant"], AQUA)]
    fig, ax = plt.subplots(figsize=(8, 2.9))
    for i, (label, lo, hi, mid, c) in enumerate(rows[::-1]):
        ax.plot([lo, hi], [i, i], color=c, linewidth=9, solid_capstyle="round", alpha=0.9)
        ax.text(hi + 0.012, i, f"${lo:.2f}–{hi:.2f}", va="center", fontsize=9, color=INK2)
        if mid is not None:
            ax.plot(mid, i, "o", color="white", markersize=7, markeredgecolor=INK, zorder=3)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
    ax.set_xlim(0, 0.85)
    ax.set_xlabel("Levelised cost of electricity (US$/kWh)")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID)
    ax.set_title("Top 100 sites: indicative LCOE vs diesel (bar = low–high assumptions; dot = central)",
                 loc="left", fontsize=11, fontweight="bold", color=INK)
    return _save(fig, "05_lcoe_vs_diesel.png")


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    h = load_hexes()
    states = gpd.read_file(STATES)
    w = load_weight_scenarios().loc["Balanced"].drop("description").astype(float).to_dict()
    cand = score(h, w)
    cand["robust"] = robustness(cand, w)
    top = shortlist(cand, 100)
    a = load_assumptions()
    for p in (suitability_map(cand, top, states), criteria_maps(h, states), scenario_comparison(h),
              onsset_benchmark(cand, top), lcoe_chart(top, a)):
        print("saved", p.name)
    print(agreement_with_onsset(cand, top).round(3))


if __name__ == "__main__":
    main()
