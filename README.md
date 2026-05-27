<p align="center">
  <h1 align="center">IFI Toolbox</h1>
  <p align="center">
    India Flood Inventory analytics, district hazard summaries, publication atlas figures, and a static web decision dashboard.
  </p>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue.svg">
  <img alt="Dashboard" src="https://img.shields.io/badge/dashboard-static%20HTML%20%7C%20Leaflet%20%7C%20Chart.js-0f766e.svg">
  <img alt="Package" src="https://img.shields.io/badge/toolbox-IFI-2b9348.svg">
  <img alt="Status" src="https://img.shields.io/badge/status-research%20toolbox-orange.svg">
  <img alt="Focus" src="https://img.shields.io/badge/focus-India%20%7C%20floods%20%7C%20districts-0f766e.svg">
</p>

<p align="center">
  <a href="#-overview">Overview</a> |
  <a href="#-dashboard">Dashboard</a> |
  <a href="#-quick-start">Quick Start</a> |
  <a href="#-rebuild-dashboard-data">Rebuild Data</a> |
  <a href="#-publication-atlas">Publication Atlas</a> |
  <a href="#-outputs">Outputs</a> |
  <a href="#-data-policy">Data Policy</a> |
  <a href="#-citation-and-data-sources">Citation</a>
</p>

---

## Overview

**IFI Toolbox** is a research and visualization toolbox for working with the
India Flood Inventory at district scale. It combines a district-exploded IFI
workbook with GADM district boundaries to create reproducible district, state,
seasonal, cause, hazard, and impact summaries.

The repository currently contains two main workflows:

1. **Static web decision dashboard** in `web/ifi_dashboard/`
2. **Publication-style Python atlas figure** in `plot_ifi_main_atlas.py`

The core workflow is:

```text
IFI workbook + GADM districts
        ↓
clean event-district records
        ↓
aggregate district, state, monthly, yearly, cause, and impact metrics
        ↓
browser-ready JSON/GeoJSON/CSV assets
        ↓
interactive district decision atlas + optional publication figure
```

The toolbox is designed for transparent flood-risk exploration: users can move
from national-scale patterns to individual districts, compare frequency and
severity, inspect dominant flood causes, and review reported impacts such as
fatalities, crop area, monetary loss, and planning-priority scores.

## Why IFI Toolbox?

Flood inventories are often event-level tables, while planning decisions are
usually made across administrative units. IFI Toolbox bridges that gap by
turning an event-district inventory into map-ready and dashboard-ready products.

It helps answer questions such as:

- Which districts have the highest number of recorded flood events?
- Which districts have the highest high-end flood severity?
- Where do frequency and severity overlap as hotspots?
- What flood causes dominate in each district or state?
- How do reported impacts vary across districts, states, years, and seasons?
- Which districts rank high in a composite planning-priority score?

The dashboard is intentionally static: after the data assets are built, it can
be hosted with a simple HTTP server or GitHub Pages without a backend.

## Dashboard

The main web application is located at:

```text
web/ifi_dashboard/
```

It provides an interactive India district map with filters, rankings, charts,
and event-level district details.

### Dashboard features

- 🗺️ Leaflet-based district map using GADM district geometries
- 🔎 district, state, cause, minimum-event, minimum-hazard, and hotspot filters
- 🧭 map layers for frequency, P95 hazard, hotspot class, dominant cause,
  fatalities, crop area, monetary loss, and planning priority
- 📊 national trend, cause, monthly-seasonality, state, and district charts
- 📍 selected-district cards with event counts, severity, impacts, and metadata
- 📋 district event table for local review
- 📤 CSV export for the currently filtered district view
- 📦 static JSON/GeoJSON/CSV assets for easy deployment

### Dashboard map layers

The current dashboard supports the following metric layers:

```text
n_events                         Event frequency
p95_hazard_score                 District 95th percentile hazard score
hotspot_score                    Bivariate frequency × severity class
dominant_cause                   Most common classified flood cause
fatalities_apportioned_sum       Apportioned reported fatalities
crop_area_km2_apportioned_sum    Apportioned affected crop area
loss_2026_usd_apportioned_sum    Apportioned reported monetary loss
priority_score                   Composite planning-priority score
```

## Repository

```text
Repository : https://github.com/marcusnobrega-eng/IFI_Toolbox
Toolbox    : IFI Toolbox
Dashboard  : web/ifi_dashboard
Status     : research toolbox / decision atlas
License    : TBD; add a LICENSE file before public release
```

## Quick Start

Clone the repository:

```bash
git clone https://github.com/marcusnobrega-eng/IFI_Toolbox.git
cd IFI_Toolbox
```

