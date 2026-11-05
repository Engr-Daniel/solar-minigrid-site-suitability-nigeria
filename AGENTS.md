# AGENTS.md

Instructions for AI coding agents and human collaborators working in this repository.

## Project at a glance
A geospatial multi-criteria analysis that ranks Nigerian settlements (H3 hexagons) for village-scale solar mini-grids, plus a Streamlit dashboard. It is a portfolio project by Daniel Oyewale (Petgrave.io).

**Read `MEMORY.md` (context & decisions) and `TASK.md` (priorities) before starting work.**

## Commands
```bash
pip install -r requirements-dev.txt           # dashboard only: requirements.txt
pytest -q                                     # must pass before committing
streamlit run app/streamlit_app.py
python src/minigrid/ingest.py                 # re-download sources -> data/raw, data/interim
python src/minigrid/hexes.py                  # rebuild data/processed/hexes.parquet
python src/minigrid/figures.py                # regenerate README figures
jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
```

## Code map
| Path | Purpose |
|---|---|
| `src/minigrid/ingest.py` | Sparse fetch of the World Bank/KTH OnSSET Nigeria layer + geoBoundaries; TopoJSON decoding |
| `src/minigrid/hexes.py` | 1 km cells → H3 res-7 hexagons; admin names by spatial join |
| `src/minigrid/mcda.py` | Eligibility screen, normalisation, weighted scoring, Monte Carlo robustness, shortlist, OnSSET benchmark |
| `src/minigrid/economics.py` | Demand, PV sizing, capex, LCOE, CO₂ avoided, LCOE low/high range |
| `src/minigrid/figures.py` | Static figures for README / notebook |
| `app/streamlit_app.py` | UI only. No calculation logic |
| `data/reference/*.csv` | Criteria, weight scenarios, economic assumptions. Every assumption needs a source or the label "Assumption" |
| `data/processed/` | Committed outputs the app needs (keep small) |
| `data/raw/`, `data/interim/` | Git-ignored downloads and intermediates |

## Rules
1. **Data honesty:** the core layer is from 2016 (population projected to 2030). Never present results as current ground truth. Label them screening analysis.
2. **Sources:** every number in `economic_assumptions.csv` must cite a source or say "Assumption".
3. **Logic in `src/`.** The app and notebooks import from `minigrid` and never re-implement formulas.
4. **Test what you add** (`tests/`). The real-data sanity tests protect `hexes.parquet`.
5. **Keep `requirements.txt` minimal:** Streamlit Cloud installs it. Heavy tools go in `requirements-dev.txt`.
6. **pydeck colours must be plain Python ints,** not NumPy types, or the layers render grey.
7. **After each session:** update `TASK.md` and record decisions in `MEMORY.md`.

## Commit conventions
`feat:`, `fix:`, `docs:`, `data:`, `test:`, `refactor:`, `chore:`.

## Git attribution
Never add `Co-Authored-By`, `Claude-Session` or other AI attribution lines to commits or PRs (see CLAUDE.md).
