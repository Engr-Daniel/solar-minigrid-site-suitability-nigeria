# Methodology

## 1. Question and scope
*Which unelectrified Nigerian communities are the best candidates for a **village-scale solar mini-grid**, and how robust is that ranking?*
This is a **national screening** analysis that produces a prioritised long-list for field verification. It is not a feasibility study.

## 2. Data
| Layer | Source | Licence | Vintage | Notes |
|---|---|---|---|---|
| Settlement cells (934,595 × 1 km²): population 2030, distance to existing / planned grid, distance to road, GHI, urban flag, least-cost technology | World Bank ESMAP & KTH-dESA, *Electrification pathways for Nigeria, Tanzania and Zambia* ([energy-data/nzt-electrification](https://github.com/energy-data/nzt-electrification)), OnSSET model ([Mentis et al. 2015](http://www.sciencedirect.com/science/article/pii/S0973082615000952)) | MIT (© 2016 World Bank Group) | 2016 release; population projected to 2030 | `566-<state>.json` files only (LGA files are subsets) |
| Existing & planned transmission lines | Same repository (TopoJSON, decoded in `ingest.py`) | MIT | 2016 | 85 existing / 30 planned features |
| LGA poverty index (0–1) | Same repository | MIT | Undocumented | Optional equity criterion, off by default |
| State & LGA boundaries | [geoBoundaries](https://www.geoboundaries.org/) gbOpen NGA ADM1 / ADM2 | CC BY 4.0 | Current | Names via spatial join |

`gd_p` ("planned grid distance") is the distance to the nearest **existing or planned** line, so it is reported as *distance to the future grid*.

## 3. Spatial unit: H3 hexagons
Cells are aggregated to **H3 resolution 7** (~5.2 km², edge ~1.4 km), roughly the footprint a village distribution network serves. Pure connected-component clustering of 1 km cells was tested and rejected: dense rural belts merge into "settlements" of tens of millions of people.

Per hexagon: population (sum), grid / future-grid / road distance (minimum over cells), GHI (population-weighted mean, zeros treated as missing), peak cell density, urban share, LGA poverty, and the OnSSET-2016 least-cost technology for Tier 3 demand at low diesel price (population-weighted mode).

## 4. Eligibility screen (defaults; all adjustable in the dashboard)
| Rule | Default | Why |
|---|---|---|
| Population 2030 | 800–10,000 | ESMAP: a typical 3rd-generation mini-grid serves 800–4,000 people. Larger towns are grid-extension or town-scale interconnected candidates |
| Urban share | ≤ 50% | Focus on unserved rural settlements |
| Distance to existing grid | ≥ 5 km | Closer than this, grid densification or extension is usually least-cost |
| GHI | not missing | 402 hexagons lack solar data |

## 5. Criteria and scoring
Each criterion is normalised to 0–1 **within the eligible set** (`data/reference/criteria.csv`):

| Criterion | Variable | Direction / transform | Rationale |
|---|---|---|---|
| Demand | population | benefit, log, **saturates at 4,000** | More customers spread fixed costs, with diminishing returns |
| Compactness | densest 1 km cell | benefit, log | Less network per customer |
| Remoteness | distance to existing grid | benefit, linear capped at 50 km | Grid extension costly; avoid over-rewarding extremes |
| Grid risk | distance to future grid | benefit, linear capped at 30 km | Lower risk of a stranded asset |
| Solar | GHI | benefit, min-max | More kWh per kWp |
| Access | distance to road | cost, linear capped at 20 km | Construction and O&M logistics |
| Need | LGA poverty index | benefit, min-max | Equity lens (optional) |

**Score = 100 × Σ wᵢ·zᵢ** (weighted linear combination). Three weight presets (`weight_scenarios.csv`): **Balanced**, **Developer (commercial)** and **Access & equity**.

## 6. Robustness
Weights are perturbed with a **Dirichlet distribution** centred on the chosen weights (concentration 20, 600–1,000 draws, zero weights stay zero). For each site we report the share of draws in which it stays in the top N. This tests whether the shortlist is an artefact of one weighting choice.

## 7. Shortlist
Sites are picked greedily by rank, skipping any hexagon adjacent (one H3 ring) to an already-chosen site, so one town doesn't take several slots.

## 8. Indicative economics (`economic_assumptions.csv`)
- **Connections** = population ÷ 5.42 (NBS rural household size) × 70% uptake.
- **Demand** = connections × 365 kWh (MTF Tier 3) × 1.3 (productive & community use).
- **PV size** = demand ÷ (GHI × 0.75 performance ratio).
- **Capex** = PV kWp × $1,200 (PV + ~1.5 kWh/kWp battery + inverters + BOS) + connections × $450 (network, meters, soft costs). The check is ~$790/connection, inside ESMAP's US$500–2,100 range.
- **LCOE** = (capex × CRF(10%, 20 yr) + 4% O&M) ÷ annual kWh. The variant with the US$350/connection grant reflects the Nigeria Electrification Project performance-based grant.
- **Low/high LCOE** swaps generation & distribution capex, O&M, discount rate and performance ratio to their range ends.
- **CO₂ avoided** = annual kWh × 0.30 L/kWh × 2.66155 kgCO₂e/L (DESNZ 2026, 100% mineral diesel). This is combustion only and therefore conservative.

## 9. Benchmark against OnSSET-2016
For 36.5% of eligible hexagons the OnSSET-2016 run (Tier 3, low diesel price) chose a mini-grid, but almost all were **diesel** mini-grids in small, sparse villages. Solar PV mini-grids were least-cost for only ~0.1% of Nigeria's population because of 2016 PV and battery costs. For the larger compact settlements on our shortlist, it chose **grid extension**.

This disagreement is expected. With current costs, the SEforALL / REA **Nigeria Integrated Energy Plan geospatial model (2022)** finds mini-grids least-cost *"predominantly in dense … areas further from existing grid infrastructure"*. A **conservative shortlist** restricted to sites where OnSSET-2016 also chose a mini-grid is available in the dashboard and notebook.

## 10. Limitations
- Settlement, grid and road layers are from **2016**. The grid has expanded since, so every shortlisted site needs a current grid check.
- Population is a **2030 projection** from the 2016 model.
- GHI is annual. Seasonality (harmattan dust, rainy season) and hourly load profiles are not modelled.
- Economics are screening-level: no HOMER-style dispatch, diesel backup, battery replacement schedule or tariff and affordability analysis.
- Not modelled: willingness to pay, anchor loads, security, land tenure, permitting or existing mini-grids.
