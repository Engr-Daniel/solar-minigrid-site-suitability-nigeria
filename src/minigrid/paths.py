"""Project paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
REFERENCE = ROOT / "data" / "reference"
FIGURES = ROOT / "reports" / "figures"

HEXES = PROCESSED / "hexes.parquet"
STATES = PROCESSED / "nga_states.geojson"
GRID_EXISTING = PROCESSED / "transmission_existing.geojson"
GRID_PLANNED = PROCESSED / "transmission_planned.geojson"
