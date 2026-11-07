"""Solar mini-grid site suitability explorer (Nigeria).  Run: streamlit run app/streamlit_app.py

UI only - all calculations live in src/minigrid.
"""
import datetime as dt
import html
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
from minigrid.paths import GRID_EXISTING, GRID_PLANNED, STATES  # noqa: E402

# ----------------------------------------------------------------------------- design tokens
INK, INK2, INK3, BORDER, GRID, SURFACE = "#1a2735", "#566576", "#8796a8", "#cfdbe8", "#e6edf5", "#ffffff"
BLUE, ORANGE, AQUA, NAVY = "#2a78d6", "#eb6834", "#1baf7a", "#0f2b4c"
SKY, SUN = "#eef4fa", "#f4b400"
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # one-hue sequential
REPO = "https://github.com/Engr-Daniel/solar-minigrid-site-suitability-nigeria"
CRIT_LABEL = {"demand": "Demand (population)", "compactness": "Settlement compactness",
              "remoteness": "Distance from existing grid", "grid_risk": "Distance from future grid",
              "solar": "Solar resource", "access": "Road access", "need": "Poverty (need)"}
DIESEL = (0.35, 0.70)
DEFAULTS = {"pop_rng": (800, 10000), "min_grid": 5, "max_urban": 0.5, "states": [], "conservative": False,
            "n_top": 100}

st.set_page_config(page_title="Solar mini-grid siting, Nigeria", page_icon=str(Path(__file__).parent / "static" / "favicon.png"), layout="wide",
                   initial_sidebar_state="auto")
