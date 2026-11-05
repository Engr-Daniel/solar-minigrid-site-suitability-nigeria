"""Reproducible data ingest.

Sources (all open):
  1. World Bank ESMAP / KTH-dESA "Electrification pathways for Nigeria, Tanzania and Zambia"
     (github.com/energy-data/nzt-electrification, MIT licence, 2016). OnSSET 1x1 km settlement
     points for Nigeria (country code 566): projected 2030 population, distance to existing and
     planned grid, distance to roads, GHI, urban flag and least-cost technology per scenario.
     Also existing / planned transmission lines (TopoJSON) and an LGA poverty index.
  2. geoBoundaries gbOpen NGA ADM1 / ADM2 (CC BY 4.0) for state and LGA names.

Run:  python -m minigrid.ingest      (from src/)   or   python src/minigrid/ingest.py
Raw downloads go to data/raw (git-ignored); outputs to data/interim and data/processed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from minigrid.paths import GRID_EXISTING, GRID_PLANNED, INTERIM, RAW  # noqa: E402

NZT_REPO = "https://github.com/energy-data/nzt-electrification"
GB_BASE = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/NGA"
CELL_COLS = ["x", "y", "p_2030", "nc", "gd_c", "gd_p", "rd", "ghi", "w_cf", "hp_d", "u", "adm1", "adm2",
             "l2", "lc_l2", "l3", "lc_l3", "n3", "lc_n3", "lcsa_l", "lcsa_n"]


def fetch_nzt(dest: Path = RAW / "nzt") -> Path:
    """Sparse, blob-less clone: only the Nigeria files are downloaded."""
    if not (dest / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout", NZT_REPO, str(dest)],
                       check=True)
    files = ["LICENSE", "assets/NGA-existing-transmission-lines.json", "assets/NGA-planned-transmission-lines.json",
             "assets/NGA-poverty.csv"]
    subprocess.run(["git", "-C", str(dest), "checkout", "HEAD", "--", *files], check=True)
    # state-level point files only (566-<state>.json); 566-<state>-<lga>.json are subsets of them
    subprocess.run(["git", "-C", str(dest), "checkout", "HEAD", "--", "assets/dumps/points/566-[0-9].json",
                    "assets/dumps/points/566-[0-9][0-9].json"], check=True)
    return dest


def fetch_geoboundaries(dest: Path = RAW) -> dict[str, Path]:
    out = {}
    for adm in ("ADM1", "ADM2"):
        p = dest / f"geoBoundaries-NGA-{adm}_simplified.geojson"
        if not p.exists():
            urllib.request.urlretrieve(f"{GB_BASE}/{adm}/{p.name}", p)
        out[adm] = p
    return out


def load_cells(nzt: Path) -> pd.DataFrame:
    files = [f for f in (nzt / "assets" / "dumps" / "points").glob("566-*.json") if re.fullmatch(r"566-\d+\.json", f.name)]
    if len(files) != 37:
        raise RuntimeError(f"Expected 37 Nigerian state files, found {len(files)}")
    df = pd.concat([pd.DataFrame(json.load(open(f)))[CELL_COLS] for f in files], ignore_index=True)
    if df.duplicated(["x", "y"]).any():
        raise RuntimeError("Duplicate cell coordinates - check source files")
    return df


def topojson_to_geojson(topo: dict, obj: str) -> dict:
    """Minimal TopoJSON decoder for (Multi)LineString objects with a quantization transform."""
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append([x * sx + tx, y * sy + ty])
        arcs.append(pts)

    def line(idx_list):
        coords = []
        for i in idx_list:
            seg = arcs[i] if i >= 0 else arcs[~i][::-1]
            coords.extend(seg if not coords else seg[1:])
        return coords

    feats = []
    for g in topo["objects"][obj]["geometries"]:
        if g["type"] == "LineString":
            geom = {"type": "LineString", "coordinates": line(g["arcs"])}
        elif g["type"] == "MultiLineString":
            geom = {"type": "MultiLineString", "coordinates": [line(a) for a in g["arcs"]]}
        else:
            continue
        feats.append({"type": "Feature", "properties": g.get("properties", {}), "geometry": geom})
    return {"type": "FeatureCollection", "features": feats}


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    nzt = fetch_nzt()
    fetch_geoboundaries()
    cells = load_cells(nzt)
    cells.to_parquet(INTERIM / "nga_cells.parquet", index=False)
    print(f"cells: {len(cells):,} | 2030 population {cells.p_2030.sum()/1e6:,.1f} M")
    for name, out in (("existing", GRID_EXISTING), ("planned", GRID_PLANNED)):
        topo = json.load(open(nzt / "assets" / f"NGA-{name}-transmission-lines.json"))
        gj = topojson_to_geojson(topo, name)
        out.write_text(json.dumps(gj))
        print(f"transmission {name}: {len(gj['features'])} features")
    pov = pd.read_csv(nzt / "assets" / "NGA-poverty.csv", header=None, names=["adm1", "adm2", "poverty_index"])
    pov.to_csv(INTERIM / "nga_poverty.csv", index=False)


if __name__ == "__main__":
    main()
