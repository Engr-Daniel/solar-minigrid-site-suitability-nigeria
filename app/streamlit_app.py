"""Solar mini-grid site suitability explorer (Nigeria).  Run: streamlit run app/streamlit_app.py

UI only - all calculations live in src/minigrid.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from minigrid.economics import lcoe_range, load_assumptions, portfolio_summary, site_economics  # noqa: E402
from minigrid.mcda import (Screen, agreement_with_onsset, load_criteria, load_hexes,  # noqa: E402
                           load_weight_scenarios, robustness, score, shortlist)
from minigrid.paths import GRID_EXISTING, GRID_PLANNED  # noqa: E402

INK, INK2, INK3, BORDER, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e7e5e0", "#ecebe7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # one-hue sequential
REPO = "https://github.com/Engr-Daniel/solar-minigrid-site-suitability-nigeria"
CRIT_LABEL = {"demand": "Demand (population)", "compactness": "Compactness", "remoteness": "Remote from grid",
              "grid_risk": "Far from future grid", "solar": "Solar resource", "access": "Road access",
              "need": "Poverty (need)"}

st.set_page_config(page_title="Solar Mini-Grid Siting · Nigeria", page_icon="☀️", layout="wide")
st.markdown(f"""
<style>
  .block-container {{padding-top: 2rem; max-width: 1360px;}}
  .hero h1 {{font-size: 1.85rem; margin: 0 0 4px 0;}}
  .hero p {{color: {INK2}; margin: 0;}}
  .hero {{border-bottom: 1px solid {BORDER}; padding-bottom: 12px; margin-bottom: 16px;}}
  .badge {{display:inline-block; font-size:0.74rem; padding:3px 9px; border-radius:999px; margin:8px 6px 0 0;
           background:#eef4fc; color:#184f95; border:1px solid #d5e5f8;}}
  .badge.warn {{background:#fff6e5; color:#7a5200; border-color:#f6e1b3;}}
  .kpi {{background:#fff; border:1px solid {BORDER}; border-radius:14px; padding:14px 16px; min-height:122px;}}
  .kpi .label {{font-size:0.72rem; color:{INK2}; text-transform:uppercase; letter-spacing:0.05em; font-weight:600;}}
  .kpi .value {{font-size:1.6rem; font-weight:700; color:{INK}; line-height:1.25; margin-top:4px;}}
  .kpi .unit {{font-size:0.9rem; font-weight:500; color:{INK2};}}
  .kpi .sub {{font-size:0.8rem; color:{INK2}; margin-top:2px;}}
  .insight {{background:#fff; border:1px solid {BORDER}; border-left:4px solid {BLUE}; border-radius:12px;
             padding:13px 15px; height:100%;}}
  .insight .t {{font-weight:700; font-size:0.93rem; margin-bottom:4px;}}
  .insight .b {{font-size:0.85rem; color:{INK2}; line-height:1.45;}}
  div[data-testid="stTabs"] button p {{font-size:0.95rem; font-weight:600;}}
  .legend span {{display:inline-block; width:22px; height:10px; margin-right:1px;}}
</style>""", unsafe_allow_html=True)


def kpi(col, label, value, unit="", sub=""):
    col.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{value} '
                 f'<span class="unit">{unit}</span></div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def insight(col, title, body, accent=BLUE):
    col.markdown(f'<div class="insight" style="border-left-color:{accent}"><div class="t">{title}</div>'
                 f'<div class="b">{body}</div></div>', unsafe_allow_html=True)


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


RAMP_RGB = [hex_rgb(c) + [210] for c in RAMP]  # plain Python ints (pydeck can't serialise numpy ints)


def colour_by_score(s: pd.Series):
    q = s.rank(pct=True).clip(0, 0.9999)
    idx = (q * len(RAMP)).astype(int).tolist()
    return [RAMP_RGB[i] for i in idx]


# ----------------------------------------------------------------------------- data
@st.cache_data
def data():
    return load_hexes(), load_weight_scenarios(), load_criteria(), load_assumptions()


@st.cache_data
def grid_layers():
    return json.loads(GRID_EXISTING.read_text()), json.loads(GRID_PLANNED.read_text())


@st.cache_data(show_spinner="Scoring 190,000 hexagons…")
def run(weights_items: tuple, screen_items: tuple, states: tuple, conservative: bool, n_top: int):
    w, scr = dict(weights_items), Screen(**dict(screen_items))
    h = HEX if not states else HEX[HEX.state.isin(states)]
    cand = score(h, w, scr)
    if conservative:
        cand = cand[cand.onsset_tech_code.between(4, 7)]
        cand["rank"] = range(1, len(cand) + 1)
    cand["robust"] = robustness(cand, w, top_n=n_top, n_draws=600)
    top = site_economics(shortlist(cand, n_top), A)
    return cand, top


HEX, W, CRIT, A = data()
EXIST, PLAN = grid_layers()

# ----------------------------------------------------------------------------- sidebar controls
with st.sidebar:
    st.markdown("### ☀️ Siting controls")
    scen = st.selectbox("Weighting scenario", list(W.index), help="Preset priorities. Fine-tune below.")
    base_w = W.loc[scen].drop("description").astype(float)
    st.caption(W.loc[scen, "description"])
    with st.expander("Fine-tune criterion weights"):
        weights = {k: st.slider(CRIT_LABEL[k], 0.0, 0.5, float(v), 0.05, key=f"w_{scen}_{k}") for k, v in base_w.items()}
    if sum(weights.values()) == 0:
        st.error("Set at least one weight above zero.")
        st.stop()
    st.markdown("**Eligibility screen**")
    pop_rng = st.slider("Population per site (2030)", 200, 30000, (800, 10000), 100)
    min_grid = st.slider("Min. distance to existing grid (km)", 0, 50, 5)
    max_urban = st.slider("Max. urban share", 0.0, 1.0, 0.5, 0.1)
    states = st.multiselect("States (empty = all)", sorted(HEX.state.dropna().unique()))
    conservative = st.toggle("Conservative: only sites OnSSET-2016 also classed mini-grid", value=False,
                             help="OnSSET 2016 used 2016 PV/battery costs, so it rarely chose solar mini-grids.")
    n_top = st.select_slider("Shortlist size", [25, 50, 100, 200], value=100)
    st.divider()
    st.link_button("💻 Code & methodology", REPO, width="stretch")
    st.caption("Built by **Daniel Oyewale** · Petgrave.io")

screen_items = tuple(sorted({"min_pop": pop_rng[0], "max_pop": pop_rng[1], "min_grid_km": float(min_grid),
                             "max_urban_share": float(max_urban)}.items()))
try:
    cand, top = run(tuple(sorted(weights.items())), screen_items, tuple(states), conservative, n_top)
except ValueError as e:
    st.warning(f"{e} Relax the eligibility screen.")
    st.stop()
summ = portfolio_summary(top)

# ----------------------------------------------------------------------------- hero
st.markdown("""
<div class="hero">
  <h1>Where should Nigeria build its next solar mini-grids?</h1>
  <p>Multi-criteria siting of village-scale solar mini-grids across 190,000 hexagons (~5 km² each), using
     population, grid distance, roads and solar resource.</p>
  <span class="badge warn">⚠️ Screening analysis: 2016 settlement data, 2030 population projection</span>
  <span class="badge">World Bank ESMAP / KTH OnSSET layer</span><span class="badge">H3 hexagons</span>
  <span class="badge">Weight-robustness tested</span>
</div>""", unsafe_allow_html=True)

t_map, t_rank, t_site, t_rob, t_meth = st.tabs(["Map", "Shortlist", "Site profile", "Robustness & benchmark",
                                                "Method & data"])

# ============================================================================= MAP
with t_map:
    c = st.columns(5)
    kpi(c[0], "Eligible areas", f"{len(cand):,}", "hexagons", f"of {len(HEX):,} populated")
    kpi(c[1], f"Top {len(top)} sites serve", f"{summ['people']/1e6:,.2f}", "M people",
        f"~{summ['connections']:,.0f} connections")
    kpi(c[2], "Solar PV needed", f"{summ['pv_mwp']:,.1f}", "MWp", f"capex ≈ ${summ['capex_musd']:,.0f}M")
    kpi(c[3], "Median LCOE", f"${summ['median_lcoe']:.2f}", "/kWh",
        f"${summ['median_lcoe_grant']:.2f} with $350 grant · diesel $0.35–0.70")
    kpi(c[4], "CO₂ avoided vs diesel", f"{summ['co2_avoided_kt_yr']:,.1f}", "kt / yr", "if gensets were the alternative")
    st.write("")

    view_df = cand[["h3", "score", "pop_2030", "grid_km", "road_km", "ghi", "state", "lga", "rank"]].copy()
    view_df["color"] = colour_by_score(view_df.score)
    tops = top[["lon", "lat", "rank", "state", "lga", "pop_2030", "score", "pv_kwp", "lcoe_usd_kwh"]].copy()
    layers = [
        pdk.Layer("H3HexagonLayer", view_df, get_hexagon="h3", get_fill_color="color", stroked=False,
                  extruded=False, pickable=True, opacity=0.75),
        pdk.Layer("GeoJsonLayer", EXIST, get_line_color=[11, 11, 11], line_width_min_pixels=1.5),
        pdk.Layer("GeoJsonLayer", PLAN, get_line_color=[138, 137, 132], line_width_min_pixels=1.2),
        pdk.Layer("ScatterplotLayer", tops, get_position=["lon", "lat"], get_fill_color=hex_rgb(ORANGE) + [235],
                  get_line_color=[255, 255, 255], line_width_min_pixels=1.5, stroked=True, radius_min_pixels=5,
                  get_radius=2500, pickable=True),
    ]
    tooltip = {"html": "<b>{state} · {lga}</b><br/>Rank {rank} · score {score}<br/>Population 2030: {pop_2030}",
               "style": {"backgroundColor": "white", "color": INK, "fontSize": "12px"}}
    view_df["score"] = view_df.score.round(1)
    tops["score"] = tops.score.round(1)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=9.1, longitude=8.6, zoom=5.3),
                             map_style="light", tooltip=tooltip), height=560)
    st.markdown(f'<div class="legend" style="font-size:0.82rem;color:{INK2}">Suitability (percentile within eligible '
                f'areas): low {"".join(f"<span style=background:{c}></span>" for c in RAMP)} high &nbsp;·&nbsp; '
                f'<b style="color:{ORANGE}">●</b> shortlisted site &nbsp;·&nbsp; ━ existing grid &nbsp;·&nbsp; '
                f'<span style="color:{INK3}">━</span> planned grid</div>', unsafe_allow_html=True)
    st.write("")
    i1, i2, i3 = st.columns(3)
    top_states = top.state.value_counts()
    insight(i1, "🌍 The north-west and north-east lead",
            f"{', '.join(top_states.index[:3])} hold <b>{top_states.iloc[:3].sum()/len(top):.0%}</b> of the shortlist: "
            "compact villages 50–100 km from the grid, under the country's strongest sun.")
    insight(i2, "⚡ Cheaper than diesel at screening level",
            f"Central LCOE <b>${summ['median_lcoe']:.2f}/kWh</b> vs $0.35–0.70 for diesel gensets; a $350/connection "
            f"grant brings it to <b>${summ['median_lcoe_grant']:.2f}</b>.", AQUA)
    insight(i3, "🔎 Check before you build",
            "Settlement data dates from 2016 and grids have grown since. Shortlisted sites need on-the-ground "
            "verification of grid status, demand and willingness to pay.", ORANGE)

# ============================================================================= SHORTLIST
with t_rank:
    st.markdown(f"**Top {len(top)} sites** (spatially de-duplicated: no two neighbouring hexagons). Click a column to sort.")
    tbl = top[["rank", "state", "lga", "pop_2030", "connections", "grid_km", "planned_km", "road_km", "ghi", "score",
               "robust", "pv_kwp", "capex_usd", "lcoe_usd_kwh", "co2_avoided_t_yr", "onsset_tech", "lat", "lon"]]
    st.dataframe(tbl, hide_index=True, width="stretch", height=520, column_config={
        "rank": "Rank", "state": "State", "lga": "LGA",
        "pop_2030": st.column_config.NumberColumn("Pop. 2030", format="%,d"),
        "connections": st.column_config.NumberColumn("Connections", format="%,d"),
        "grid_km": st.column_config.NumberColumn("Grid km", format="%.0f"),
        "planned_km": st.column_config.NumberColumn("Future grid km", format="%.0f"),
        "road_km": st.column_config.NumberColumn("Road km", format="%.1f"),
        "ghi": st.column_config.NumberColumn("GHI", format="%,.0f"),
        "score": st.column_config.ProgressColumn("Score", format="%.1f", min_value=0, max_value=100),
        "robust": st.column_config.ProgressColumn("Robust", format="percent", min_value=0, max_value=1,
                                                  help="Share of 600 random weight sets keeping the site in the top N"),
        "pv_kwp": st.column_config.NumberColumn("PV kWp", format="%,.0f"),
        "capex_usd": st.column_config.NumberColumn("Capex", format="$%,.0f"),
        "lcoe_usd_kwh": st.column_config.NumberColumn("LCOE $/kWh", format="%.2f"),
        "co2_avoided_t_yr": st.column_config.NumberColumn("CO₂ t/yr", format="%,.0f"),
        "onsset_tech": "OnSSET-2016 choice", "lat": st.column_config.NumberColumn("Lat", format="%.4f"),
        "lon": st.column_config.NumberColumn("Lon", format="%.4f")})
    st.download_button("⬇️ Download shortlist (CSV)", tbl.to_csv(index=False).encode(), "minigrid_shortlist.csv",
                       "text/csv")
    a, b = st.columns(2, gap="large")
    by_state = top.groupby("state").agg(sites=("h3", "size"), people=("pop_2030", "sum")).sort_values("sites")
    fig = go.Figure(go.Bar(y=by_state.index, x=by_state.sites, orientation="h", marker_color=BLUE,
                           text=by_state.sites, textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x} sites<extra></extra>"))
    fig.update_layout(title="<b>Shortlisted sites by state</b>", height=max(300, 26 * len(by_state) + 80),
                      margin=dict(l=8, r=30, t=50, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      barcornerradius=4, xaxis=dict(gridcolor=GRID), font=dict(color=INK2))
    a.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    fig = go.Figure(go.Histogram(x=top.pop_2030, nbinsx=20, marker_color=AQUA))
    fig.update_layout(title="<b>Site size: population 2030</b>", height=320, bargap=0.08,
                      margin=dict(l=8, r=10, t=50, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(title="People per site", tickformat=","), yaxis=dict(title="Sites", gridcolor=GRID),
                      font=dict(color=INK2))
    b.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ============================================================================= SITE PROFILE
with t_site:
    opts = {r.h3: f"#{r.rank} · {r.state}, {r.lga} · {r.pop_2030:,.0f} people" for r in top.itertuples()}
    pick = st.selectbox("Choose a shortlisted site", list(opts), format_func=opts.get)
    s = top.set_index("h3").loc[pick]
    c = st.columns(4)
    kpi(c[0], "Rank / score", f"#{int(s['rank'])}", f"· {s.score:.1f}", f"robust in {s.robust:.0%} of weight draws")
    kpi(c[1], "People 2030", f"{s.pop_2030:,.0f}", "", f"~{s.connections:,.0f} connections")
    kpi(c[2], "System size", f"{s.pv_kwp:,.0f}", "kWp", f"capex ≈ ${s.capex_usd/1e3:,.0f}k "
        f"(${s.capex_per_connection:,.0f}/connection)")
    kpi(c[3], "LCOE", f"${s.lcoe_usd_kwh:.2f}", "/kWh", f"${s.lcoe_with_grant_usd_kwh:.2f} with grant · "
        f"{s.co2_avoided_t_yr:,.0f} t CO₂/yr avoided")
    st.write("")
    a, b = st.columns([1.1, 1], gap="large")
    crit = [k for k in CRIT_LABEL if f"n_{k}" in s.index]
    vals = [float(s[f"n_{k}"]) for k in crit]
    fig = go.Figure(go.Bar(y=[CRIT_LABEL[k] for k in crit][::-1], x=vals[::-1], orientation="h", marker_color=BLUE,
                           text=[f"{v:.2f}" for v in vals[::-1]], textposition="outside", cliponaxis=False))
    fig.update_layout(title="<b>Criterion scores (0 = worst, 1 = best among eligible areas)</b>", height=340,
                      margin=dict(l=8, r=30, t=50, b=10), xaxis=dict(range=[0, 1.12], gridcolor=GRID),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", barcornerradius=4,
                      font=dict(color=INK2))
    a.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    b.markdown(f"""
**{s.state} · {s.lga}**

| | |
|---|---|
| Distance to existing grid | **{s.grid_km:,.0f} km** |
| Distance to future grid (existing or planned) | **{s.planned_km:,.0f} km** |
| Distance to road | **{s.road_km:,.1f} km** |
| Solar GHI | **{s.ghi:,.0f} kWh/m²/yr** → {s.yield_kwh_per_kwp:,.0f} kWh/kWp/yr |
| Densest 1 km² cell | **{s.peak_density:,.0f} people** |
| OnSSET-2016 least-cost choice | {s.onsset_tech} |
| Location | {s.lat:.4f}, {s.lon:.4f} · H3 `{pick}` |
""")
    b.caption("Indicative screening economics. Not a feasibility study: verify grid status, demand and site access.")

# ============================================================================= ROBUSTNESS & BENCHMARK
with t_rob:
    a, b = st.columns(2, gap="large")
    fig = go.Figure(go.Histogram(x=top.robust, nbinsx=20, marker_color=BLUE))
    fig.update_layout(title=f"<b>How robust is the shortlist?</b><br><sup>Share of 600 random weight sets "
                            f"(Dirichlet around the chosen weights) that keep each site in the top {len(top)}</sup>",
                      height=360, margin=dict(l=8, r=10, t=70, b=10), bargap=0.08, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(tickformat=".0%", title="Top-N frequency"),
                      yaxis=dict(title="Sites", gridcolor=GRID), font=dict(color=INK2))
    a.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    a.markdown(f"**{(top.robust >= 0.8).mean():.0%}** of shortlisted sites stay in the top {len(top)} in ≥80% of "
               "weight draws, so the shortlist is not an artefact of one weighting choice.")
    ag = agreement_with_onsset(cand, top)
    b.markdown("#### Benchmark vs the World Bank/KTH OnSSET 2016 run")
    b.dataframe(ag.rename(columns={"sites": "Sites", "onsset_minigrid_share": "OnSSET chose a mini-grid",
                                   "onsset_minigrid_pop_share": "…share of population"}),
                width="stretch", column_config={"OnSSET chose a mini-grid": st.column_config.NumberColumn(format="percent"),
                                                "…share of population": st.column_config.NumberColumn(format="percent"),
                                                "Sites": st.column_config.NumberColumn(format="%,d")})
    b.markdown("""
**Why the shortlist disagrees with OnSSET-2016, and why that's expected:**
- The 2016 run used **2016 solar and battery costs**. It chose solar PV mini-grids for only ~0.1% of Nigeria's population,
  and its "mini-grids" were almost all **diesel**, in small (<1,500 people), sparse villages.
- For larger, compact settlements it preferred **grid extension**, assuming the grid would arrive.
- With current costs, SEforALL's **2022 Nigeria Integrated Energy Plan** finds mini-grids least-cost predominantly in
  **denser settlements further from the grid**. That's the profile this shortlist targets.
- Use the **Conservative** toggle in the sidebar to see only sites both models agree on.
""")

# ============================================================================= METHOD & DATA
with t_meth:
    a, b = st.columns(2, gap="large")
    a.markdown("""
#### How the ranking works
1. **Units:** 934,595 OnSSET 1 km² settlement cells, aggregated to **H3 resolution-7 hexagons** (~5 km², about the
   area a village mini-grid serves).
2. **Eligibility screen:** population band, mostly rural, minimum distance to the existing grid, valid solar data
   (all adjustable in the sidebar).
3. **Criteria**, normalised 0–1 within the eligible set: demand (log, saturating at 4,000 people), compactness,
   distance to existing grid (capped 50 km), distance to future grid (capped 30 km), solar GHI, road access (capped 20 km),
   and optional LGA poverty.
4. **Weighted linear combination** → score 0–100. Three preset weightings, or tune your own.
5. **Robustness:** 600 random weight sets around your choice. **Shortlist:** greedy by rank with no neighbouring hexagons.
6. **Economics:** demand = households × 70% uptake × MTF Tier 3 (365 kWh) + 30% productive use; PV sized from GHI;
   capex = PV+battery $1,200/kWp + distribution $450/connection; 10% discount rate, 20 years.
""")
    rng = lcoe_range(top, A)
    b.markdown(f"""
#### Limitations
- **Data vintage:** settlement, grid and road layers come from the 2016 World Bank/KTH model, and population is a
  2030 projection. The grid has grown since, so verify each site's grid status.
- **Screening economics:** LCOE ranges from **${rng['low']['lcoe']:.2f} to ${rng['high']['lcoe']:.2f}/kWh** across the
  low/high assumption sets (central ${rng['central']['lcoe']:.2f}).
- **Poverty index:** an LGA-level 0–1 index from the same tool. Its definition and year are undocumented, so it's
  off by default.
- **Not modelled:** willingness to pay, productive-use anchors, security, land, permitting.

[Full methodology & sources →]({REPO}/blob/master/docs/methodology.md)
""")
    st.markdown("#### Criteria definitions")
    st.dataframe(CRIT[["criterion", "column", "direction", "transform", "cap", "description", "rationale"]],
                 hide_index=True, width="stretch")
    st.markdown("#### Economic assumptions")
    st.dataframe(pd.read_csv(ROOT / "data" / "reference" / "economic_assumptions.csv"), hide_index=True, width="stretch")