Create a Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install --upgrade pip
python3 -m pip install pandas geopandas numpy matplotlib openpyxl
```

Start the static dashboard locally:

```bash
python3 -m http.server 8000 --directory web/ifi_dashboard
```

Open the dashboard in a browser:

```text
http://localhost:8000
```

The dashboard loads prebuilt assets from:

```text
web/ifi_dashboard/data/
```

No Python backend is required once these data files exist.

## Rebuild Dashboard Data

The dashboard data builder is:

```text
web/ifi_dashboard/scripts/build_data.py
```

It reads:

```text
India_Flood_Inventory_v7_corrected_combined_exploded_added_numericalMetrics.xlsx
Districts_Shapefile/GADM41_IND2_Districts.shp
```

and writes browser-ready assets to:

```text
web/ifi_dashboard/data/
```

Run from the repository root:

```bash
python3 web/ifi_dashboard/scripts/build_data.py
```

The script currently expects the IFI workbook to contain a sheet named:

```text
in
```

After rebuilding the assets, restart or refresh the local dashboard:

```bash
python3 -m http.server 8000 --directory web/ifi_dashboard
```

## Current Dataset Snapshot

The prebuilt dashboard assets currently summarize the following dataset state:

```text
Source workbook rows              : 21,921
Valid event-district records      : 21,106
Unique IFI events in workbook     : 6,781
Unique mapped IFI events          : 5,966
GADM districts                    : 676
Districts with IFI records        : 622
States / union territories total  : 36
States with IFI records           : 33
Time span                         : 1967–2023
Mean hazard score                 : 23.06
P95 hazard score                  : 74.50
Total reported fatalities         : 63,085
Total reported people affected    : 282,033,080.3
Total reported crop area          : 422,267.293 km2
Total reported monetary loss      : 5,937,249,011.37 2026 USD
```

Impact totals in the dashboard use apportioned district/state rollups so that
multi-district events are not counted repeatedly in administrative summaries.
Values marked by source sanity-cap flags are excluded from dashboard rollups.

## Publication Atlas

The repository also includes a Python script for generating a publication-style
multi-panel atlas figure:

```text
plot_ifi_main_atlas.py
```

The atlas script aggregates the district-exploded IFI data and creates a static
figure summarizing flood-event frequency, severity, classified causes, hotspot
patterns, seasonality, and state-level cause composition.

### Atlas script outputs

The script writes:

```text
Figures_IFI_Exploded/IFI_main_flood_hazard_atlas_v5b_fixed.png
Figures_IFI_Exploded/IFI_main_flood_hazard_atlas_v5b_fixed.pdf
Figures_IFI_Exploded/IFI_main_flood_hazard_atlas_v5b_fixed.svg
Figures_IFI_Exploded/IFI_district_summary_from_exploded_database_v5b_fixed.csv
```

### Important path note

`plot_ifi_main_atlas.py` is currently a script-style workflow with paths defined
near the top of the file. Before running it on a new machine, update:

```python
BASE_DIR
CSV_PATH
DISTRICT_SHP
COUNTRY_SHP
STATE_SHP
OUT_DIR
```

The dashboard builder is more portable because it uses paths relative to the
repository root.

Run the atlas script after updating paths:

```bash
python3 plot_ifi_main_atlas.py
```

## Complete Workflow

Use this sequence when rebuilding the dashboard from source data.

### 1. Confirm source files

The expected source files are:

```text
India_Flood_Inventory_v7_corrected_combined_exploded_added_numericalMetrics.xlsx
Districts_Shapefile/GADM41_IND2_Districts.shp
Districts_Shapefile/GADM41_IND2_Districts.dbf
Districts_Shapefile/GADM41_IND2_Districts.shx
Districts_Shapefile/GADM41_IND2_Districts.prj
```

The shapefile sidecar files must stay together in the same folder.

### 2. Install Python dependencies

```bash
python3 -m pip install pandas geopandas numpy matplotlib openpyxl
```

If GeoPandas installation is difficult on your system, a conda environment is
usually more reliable:

```bash
conda create -n ifi-toolbox python=3.10 pandas geopandas numpy matplotlib openpyxl -c conda-forge
conda activate ifi-toolbox
```

### 3. Rebuild dashboard assets

```bash
python3 web/ifi_dashboard/scripts/build_data.py
```

### 4. Serve the dashboard locally

```bash
python3 -m http.server 8000 --directory web/ifi_dashboard
```

Open:

```text
http://localhost:8000
```

### 5. Optional: regenerate publication atlas

Update the hard-coded paths in `plot_ifi_main_atlas.py`, then run:

```bash
python3 plot_ifi_main_atlas.py
```

## Outputs

IFI Toolbox organizes generated dashboard products under:

```text
web/ifi_dashboard/data/
  analytics.json
  bootstrap.js
  district_summary.csv
  districts.geojson
  manifest.json
  state_summary.csv
```

The main files are:

```text
analytics.json        Dashboard metadata, totals, metrics, rankings, time series,
                      cause summaries, district details, and provenance.

districts.geojson     Simplified district geometries joined to dashboard metrics.

district_summary.csv  One-row-per-district summary table.

state_summary.csv     State-level event, severity, cause, and impact rollups.

manifest.json         Lightweight asset manifest for checking generated data.

bootstrap.js          Browser bootstrap file telling the dashboard where to load
                      analytics and GeoJSON assets.