st.markdown(f"""
<style>
  .block-container {{padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px;}}
  h1, h2, h3, h4 {{font-family: "Bricolage Grotesque", sans-serif; letter-spacing: -0.02em;}}
  [data-testid="stSidebar"] .sb-h {{font-family:"Bricolage Grotesque"; font-size:1rem; font-weight:700; color:{NAVY};
      margin:22px 0 4px 0; padding-top:12px; border-top:1px solid {BORDER};}}
  .hero {{background:{SKY}; border-radius:10px; padding:30px 34px 26px; margin-bottom:22px;}}
  .hero h1 {{color:{NAVY}; font-size:clamp(1.7rem, 3.4vw, 2.8rem); font-stretch:88%; line-height:1.02; margin:0 0 12px;
            padding:0; font-weight:800; letter-spacing:-.02em; max-width:24ch;}}
  .hero p {{color:{INK2}; margin:0; font-size:1rem; max-width:78ch; line-height:1.55;}}
  .funnel {{display:flex; align-items:flex-start; gap:18px; margin-top:24px; flex-wrap:wrap;}}
  .funnel div b {{display:block; font-family:"Bricolage Grotesque"; font-size:2.1rem; font-weight:700; color:{NAVY};
                 letter-spacing:-.03em; line-height:1;}}
  .funnel div span {{font-size:.86rem; color:{INK2};}}
  .funnel div:last-of-type b {{color:#2f7d4a;}}
  .funnel i {{width:36px; height:2px; background:{SUN}; margin-top:18px; position:relative;}}
  .funnel i:after {{content:""; position:absolute; right:-1px; top:-5px; border:6px solid transparent; border-left:9px solid {SUN};}}
  .ctx {{font-size:.86rem; color:{INK2}; margin-top:18px;}} .ctx b {{color:{NAVY};}}
  .kpis {{display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:22px; margin-bottom:10px;}}
  .kpi {{border-top:3px solid {SUN}; padding:12px 0 6px; min-height:118px;}}
  .kpi .label {{font-size:0.88rem; color:{NAVY}; font-weight:600;}}
  .kpi .value {{font-family:"Bricolage Grotesque"; font-size:2rem; font-weight:700; color:{NAVY}; line-height:1.1;
               margin-top:6px; letter-spacing:-.02em; font-variant-numeric: tabular-nums;}}
  .kpi .unit {{font-family:"Instrument Sans"; font-size:0.9rem; font-weight:500; color:{INK2}; margin-left:3px; letter-spacing:0;}}
  .kpi .sub {{font-size:0.82rem; color:{INK2}; margin-top:4px; line-height:1.4;}}
  .headline {{font-family:"Bricolage Grotesque"; font-size:1.3rem; line-height:1.4; color:{NAVY}; font-weight:500;
             margin:8px 0 22px; max-width:72ch; letter-spacing:-.01em;}}
  .card {{background:#fff; border:1px solid {BORDER}; border-radius:10px; padding:18px 20px; height:100%;}}
  .card h4 {{margin:0 0 12px 0; padding:0; font-size:1.08rem; color:{NAVY};}}
  .card .muted {{color:{INK2}; font-size:0.88rem; line-height:1.5;}}
  .msg {{display:flex; gap:12px; align-items:flex-start; margin-bottom:14px;}}
  .msg .n {{flex:0 0 10px; width:10px; height:10px; border-radius:50%; background:{SUN}; font-size:0; margin-top:7px;}}
  .msg .t {{font-weight:700; font-size:0.95rem; color:{NAVY};}}
  .msg .b {{font-size:0.88rem; color:{INK2}; line-height:1.45;}}
  table.rank {{width:100%; border-collapse:collapse; font-size:0.85rem; font-variant-numeric: tabular-nums;}}
  table.rank th {{text-align:left; color:{INK2}; font-weight:600; font-size:0.8rem; padding:0 6px 6px 0; border-bottom:1px solid {BORDER};}}
  table.rank td {{padding:7px 6px 7px 0; border-bottom:1px solid {GRID}; color:{INK};}}
  table.rank td.r {{text-align:right;}} table.rank th.r {{text-align:right;}}
  .pill {{display:inline-flex; width:22px; height:22px; border-radius:50%; background:{NAVY}; color:#fff;
         font-weight:700; font-size:0.72rem; align-items:center; justify-content:center;}}
  .bar {{height:6px; background:{GRID}; border-radius:4px; width:64px; display:inline-block; vertical-align:middle;}}
  .bar > span {{display:block; height:6px; background:{BLUE}; border-radius:4px;}}
  .legend {{display:flex; flex-wrap:wrap; gap:18px; align-items:center; font-size:0.82rem; color:{INK2}; padding:10px 2px 0 2px;}}
  .legend .ramp span {{display:inline-block; width:20px; height:10px;}}
  .legend .ramp span:first-child {{border-radius:3px 0 0 3px;}} .legend .ramp span:last-child {{border-radius:0 3px 3px 0;}}
  .legend .dot {{display:inline-block; width:11px; height:11px; border-radius:50%; background:{ORANGE};
         border:1.5px solid #fff; box-shadow:0 0 0 1px {ORANGE}; vertical-align:-1px; margin-right:4px;}}
  .legend .ln {{display:inline-block; width:22px; height:0; border-top:2px solid {INK}; vertical-align:middle; margin-right:4px;}}
  .legend .ln.p {{border-top:2px dashed {INK3};}}
  .sec {{font-family:"Bricolage Grotesque"; font-size:1.4rem; font-weight:700; color:{NAVY}; margin:30px 0 2px 0; letter-spacing:-.015em;}}
  .sec-sub {{font-size:0.9rem; color:{INK2}; margin:0 0 14px 0;}}
  .foot {{margin-top:40px; padding:16px 0 0; border-top:1px solid {BORDER}; font-size:0.84rem; color:{INK2}; line-height:1.6;}}
  .foot a {{color:{NAVY};}}
  table.rank, table.rank tr, table.rank td, table.rank th {{border-left:none !important; border-right:none !important;
         border-top:none !important; background:transparent !important;}}
  table.rank td {{padding:6px 6px 6px 0 !important; border-bottom:1px solid {GRID} !important; line-height:1.25;}}
  table.rank th {{padding:0 6px 6px 0 !important; border-bottom:1px solid {BORDER} !important;}}
  .mobile-hint {{display:none;}}
  div[data-testid="stTabs"] [data-baseweb="tab-list"] {{gap:4px; border-bottom:1px solid {BORDER};}}
  div[data-testid="stTabs"] button {{padding:10px 14px;}}
  div[data-testid="stTabs"] button p {{font-size:0.98rem; font-weight:600;}}
  div[data-testid="stTabs"] button[aria-selected="true"] {{background:{SKY}; border-radius:8px 8px 0 0;}}
  @media (max-width: 768px) {{
    .block-container {{padding-left:0.8rem; padding-right:0.8rem; padding-top:3.2rem;}}
    .hero {{padding:20px 18px;}} .hero h1 {{font-size:1.6rem;}} .hero p {{font-size:0.9rem;}}
    .funnel {{gap:8px 22px;}} .funnel div b {{font-size:1.5rem;}} .funnel i {{display:none;}}
    .kpis {{grid-template-columns:repeat(2, 1fr); gap:14px;}} .kpi {{min-height:0;}} .kpi .value {{font-size:1.45rem;}}
    .kpi .sub {{font-size:0.76rem;}} .headline {{font-size:1.05rem;}} .legend {{gap:10px; font-size:0.76rem;}}
    .mobile-hint {{display:block; font-size:0.82rem; margin-top:12px; color:{INK2};}}
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {{overflow-x:auto; flex-wrap:nowrap;}}
    div[data-testid="stTabs"] button {{padding:8px 8px; white-space:nowrap;}} div[data-testid="stTabs"] button p {{font-size:0.86rem;}}
    .sec {{font-size:1.15rem;}}
  }}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- helpers
def kpi_row(items):
    """Responsive KPI grid: one row on desktop, two columns on phones."""
    st.markdown('<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}<span class="unit">{unit}</span>'
        f'</div><div class="sub">{sub}</div></div>' for label, value, unit, sub in items) + "</div>",
        unsafe_allow_html=True)


def section(title, sub=""):
    st.markdown(f'<div class="sec">{title}</div>' + (f'<div class="sec-sub">{sub}</div>' if sub else ""),
                unsafe_allow_html=True)


def hex_rgb(h, a=None):
    h = h.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return rgb + [a] if a is not None else rgb


RAMP_RGB = [hex_rgb(c, 200) for c in RAMP]  # plain Python ints (pydeck can't serialise numpy ints)


def colour_by_score(s: pd.Series):
    idx = (s.rank(pct=True).clip(0, 0.9999) * len(RAMP)).astype(int).tolist()
    return [RAMP_RGB[i] for i in idx]


def style(fig, title, sub=None, height=340, legend=False):
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>" + (f"<br><span style='font-size:12px;color:{INK2};font-weight:400'>{sub}</span>" if sub else ""),
                   x=0, xanchor="left", y=0.97, font=dict(family="Bricolage Grotesque, sans-serif", size=16, color=NAVY)),
        height=height, margin=dict(l=6, r=24, t=72 if sub else 48, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Instrument Sans, sans-serif", color=INK2, size=12),
        hoverlabel=dict(bgcolor="white", bordercolor=BORDER, font=dict(color=INK, size=12)),
        showlegend=legend, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title=None),
        barcornerradius=4)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=BORDER, tickfont=dict(color=INK2))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=BORDER, tickfont=dict(color=INK2))
    return fig


PLOT_CFG = {"displayModeBar": False}


def money(x):
    return f"${x/1e6:,.1f}M" if x >= 1e6 else f"${x/1e3:,.0f}k"


# ----------------------------------------------------------------------------- data
@st.cache_data
def data():
    return load_hexes(), load_weight_scenarios(), load_criteria(), load_assumptions()


@st.cache_data
def geo_layers():
    states = json.loads(STATES.read_text())
    for f in states["features"]:
        f["properties"] = {}
    return json.loads(GRID_EXISTING.read_text()), json.loads(GRID_PLANNED.read_text()), states


@st.cache_data(show_spinner="Scoring 190,000 hexagons…")
def run(weights_items: tuple, screen_items: tuple, states: tuple, conservative: bool, n_top: int):
    w, scr = dict(weights_items), Screen(**dict(screen_items))
    h = HEX if not states else HEX[HEX.state.isin(states)]
    cand = score(h, w, scr)
    if conservative:
        cand = cand[cand.onsset_tech_code.between(4, 7)]
        cand["rank"] = range(1, len(cand) + 1)
    cand["robust"] = robustness(cand, w, top_n=n_top, n_draws=600)
    top = site_economics(shortlist(cand, n_top), A).reset_index(drop=True)
    top.insert(0, "priority", range(1, len(top) + 1))
    return cand, top


HEX, W, CRIT, A = data()
try:
    MOBILE = any(t in (st.context.headers.get("User-Agent") or "") for t in ("Mobi", "Android", "iPhone"))
except Exception:  # noqa: BLE001 - headers unavailable (e.g. tests)
    MOBILE = False
EXIST, PLAN, STATE_GEO = geo_layers()

# ----------------------------------------------------------------------------- sidebar controls
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    for k in [k for k in st.session_state if k.startswith("w_")]:
        del st.session_state[k]


with st.sidebar:
    st.markdown("### Scenario controls")
    st.caption("Change the priorities and screen; every view updates.")
    st.markdown('<div class="sb-h">Priorities</div>', unsafe_allow_html=True)
    scen = st.selectbox("Weighting scenario", list(W.index), help="Preset stakeholder lenses. Fine-tune below.")
    base_w = W.loc[scen].drop("description").astype(float)
    st.caption(W.loc[scen, "description"])
    with st.expander("Fine-tune criterion weights"):
        weights = {k: st.slider(CRIT_LABEL[k], 0.0, 0.5, float(v), 0.05, key=f"w_{scen}_{k}") for k, v in base_w.items()}
        st.caption("Weights are re-normalised to sum to 100%.")
    if sum(weights.values()) == 0:
        st.error("Set at least one weight above zero.")
        st.stop()
    st.markdown('<div class="sb-h">Eligibility screen</div>', unsafe_allow_html=True)
    pop_rng = st.slider("Population per site (2030)", 200, 30000, step=100, key="pop_rng")
    min_grid = st.slider("Min. distance to existing grid (km)", 0, 50, key="min_grid")
    max_urban = st.slider("Max. urban share", 0.0, 1.0, step=0.1, key="max_urban")
    states = st.multiselect("Focus states", sorted(HEX.state.dropna().unique()), key="states",
                            placeholder="All 37 states")
    conservative = st.toggle("Conservative mode", key="conservative",
                             help="Only keep sites where the 2016 World Bank/KTH OnSSET model also chose a mini-grid.")
    st.markdown('<div class="sb-h">Portfolio</div>', unsafe_allow_html=True)
    n_top = st.select_slider("Shortlist size", [25, 50, 100, 200], key="n_top")
    st.button("Reset to defaults", on_click=reset, width="stretch")
    st.divider()
    st.link_button("Code and methodology", REPO, width="stretch")
    st.caption("Daniel Oyewale")

screen_items = tuple(sorted({"min_pop": pop_rng[0], "max_pop": pop_rng[1], "min_grid_km": float(min_grid),
                             "max_urban_share": float(max_urban)}.items()))
try:
    cand, top = run(tuple(sorted(weights.items())), screen_items, tuple(states), conservative, n_top)
except ValueError as e:
    st.warning(f"{e} Relax the eligibility screen.")
    st.stop()
if top.empty:
    st.warning("No sites pass the current screen. Relax the filters in the sidebar.")
    st.stop()
summ = portfolio_summary(top)
rng = lcoe_range(top, A)
top_states = top.state.value_counts()
lead3 = top_states.index[:3].tolist()
lead_share = top_states.iloc[:3].sum() / len(top)
saving = 1 - summ["median_lcoe"] / DIESEL[0]
robust_share = (top.robust >= 0.8).mean()

# ----------------------------------------------------------------------------- hero
scope = ", ".join(states) if states else "All 37 states"
st.markdown(f"""<div class="hero">
  <h1>Where should Nigeria build its next solar mini-grids?</h1>
  <p>Every populated area in Nigeria, about 5 km² each, is screened and ranked for a village-scale solar mini-grid on
     population, distance from the grid, road access and sunshine. The shortlist gets an estimated cost, tariff and
     carbon saving.</p>
  <div class="funnel"><div><b>{len(HEX):,}</b><span>populated areas</span></div><i></i>
    <div><b>{len(cand):,}</b><span>pass the screen</span></div><i></i>
    <div><b>{len(top)}</b><span>shortlisted sites</span></div></div>
  <div class="ctx">Showing <b>{html.escape(scen)}</b> priorities{', conservative mode' if conservative else ''}, {html.escape(scope)}.
     Screening analysis on 2016 settlement data with 2030 population.</div>
  <div class="mobile-hint">Open the menu at the top left to change priorities and filters.</div>
</div>""", unsafe_allow_html=True)

t_exec, t_inv, t_sites, t_rob, t_meth = st.tabs(
    ["Executive summary", "Investment case", "Site explorer", "Robustness & benchmark", "Method & data"])

# ============================================================================= EXECUTIVE SUMMARY
with t_exec:
    st.markdown(
        f'<div class="headline">The top <b>{len(top)}</b> sites would bring electricity to <b>~{summ["people"]/1e3:,.0f}k '
        f'people</b> with <b>{summ["pv_mwp"]:,.1f} MWp</b> of solar for about <b>${summ["capex_musd"]:,.0f}M</b>, at '
        f'<b>${summ["median_lcoe"]:.2f}/kWh</b>'
        + (f', roughly <b>{saving:.0%} below</b> the cheapest diesel generation' if saving > 0 else '')
        + f'. <b>{", ".join(lead3)}</b> account for {lead_share:.0%} of the shortlist.</div>',
        unsafe_allow_html=True)
    kpi_row([
        ("People served", f"{summ['people']/1e3:,.0f}", "k", f"~{summ['connections']:,.0f} household connections"),
        ("Solar capacity", f"{summ['pv_mwp']:,.1f}", " MWp", f"across {len(top)} mini-grids"),
        ("Investment", f"${summ['capex_musd']:,.0f}", "M",
         f"${summ['capex_musd']*1e6/summ['connections']:,.0f} per connection"),
        ("Cost of power", f"${summ['median_lcoe']:.2f}", "/kWh",
         f"${summ['median_lcoe_grant']:.2f} with grant · diesel ${DIESEL[0]:.2f}–{DIESEL[1]:.2f}"),
        ("CO₂ avoided", f"{summ['co2_avoided_kt_yr']:,.1f}", " kt/yr", "vs diesel generators")])
    st.write("")

    m, r = st.columns([1.75, 1], gap="medium")
    with m:
        view_df = cand[["h3", "score", "pop_2030", "grid_km", "state", "lga"]].copy()
        view_df["color"] = colour_by_score(view_df.score)
        view_df["tt_title"] = view_df.state + " · " + view_df.lga
        view_df["tt_body"] = ("Suitability " + view_df.score.round(0).astype(int).astype(str) + "/100 · "
                              + view_df.pop_2030.round(-2).astype(int).map("{:,}".format) + " people · "
                              + view_df.grid_km.round(0).astype(int).astype(str) + " km to grid")
        tops = top[["lon", "lat", "priority", "state", "lga", "pop_2030", "pv_kwp", "lcoe_usd_kwh", "grid_km"]].copy()
        tops["tt_title"] = "Priority #" + tops.priority.astype(str) + " · " + tops.state + ", " + tops.lga
        tops["tt_body"] = (tops.pop_2030.round(-2).astype(int).map("{:,}".format) + " people · "
                           + tops.pv_kwp.round(0).astype(int).map("{:,}".format) + " kWp · $"
                           + tops.lcoe_usd_kwh.round(2).astype(str) + "/kWh")
        tops["radius"] = (tops.pop_2030 ** 0.5 * 40).astype(float)
        top10 = tops[tops.priority <= 10]
        layers = [
            pdk.Layer("GeoJsonLayer", STATE_GEO, stroked=True, filled=False, get_line_color=[160, 158, 152, 160],
                      line_width_min_pixels=0.6),
            pdk.Layer("H3HexagonLayer", view_df, get_hexagon="h3", get_fill_color="color", stroked=False,
                      extruded=False, pickable=True),
            pdk.Layer("GeoJsonLayer", EXIST, get_line_color=[11, 11, 11, 220], line_width_min_pixels=1.6),
            pdk.Layer("GeoJsonLayer", PLAN, get_line_color=[120, 119, 115, 200], line_width_min_pixels=1.2),
            pdk.Layer("ScatterplotLayer", tops, get_position=["lon", "lat"], get_fill_color=hex_rgb(ORANGE, 235),
                      get_line_color=[255, 255, 255], line_width_min_pixels=1.5, stroked=True, get_radius="radius",
                      radius_min_pixels=4, radius_max_pixels=11, pickable=True),
            pdk.Layer("ScatterplotLayer", top10, get_position=["lon", "lat"], get_fill_color=hex_rgb(ORANGE, 255),
                      get_line_color=hex_rgb(NAVY), line_width_min_pixels=2.5, stroked=True, get_radius=6000,
                      radius_min_pixels=8, radius_max_pixels=13, pickable=True),
        ]
        tooltip = {"html": "<div style='font-weight:700;margin-bottom:2px'>{tt_title}</div><div>{tt_body}</div>",
                   "style": {"backgroundColor": "white", "color": INK, "fontSize": "12px", "padding": "8px 10px",
                             "border": f"1px solid {BORDER}", "borderRadius": "8px",
                             "boxShadow": "0 4px 12px rgba(0,0,0,0.08)"}}
        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=9.0, longitude=8.4, zoom=4.3 if MOBILE else 5.15),
                                 map_style="light", tooltip=tooltip), height=400 if MOBILE else 560)
        st.markdown(
            f'<div class="legend"><span>Suitability (percentile of eligible areas)</span>'
            f'<span class="ramp">low&nbsp;{"".join(f"<span style=background:{c}></span>" for c in RAMP)}&nbsp;high</span>'
            f'<span><span class="dot"></span>Shortlisted site (size = population; navy ring = top 10)</span>'
            f'<span><span class="ln"></span>Existing grid</span><span><span class="ln p"></span>Planned grid</span></div>',
            unsafe_allow_html=True)
    with r:
        rows = "".join(
            f"<tr><td><span class='pill'>{t.priority}</span></td><td><b>{html.escape(t.lga)}</b><br>"
            f"<span style='color:{INK3};font-size:0.76rem'>{html.escape(t.state)}</span></td>"
            f"<td class='r'>{t.pop_2030/1e3:,.1f}k</td><td class='r'>{t.grid_km:,.0f}</td>"
            f"<td class='r'><span class='bar'><span style='width:{t.score:.0f}%'></span></span></td></tr>"
            for t in top.head(10).itertuples())
        st.markdown(f"""<div class="card"><h4>Top 10 priority sites</h4>
            <table class="rank"><tr><th>#</th><th>LGA</th><th class="r">People</th><th class="r">km to grid</th>
            <th class="r">Score</th></tr>{rows}</table>
            <div class="muted" style="margin-top:10px">Full ranked list, economics and download in <b>Site explorer</b>.</div>
            </div>""", unsafe_allow_html=True)

    section("What this means for decision-makers")
    a, b = st.columns(2, gap="medium")
    msgs = [
        ("The opportunity is concentrated in the north",
         f"{', '.join(lead3)} hold {lead_share:.0%} of the shortlist: compact villages a median "
         f"{top.grid_km.median():,.0f} km from the grid, under Nigeria's strongest sun "
         f"(~{top.ghi.median():,.0f} kWh/m²/yr)."),
        ("Solar mini-grids out-compete diesel",
         f"Central cost of ${summ['median_lcoe']:.2f}/kWh (range ${rng['low']['lcoe']:.2f}–{rng['high']['lcoe']:.2f}) "
         f"against ${DIESEL[0]:.2f}–{DIESEL[1]:.2f} for diesel generation. A $350/connection grant brings it to "
         f"${summ['median_lcoe_grant']:.2f}."),
        ("The ranking is robust",
         f"{robust_share:.0%} of shortlisted sites stay in the top {len(top)} in at least 80% of 600 alternative weightings, "
         "so the priority list doesn't hinge on one set of assumptions."),
    ]
    steps = [
        ("Verify the top 25 on the ground", "Confirm current grid status (the layers date from 2016), settlement size "
         "and security before any developer engagement."),
        ("Run demand and willingness-to-pay surveys", "Identify anchor loads (agro-processing, health centres, schools) "
         "that improve the business case."),
        ("Package sites into tenders", "Cluster neighbouring sites in the lead states into investment-ready lots for "
         "REA / NEP performance-based grants."),
    ]
    with a:
        st.markdown('<div class="card"><h4>Key findings</h4>' + "".join(
            f'<div class="msg"><div class="n">{i}</div><div><div class="t">{t}</div><div class="b">{bdy}</div></div></div>'
            for i, (t, bdy) in enumerate(msgs, 1)) + "</div>", unsafe_allow_html=True)
    with b:
        st.markdown('<div class="card"><h4>Recommended next steps</h4>' + "".join(
            f'<div class="msg"><div class="n" style="background:{ORANGE}">{i}</div><div><div class="t">{t}</div>'
            f'<div class="b">{bdy}</div></div></div>' for i, (t, bdy) in enumerate(steps, 1)) + "</div>",
            unsafe_allow_html=True)

# ============================================================================= INVESTMENT CASE
with t_inv:
    section("Investment case", "Indicative, screening-level economics for the shortlisted portfolio. Not a feasibility study.")
    a, b = st.columns(2, gap="large")
    with a:
        cats = ["Diesel generator", "Solar mini-grid", "Solar mini-grid + $350 grant"]
        lows = [DIESEL[0], rng["low"]["lcoe"], rng["low"]["lcoe_grant"]]
        highs = [DIESEL[1], rng["high"]["lcoe"], rng["high"]["lcoe_grant"]]
        mids = [None, rng["central"]["lcoe"], rng["central"]["lcoe_grant"]]
        cols = [INK3, BLUE, AQUA]
        fig = go.Figure()
        for cat, lo, hi, mid, col in zip(cats, lows, highs, mids, cols):
            fig.add_trace(go.Scatter(x=[lo, hi], y=[cat, cat], mode="lines", line=dict(color=col, width=12),
                                     hovertemplate=f"{cat}: ${lo:.2f}–{hi:.2f}/kWh<extra></extra>"))
            if mid:
                fig.add_trace(go.Scatter(x=[mid], y=[cat], mode="markers+text", text=[f"${mid:.2f}"],
                                         textposition="top center", textfont=dict(color=INK, size=12),
                                         marker=dict(size=14, color="white", line=dict(color=col, width=3)),
                                         hovertemplate=f"Central: ${mid:.2f}/kWh<extra></extra>"))
        style(fig, "Cost of electricity: solar mini-grid vs diesel", "US$/kWh · bars = low–high range, dot = central case",
              height=330)
        fig.update_xaxes(tickprefix="$", tickformat=".2f", range=[0, max(highs) * 1.08])
        fig.update_yaxes(categoryorder="array", categoryarray=cats[::-1], gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with b:
        t2 = top.sort_values("priority")
        cum_capex, cum_people = t2.capex_usd.cumsum() / 1e6, t2.pop_2030.cumsum() / 1e3
        fig = go.Figure(go.Scatter(x=cum_capex, y=cum_people, mode="lines", line=dict(color=BLUE, width=2.5),
                                   fill="tozeroy", fillcolor="rgba(42,120,214,0.08)", customdata=t2.priority,
                                   hovertemplate="First %{customdata} sites<br>$%{x:,.1f}M → %{y:,.0f}k people"
                                                 "<extra></extra>"))
        for k in [25, 50, 100]:
            if k < len(t2):
                fig.add_trace(go.Scatter(x=[cum_capex.iloc[k - 1]], y=[cum_people.iloc[k - 1]], mode="markers+text",
                                         marker=dict(size=9, color=ORANGE, line=dict(color="white", width=2)),
                                         text=[f"Top {k}"], textposition="top left", textfont=dict(color=INK, size=11),
                                         hoverinfo="skip"))
        style(fig, "People reached per dollar invested", "Cumulative, in priority order", height=330)
        fig.update_xaxes(title="Cumulative capex (US$ M)", tickprefix="$")
        fig.update_yaxes(title="People served (thousands)")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

    section("Phased roll-out", "Splitting the shortlist into delivery tranches by priority.")
    edges = [e for e in [0, 25, 50, 100, 200] if e < len(top)] + [len(top)]
    tr = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = top.iloc[lo:hi]
        p = portfolio_summary(s)
        tr.append({"Tranche": f"Phase {len(tr)+1}: priority {lo+1}–{hi}", "Sites": len(s), "People": p["people"],
                   "Connections": p["connections"], "Solar (MWp)": p["pv_mwp"], "Capex (US$ M)": p["capex_musd"],
                   "Median LCOE ($/kWh)": p["median_lcoe"], "CO₂ avoided (kt/yr)": p["co2_avoided_kt_yr"],
                   "Lead states": ", ".join(s.state.value_counts().index[:3])})
    st.dataframe(pd.DataFrame(tr), hide_index=True, width="stretch", column_config={
        "People": st.column_config.NumberColumn(format="%,.0f"),
        "Connections": st.column_config.NumberColumn(format="%,.0f"),
        "Solar (MWp)": st.column_config.NumberColumn(format="%.1f"),
        "Capex (US$ M)": st.column_config.NumberColumn(format="$%.1f"),
        "Median LCOE ($/kWh)": st.column_config.NumberColumn(format="$%.2f"),
        "CO₂ avoided (kt/yr)": st.column_config.NumberColumn(format="%.1f")})

    by_state = (top.groupby("state").agg(sites=("h3", "size"), people=("pop_2030", "sum"), capex=("capex_usd", "sum"))
                .sort_values("capex"))
    fig = go.Figure(go.Bar(y=by_state.index, x=by_state.capex / 1e6, orientation="h", marker_color=BLUE,
                           text=[f"${c/1e6:,.1f}M" if MOBILE else f"${c/1e6:,.1f}M · {n} sites · {p/1e3:,.0f}k people"
                                 for c, n, p in zip(by_state.capex, by_state.sites, by_state.people)],
                           customdata=list(zip(by_state.sites, by_state.people / 1e3)),
                           textposition="outside", cliponaxis=False, textfont=dict(color=INK2, size=11),
                           hovertemplate="%{y}: $%{x:,.1f}M · %{customdata[0]} sites · "
                                         "%{customdata[1]:,.0f}k people<extra></extra>"))
    style(fig, "Investment by state", "Indicative capex of shortlisted sites", height=max(280, 30 * len(by_state) + 90))
    fig.update_xaxes(tickprefix="$", ticksuffix="M", range=[0, by_state.capex.max() / 1e6 * (1.2 if MOBILE else 1.45)])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    st.caption("Assumptions: MTF Tier 3 (365 kWh/household/yr) + 30% productive use; 70% uptake; PV + battery "
               "\\$1,200/kWp; distribution \\$450/connection; 10% discount rate over 20 years; O&M 4% of capex/yr. "
               "Full table in **Method & data**.")

# ============================================================================= SITE EXPLORER
with t_sites:
    section(f"Ranked shortlist: {len(top)} sites",
            "No two sites are neighbouring hexagons. Select a row to open its profile below.")
    tbl = top.assign(robust=top.robust * 100)[["priority", "state", "lga", "pop_2030", "connections", "grid_km", "road_km", "ghi", "score", "robust",
               "pv_kwp", "capex_usd", "lcoe_usd_kwh", "co2_avoided_t_yr", "lat", "lon"]]
    ev = st.dataframe(tbl, hide_index=True, width="stretch", height=420, on_select="rerun",
                      selection_mode="single-row", key="site_tbl", column_config={
                          "priority": st.column_config.NumberColumn("#", width="small"), "state": "State", "lga": "LGA",
                          "pop_2030": st.column_config.NumberColumn("People 2030", format="%,d"),
                          "connections": st.column_config.NumberColumn("Connections", format="%,d"),
                          "grid_km": st.column_config.NumberColumn("Grid km", format="%.0f"),
                          "road_km": st.column_config.NumberColumn("Road km", format="%.1f"),
                          "ghi": st.column_config.NumberColumn("GHI", format="%,.0f", help="kWh/m²/yr"),
                          "score": st.column_config.ProgressColumn("Score", format="%.0f", min_value=0, max_value=100),
                          "robust": st.column_config.ProgressColumn("Robustness", format="%.0f%%", min_value=0,
                                                                    max_value=100, help="Share of 600 weight sets keeping "
                                                                                      "the site in the shortlist"),
                          "pv_kwp": st.column_config.NumberColumn("PV kWp", format="%,.0f"),
                          "capex_usd": st.column_config.NumberColumn("Capex", format="$%,.0f"),
                          "lcoe_usd_kwh": st.column_config.NumberColumn("LCOE", format="$%.2f"),
                          "co2_avoided_t_yr": st.column_config.NumberColumn("CO₂ t/yr", format="%,.0f"),
                          "lat": st.column_config.NumberColumn("Lat", format="%.4f"),
                          "lon": st.column_config.NumberColumn("Lon", format="%.4f")})
    sel = getattr(getattr(ev, "selection", None), "rows", None) or [0]
    s = top.iloc[sel[0]]

    section(f"Site profile: #{int(s.priority)} {s.lga}, {s.state}")
    kpi_row([
        ("Suitability", f"{s.score:.0f}", "/100", f"robust in {s.robust:.0%} of weightings"),
        ("People 2030", f"{s.pop_2030:,.0f}", "", f"~{s.connections:,.0f} connections"),
        ("System", f"{s.pv_kwp:,.0f}", " kWp", f"capex ≈ {money(s.capex_usd)} (${s.capex_per_connection:,.0f}/conn.)"),
        ("Cost of power", f"${s.lcoe_usd_kwh:.2f}", "/kWh",
         f"${s.lcoe_with_grant_usd_kwh:.2f} with grant · {s.co2_avoided_t_yr:,.0f} t CO₂/yr avoided")])
    st.write("")
    a, b, d = st.columns([1.15, 1, 1], gap="medium")
    with a:
        crit = [k for k in CRIT_LABEL if f"n_{k}" in s.index and weights.get(k, 0) > 0]
        vals = [float(s[f"n_{k}"]) for k in crit]
        fig = go.Figure(go.Bar(y=[CRIT_LABEL[k] for k in crit][::-1], x=vals[::-1], orientation="h", marker_color=BLUE,
                               text=[f"{v:.2f}" for v in vals[::-1]], textposition="outside", cliponaxis=False,
                               textfont=dict(color=INK2), hovertemplate="%{y}: %{x:.2f}<extra></extra>"))
        style(fig, "Why this site scores well", "Criterion scores, 0 = worst, 1 = best among eligible areas", height=330)
        fig.update_xaxes(range=[0, 1.15])
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with b:
        st.markdown(f"""<div class="card"><h4>Site facts</h4><table class="rank">
          <tr><td>Distance to existing grid</td><td class="r"><b>{s.grid_km:,.0f} km</b></td></tr>
          <tr><td>Distance to future grid</td><td class="r"><b>{s.planned_km:,.0f} km</b></td></tr>
          <tr><td>Distance to road</td><td class="r"><b>{s.road_km:,.1f} km</b></td></tr>
          <tr><td>Solar resource (GHI)</td><td class="r"><b>{s.ghi:,.0f}</b> kWh/m²/yr</td></tr>
          <tr><td>Specific yield</td><td class="r"><b>{s.yield_kwh_per_kwp:,.0f}</b> kWh/kWp/yr</td></tr>
          <tr><td>Densest 1 km² cell</td><td class="r"><b>{s.peak_density:,.0f}</b> people</td></tr>
          <tr><td>Annual demand</td><td class="r"><b>{s.demand_mwh_yr:,.0f}</b> MWh</td></tr>
          <tr><td>OnSSET-2016 choice</td><td class="r">{html.escape(str(s.onsset_tech))}</td></tr>
          <tr><td>Coordinates</td><td class="r">{s.lat:.4f}, {s.lon:.4f}</td></tr></table>
          <div class="muted" style="margin-top:8px">Verify grid status, demand and access on site.</div></div>""",
                    unsafe_allow_html=True)
    with d:
        near = cand[(cand.lat.sub(s.lat).abs() < 0.35) & (cand.lon.sub(s.lon).abs() < 0.35)][["h3", "score"]].copy()
        near["color"] = [c[:3] + [150] for c in colour_by_score(near.score)] if len(near) else []
        site = pd.DataFrame({"lon": [float(s.lon)], "lat": [float(s.lat)]})
        st.pydeck_chart(pdk.Deck(layers=[
            pdk.Layer("H3HexagonLayer", near, get_hexagon="h3", get_fill_color="color", stroked=False),
            pdk.Layer("GeoJsonLayer", EXIST, get_line_color=[11, 11, 11], line_width_min_pixels=1.5),
            pdk.Layer("ScatterplotLayer", site, get_position=["lon", "lat"], get_fill_color=hex_rgb(ORANGE, 255),
                      get_line_color=hex_rgb(NAVY), line_width_min_pixels=3, stroked=True, get_radius=1500,
                      radius_min_pixels=11)],
            initial_view_state=pdk.ViewState(latitude=float(s.lat), longitude=float(s.lon), zoom=8.6),
            map_style="light"), height=330)
        st.caption("Site (orange) and surrounding eligible areas, shaded by suitability.")

    st.download_button("⬇ Download shortlist (CSV)", top.to_csv(index=False).encode(), "minigrid_shortlist.csv",
                       "text/csv")

# ============================================================================= ROBUSTNESS & BENCHMARK
with t_rob:
    section("How much can stakeholders trust the ranking?")
    a, b = st.columns(2, gap="large")
    with a:
        fig = go.Figure(go.Histogram(x=top.robust, xbins=dict(start=0, end=1.0001, size=0.05), marker_color=BLUE,
                                     marker_line=dict(color="white", width=2),
                                     hovertemplate="%{x}: %{y} sites<extra></extra>"))
        fig.add_vline(x=0.8, line=dict(color=ORANGE, dash="dash", width=1.5))
        fig.add_annotation(x=0.8, y=1, yref="paper", text=f"{robust_share:.0%} of sites ≥ 80%", showarrow=False,
                           xanchor="right", xshift=-6, font=dict(color=INK, size=12))
        style(fig, "Weight-robustness of the shortlist",
              f"Share of 600 random weightings (Dirichlet) keeping each site in the top {len(top)}", height=340)
        fig.update_xaxes(tickformat=".0%", title="Top-N frequency", range=[0, 1.02])
        fig.update_yaxes(title="Sites")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with b:
        ov = []
        for name in W.index:
            w2 = W.loc[name].drop("description").astype(float).to_dict()
            if name == scen and dict(weights) == w2:
                continue
            c2, t2 = run(tuple(sorted(w2.items())), screen_items, tuple(states), conservative, n_top)
            ov.append({"Compared with": name, "Shared sites": len(set(t2.h3) & set(top.h3)),
                       "Share": len(set(t2.h3) & set(top.h3)) / len(top)})
        st.markdown('<div class="card"><h4>Do other stakeholder lenses agree?</h4>' + "".join(
            f'<div style="margin:10px 0 4px 0;font-size:0.88rem"><b>{html.escape(o["Compared with"])}</b> '
            f'<span style="float:right">{o["Shared sites"]} of {len(top)} sites</span></div>'
            f'<div class="bar" style="width:100%;height:10px"><span style="width:{o["Share"]*100:.0f}%;height:10px">'
            f'</span></div>' for o in ov)
            + '<div class="muted" style="margin-top:14px">Overlap between this shortlist and the shortlist under each '
              'alternative preset weighting, with the same screen.</div></div>', unsafe_allow_html=True)

    section("Benchmark against the World Bank/KTH OnSSET 2016 model")
    a, b = st.columns([1.1, 1], gap="large")
    ag = agreement_with_onsset(cand, top)
    a.dataframe(ag.rename(columns={"sites": "Sites", "onsset_minigrid_share": "OnSSET chose a mini-grid",
                                   "onsset_minigrid_pop_share": "Pop. share"}),
                width="stretch", column_config={"OnSSET chose a mini-grid": st.column_config.NumberColumn("OnSSET: mini-grid", format="percent"),
                                                "Pop. share": st.column_config.NumberColumn(format="percent"),
                                                "Sites": st.column_config.NumberColumn(format="%,d")})
    b.markdown("""
**Why the shortlist disagrees with OnSSET-2016, and why that's expected**
- The 2016 run used **2016 solar and battery costs**. It chose solar mini-grids for only ~0.1% of Nigeria's population,
  and its "mini-grids" were almost all **diesel**, in small, sparse villages.
- For larger, compact settlements it assumed **grid extension** would arrive.
- With current costs, SEforALL's **2022 Nigeria Integrated Energy Plan** finds mini-grids least-cost predominantly in
  **denser settlements further from the grid**. That's the profile this shortlist targets.
- Switch on **Conservative mode** in the sidebar to see only sites both models agree on.
""")

# ============================================================================= METHOD & DATA
with t_meth:
    a, b = st.columns(2, gap="large")
    a.markdown("""
#### How the ranking works
1. **Units:** 934,595 OnSSET 1 km² settlement cells, aggregated to **H3 resolution-7 hexagons** (~5 km², about the
   area a village mini-grid serves).
2. **Eligibility screen:** population band, mostly rural, minimum distance to the existing grid, valid solar data.
3. **Criteria**, normalised 0–1 within the eligible set: demand (log, saturating at 4,000 people), compactness,
   distance to existing grid (capped at 50 km), distance to future grid (capped at 30 km), solar GHI, road access
   (capped at 20 km), and optional LGA poverty.
4. **Weighted linear combination** → score 0–100, under three preset stakeholder lenses or custom weights.
5. **Robustness:** 600 random weightings around the chosen weights. **Shortlist:** greedy by rank, no neighbouring hexagons.
6. **Economics:** households × 70% uptake × MTF Tier 3 (365 kWh) + 30% productive use; PV sized from GHI;
   capex = PV + battery \\$1,200/kWp + distribution \\$450/connection; 10% discount rate over 20 years.
""")
    b.markdown(f"""
#### Limitations
- **Data vintage:** settlement, grid and road layers come from the 2016 World Bank/KTH model, and population is a
  2030 projection. The grid has grown since, so verify each site.
- **Screening economics:** LCOE ranges from **\\${rng['low']['lcoe']:.2f} to \\${rng['high']['lcoe']:.2f}/kWh** across the
  low/high assumption sets (central \\${rng['central']['lcoe']:.2f}). No hourly dispatch or battery replacement.
- **Poverty index:** an LGA-level 0–1 index of undocumented definition, so it's off by default.
- **Not modelled:** willingness to pay, anchor loads, security, land, permitting, existing mini-grids.

[Full methodology & sources →]({REPO}/blob/master/docs/methodology.md)
""")
    with st.expander("Criteria definitions"):
        st.dataframe(CRIT[["criterion", "column", "direction", "transform", "cap", "description", "rationale"]],
                     hide_index=True, width="stretch")
    with st.expander("Economic assumptions & sources"):
        st.dataframe(pd.read_csv(ROOT / "data" / "reference" / "economic_assumptions.csv"), hide_index=True,
                     width="stretch")

# ----------------------------------------------------------------------------- briefing note + footer
def briefing_html() -> str:
    rows = "".join(f"<tr><td>{t.priority}</td><td>{html.escape(t.state)}</td><td>{html.escape(t.lga)}</td>"
                   f"<td>{t.pop_2030:,.0f}</td><td>{t.grid_km:,.0f}</td><td>{t.pv_kwp:,.0f}</td>"
                   f"<td>{money(t.capex_usd)}</td><td>${t.lcoe_usd_kwh:.2f}</td></tr>" for t in top.head(25).itertuples())
    li = "".join(f"<li><b>{t}.</b> {b}</li>" for t, b in msgs)
    nx = "".join(f"<li><b>{t}.</b> {b}</li>" for t, b in steps)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Solar mini-grid siting brief: Nigeria</title>
<style>body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#0b0b0b;max-width:900px;margin:32px auto;
padding:0 24px;line-height:1.5}} h1{{color:{NAVY};margin-bottom:4px}} .sub{{color:#52514e}}
.k{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:20px 0}} .k div{{border:1px solid #e7e5e0;
border-radius:10px;padding:10px}} .k b{{display:block;font-size:20px}} .k span{{font-size:11px;color:#52514e;
text-transform:uppercase}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid
#e7e5e0;padding:6px;text-align:left}} th{{color:#52514e}} .note{{font-size:12px;color:#52514e;border-top:1px solid
#e7e5e0;margin-top:24px;padding-top:10px}} @media print{{body{{margin:0}}}}</style></head><body>
<h1>Solar mini-grid site prioritisation: Nigeria</h1>
<div class="sub">Briefing note · scenario <b>{html.escape(scen)}</b>{' (conservative)' if conservative else ''} ·
{html.escape(scope)} · generated {dt.date.today():%d %B %Y}</div>
<div class="k"><div><span>People served</span><b>{summ['people']/1e3:,.0f}k</b></div>
<div><span>Solar capacity</span><b>{summ['pv_mwp']:,.1f} MWp</b></div><div><span>Investment</span>
<b>${summ['capex_musd']:,.0f}M</b></div><div><span>Cost of power</span><b>${summ['median_lcoe']:.2f}/kWh</b></div>
<div><span>CO₂ avoided</span><b>{summ['co2_avoided_kt_yr']:,.1f} kt/yr</b></div></div>
<h3>Key findings</h3><ul>{li}</ul><h3>Recommended next steps</h3><ul>{nx}</ul>
<h3>Top 25 priority sites</h3><table><tr><th>#</th><th>State</th><th>LGA</th><th>People 2030</th><th>km to grid</th>
<th>PV kWp</th><th>Capex</th><th>LCOE</th></tr>{rows}</table>
<div class="note">Screening analysis. Settlement, grid and road data: World Bank ESMAP / KTH-dESA OnSSET Nigeria layer (2016),
population projected to 2030. Economics are indicative. Shortlisted sites require field verification.
Method and code: {REPO}. Prepared by Daniel Oyewale.</div></body></html>"""


with st.sidebar:
    st.download_button("⬇ Briefing note (HTML, print to PDF)", briefing_html().encode(), "minigrid_briefing_note.html",
                       "text/html", width="stretch")

st.markdown(f"""<div class="foot">Screening analysis for prioritisation, not a substitute for site feasibility
studies. Sources are listed under Method &amp; data. <a href="{REPO}">Source code</a></div>""", unsafe_allow_html=True)
