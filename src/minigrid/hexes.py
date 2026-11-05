"""Aggregate 1x1 km OnSSET cells into H3 hexagons (candidate mini-grid service areas).

H3 resolution 7 averages ~5.2 km2 (edge ~1.4 km), close to the footprint a single village
mini-grid distribution network serves. Each hexagon carries:
  pop_2030      projected population (sum of cells)
  cells         number of populated 1 km cells
  urban_share   share of cells flagged urban by OnSSET
  grid_km       distance from the hexagon's closest cell to the EXISTING grid (min)
  planned_km    distance to the PLANNED grid (min)
  road_km       distance to the nearest road (min)
  ghi           global horizontal irradiation, kWh/m2/yr (population-weighted mean; zeros = no data)
  peak_density  population of the densest cell (people/km2) - proxy for a compact village core
  onsset_tech   least-cost technology chosen by OnSSET for Tier 3 demand, low diesel price (pop-weighted mode)
  poverty_index LGA poverty index (0-1) from the World Bank/KTH tool
  state, lga    geoBoundaries ADM1 / ADM2 names
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from minigrid.paths import HEXES, INTERIM, RAW, STATES  # noqa: E402

H3_RES = 7
TECH = {1: "Grid", 2: "Stand-alone diesel", 3: "Stand-alone PV", 4: "Mini-grid diesel",
        5: "Mini-grid PV", 6: "Mini-grid wind", 7: "Mini-grid hydro"}


def _weighted_mode(values: pd.Series, weights: pd.Series):
    return weights.groupby(values).sum().idxmax()


def aggregate(cells: pd.DataFrame, res: int = H3_RES) -> pd.DataFrame:
    c = cells.copy()
    c["h3"] = [h3.latlng_to_cell(y, x, res) for x, y in zip(c.x.values, c.y.values)]
    c["ghi_w"] = np.where(c.ghi > 0, c.ghi * c.p_2030, np.nan)
    c["w_valid"] = np.where(c.ghi > 0, c.p_2030, np.nan)
    g = c.groupby("h3").agg(
        pop_2030=("p_2030", "sum"), new_connections=("nc", "sum"), cells=("p_2030", "size"),
        urban_share=("u", "mean"), grid_km=("gd_c", "min"), planned_km=("gd_p", "min"), road_km=("rd", "min"),
        ghi_w=("ghi_w", "sum"), w_valid=("w_valid", "sum"), ghi_max=("ghi", "max"), peak_density=("p_2030", "max"),
        adm1=("adm1", lambda s: s.mode().iat[0]), adm2=("adm2", lambda s: s.mode().iat[0]),
    )
    g["ghi"] = np.where(g.w_valid > 0, g.ghi_w / g.w_valid, np.where(g.ghi_max > 0, g.ghi_max, np.nan))
    tech = c[c.p_2030 > 0].groupby("h3").apply(lambda d: _weighted_mode(d.l3, d.p_2030), include_groups=False)
    g["onsset_tech_code"] = tech.reindex(g.index).fillna(0).astype(int)
    g["onsset_tech"] = g.onsset_tech_code.map(TECH).fillna("n/a")
    g = g.drop(columns=["ghi_w", "w_valid", "ghi_max"]).reset_index()
    latlng = [h3.cell_to_latlng(h) for h in g.h3]
    g["lat"] = [p[0] for p in latlng]
    g["lon"] = [p[1] for p in latlng]
    return g


def add_admin(hexes: pd.DataFrame, adm1_path: Path, adm2_path: Path) -> pd.DataFrame:
    pts = gpd.GeoDataFrame(hexes, geometry=gpd.points_from_xy(hexes.lon, hexes.lat), crs="EPSG:4326")
    a1 = gpd.read_file(adm1_path)[["shapeName", "geometry"]].rename(columns={"shapeName": "state"})
    a2 = gpd.read_file(adm2_path)[["shapeName", "geometry"]].rename(columns={"shapeName": "lga"})
    out = gpd.sjoin(pts, a1, how="left", predicate="within").drop(columns="index_right")
    out = gpd.sjoin(out, a2, how="left", predicate="within").drop(columns="index_right")
    # border hexes whose centroid falls just outside a polygon: use nearest
    for col, layer in (("state", a1), ("lga", a2)):
        miss = out[col].isna()
        if miss.any():
            near = gpd.sjoin_nearest(out.loc[miss, ["geometry"]].to_crs(32632), layer.to_crs(32632), how="left")
            out.loc[miss, col] = near.groupby(level=0)[col].first()
    return pd.DataFrame(out.drop(columns="geometry"))


def main():
    cells = pd.read_parquet(INTERIM / "nga_cells.parquet")
    hexes = aggregate(cells)
    pov = pd.read_csv(INTERIM / "nga_poverty.csv")
    hexes = hexes.merge(pov, on=["adm1", "adm2"], how="left")
    hexes = add_admin(hexes, RAW / "geoBoundaries-NGA-ADM1_simplified.geojson",
                      RAW / "geoBoundaries-NGA-ADM2_simplified.geojson")
    hexes = hexes[hexes.pop_2030 > 0].reset_index(drop=True)
    for col in ("grid_km", "planned_km", "road_km", "ghi", "urban_share", "poverty_index", "lat", "lon"):
        hexes[col] = hexes[col].astype("float32")
    hexes.to_parquet(HEXES, index=False)
    states = gpd.read_file(RAW / "geoBoundaries-NGA-ADM1_simplified.geojson")[["shapeName", "geometry"]]
    states.rename(columns={"shapeName": "state"}).to_file(STATES, driver="GeoJSON")
    print(f"hexes: {len(hexes):,} | pop {hexes.pop_2030.sum()/1e6:,.1f} M | states {hexes.state.nunique()} "
          f"| LGAs {hexes.lga.nunique()} | missing GHI {hexes.ghi.isna().sum()} | file {HEXES.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
