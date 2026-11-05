# MEMORY.md

Long-term project memory: context, decisions and lessons. Newest decisions first.

## Context
- **Owner:** Daniel Oyewale (Petgrave.io). Portfolio project 3 of 3. Project 1 = carbon-footprint-esg-dashboard; project 2 (Petgrave Data Strategy Blueprint case study) is paused.
- **Question:** which Nigerian communities suit village-scale solar mini-grids, and how robust is the ranking?
- **Build constraints:** the session could reach only GitHub-hosted data (HDX, WorldPop, NASA, GSA and OSM mirrors were blocked). That led to the World Bank/KTH OnSSET layer on GitHub (MIT) plus geoBoundaries via media.githubusercontent.com.

## Results snapshot (Balanced, defaults)
- 191,316 populated hexagons; 33,138 eligible; top 100: ~759k people, ~98k connections, 27.6 MWp, ~$77M, LCOE $0.26 ($0.14–0.60; $0.18 with grant), ~37 kt CO₂/yr
- Katsina + Bauchi + Zamfara = 70% of the top 100; median 69 km from the grid
- 60% of the top 100 have ≥80% top-N frequency; Balanced vs Developer overlap 85/100
- OnSSET-2016 agreement: 0% of the top 100 (it chose grid); 36.5% of eligible hexagons were OnSSET mini-grids (almost all diesel)
- Conservative shortlist (OnSSET also mini-grid): ~312k people, median 2,816 people per site, in Borno/Yobe/Adamawa

## Decision log
| Date | Decision | Reason |
|---|---|---|
| 2026-11-05 | Core data = World Bank/KTH OnSSET Nigeria 1 km cells (566-<state>.json; LGA files are subsets) | Open, MIT, consistent national layer with population, grid/road distance and GHI. Vintage 2016 is disclosed |
| 2026-11-05 | Spatial unit = H3 res 7 (~5 km²) | Connected components of 1 km cells merged rural belts into 55M-person "settlements" |
| 2026-11-05 | Default screen 800–10,000 people, ≤50% urban, ≥5 km from grid | ESMAP typical mini-grid 800–4,000 people; village scale |
| 2026-11-05 | Demand saturates at 4,000 (log_cap) | Without it the ranking chased the largest towns (OnSSET would grid-connect them) |
| 2026-11-05 | `gd_p` treated as distance to future grid (existing OR planned) | Data shows gd_p ≤ gd_c everywhere |
| 2026-11-05 | OnSSET-2016 tech used as a benchmark, not a criterion; conservative toggle added | 2016 PV costs make it biased against solar; SEforALL IEP 2022 supports dense-and-remote mini-grids |
| 2026-11-05 | Capex = $1,200/kWp generation + $450/connection distribution | LCOE varies with GHI; total ~$790/connection sits within ESMAP $500–2,100 |
| 2026-11-05 | Poverty index weight 0 by default | Definition and year undocumented in the source |

## Lessons learned
- pydeck needs plain Python ints in colour lists; NumPy ints render grey.
- `git ls-tree -l` on a blob-less partial clone fetches every blob. Use `--name-only`, then check out only the needed paths.
- Validation against an external model surfaced a real modelling bias (size-chasing). Always benchmark.