```

The static dashboard application itself is:

```text
web/ifi_dashboard/index.html
web/ifi_dashboard/styles.css
web/ifi_dashboard/app.js
```

## Project Layout

```text
IFI_Toolbox/
  India_Flood_Inventory_v7_corrected_combined_exploded_added_numericalMetrics.xlsx
  plot_ifi_main_atlas.py
  s11069-021-04698-6.pdf
  s11069-025-07493-9.pdf

  Districts_Shapefile/
    GADM41_IND2_Districts.shp
    GADM41_IND2_Districts.dbf
    GADM41_IND2_Districts.shx
    GADM41_IND2_Districts.prj
    GADM41_IND2_Districts.cpg
    GADM41_IND2_Districts.zip

  web/
    ifi_dashboard/
      README.md
      index.html
      styles.css
      app.js
      scripts/
        build_data.py
      data/
        analytics.json
        bootstrap.js
        district_summary.csv
        districts.geojson
        manifest.json
        state_summary.csv
```

## Dashboard Deployment

Because the dashboard is static, it can be deployed with GitHub Pages.

If GitHub Pages is enabled from the repository root, the dashboard should be
available at a path like:

```text
https://<username>.github.io/IFI_Toolbox/web/ifi_dashboard/
```

For a cleaner GitHub Pages URL, move or copy the dashboard files into a `docs/`
folder and configure GitHub Pages to serve from `docs/`.

The dashboard uses external CDN assets for Leaflet, Chart.js, and Lucide icons.
An internet connection is therefore required unless those libraries are vendored
locally.

## Data Policy

This repository currently includes the IFI workbook, district shapefile, source
paper PDFs, and prebuilt dashboard assets. That is convenient for reproducible
use, but it makes the repository data-heavy.

Recommended public-release cleanup:

```text
Remove from Git:
  .DS_Store
  __MACOSX/
  temporary local outputs
  local Python environments
  cache folders

Consider Git LFS or external releases for:
  large workbooks
  shapefiles
  generated GeoJSON/JSON assets if they become too large
  publication figures
```

A practical `.gitignore` starting point is:

```gitignore
# macOS
.DS_Store
__MACOSX/

# Python
.venv/
__pycache__/
*.pyc
.ipynb_checkpoints/

# Local outputs
Figures_IFI_Exploded/
*.log

# Optional large/generated assets
# web/ifi_dashboard/data/*.json
# web/ifi_dashboard/data/*.geojson
```

Keep the source workbook and district shapefile under version control only if
that is intentional for the public repository.

## Development Notes

The dashboard data builder is currently script-based rather than an installable
Python package. The most important configuration constants are defined near the
top of:

```text
web/ifi_dashboard/scripts/build_data.py
```

Key constants include:

```text
WORKBOOK                    source IFI workbook
DISTRICT_SHP                GADM district shapefile
MIN_SCORED_EVENTS           minimum scored events for hazard ranking
SIMPLIFY_TOLERANCE_DEGREES  GeoJSON simplification tolerance
USD_INR_2026                INR-to-USD conversion used for dashboard display
```

The dashboard frontend is also static and script-based. Main files:

```text
index.html   page structure and dashboard panels
styles.css   visual styling and responsive layout
app.js       map, filters, charts, rankings, tables, and interactions
```

## Troubleshooting

### The dashboard page opens but the map or charts do not load

Make sure you are serving the folder through HTTP rather than opening
`index.html` directly from the filesystem:

```bash
python3 -m http.server 8000 --directory web/ifi_dashboard
```

Then open:

```text
http://localhost:8000
```

### The dashboard cannot find data files

Rebuild the dashboard assets:

```bash
python3 web/ifi_dashboard/scripts/build_data.py
```

Then check that these files exist:

```text
web/ifi_dashboard/data/analytics.json
web/ifi_dashboard/data/districts.geojson
web/ifi_dashboard/data/bootstrap.js
```

### GeoPandas cannot read the shapefile

Confirm that all shapefile sidecar files are present in the same folder:

```text
.shp
.dbf
.shx
.prj
.cpg
```

If installation errors occur, use a conda environment from `conda-forge`:

```bash
conda create -n ifi-toolbox python=3.10 geopandas pandas numpy matplotlib openpyxl -c conda-forge
conda activate ifi-toolbox
```

### The atlas script fails because of missing paths

Update the script-level path constants in `plot_ifi_main_atlas.py`. The atlas
script currently references local research-computing paths and optional country
and state boundary shapefiles.

## Citation And Data Sources

The toolbox includes and/or references the following IFI-related papers:

- **India flood inventory: creation of a multi-source national geospatial database to facilitate comprehensive flood research**  
  DOI: `https://doi.org/10.1007/s11069-021-04698-6`

- **A district-level flood severity index for flood management in India**  
  DOI: `https://doi.org/10.1007/s11069-025-07493-9`

Please cite the underlying IFI dataset, GADM boundary data, and any related
papers when using this toolbox in research, reports, or derivative datasets.

## License

No license file is currently included in this repository. Add a `LICENSE` file
before public release and update the badge at the top of this README.

If you intend to use the same license as your related toolboxes, add the license
file and update this section, for example:

```text
IFI Toolbox is released under the MIT License.
```
