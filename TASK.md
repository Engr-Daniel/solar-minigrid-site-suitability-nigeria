# TASK.md

Status: `[x]` done · `[ ]` to do

## ✅ Phase 1: Build (done, 2026-11-05)
- [x] Reproducible ingest (sparse git fetch of OnSSET Nigeria layer, geoBoundaries, TopoJSON transmission lines)
- [x] H3 res-7 aggregation with state/LGA names
- [x] MCDA: screen, 7 criteria, 3 weight scenarios, Dirichlet robustness, de-duplicated shortlist
- [x] Indicative economics (PV sizing, capex, LCOE ± grant, low/high range, CO₂ avoided)
- [x] Benchmark vs OnSSET-2016 + conservative shortlist
- [x] Static figures, notebook with generated findings, Streamlit dashboard (pydeck H3 map)
- [x] Tests + GitHub Actions CI
- [x] README, methodology, AGENTS, MEMORY, TASK

## 🚀 Phase 2: Publish
- [ ] Deploy to Streamlit Community Cloud (main file `app/streamlit_app.py`) and add the URL to the README *(you)*
- [ ] Make the repo public and pin it *(you)*
- [ ] LinkedIn post

## 💡 Backlog (nice to have)
- [ ] Refresh with current data when access allows: GRID3 settlements, Gridfinder / OSM grid, Global Solar Atlas, WorldPop 2025
- [ ] Exclude areas with existing mini-grids (REA / NEP site lists)
- [ ] AHP pairwise weighting workshop template
- [ ] Hourly PV + battery sizing (pvlib) for the top 10 sites
