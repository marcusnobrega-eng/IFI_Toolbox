# India Flood Decision Atlas

Static dashboard for the India Flood Inventory workbook and GADM district shapefile in this repository.

## Run locally

From the repository root:

```bash
python3 -m http.server 8000 --directory web/ifi_dashboard
```

Then open:

```text
http://localhost:8000
```

## Rebuild data assets

The dashboard data is generated from:

- `India_Flood_Inventory_v7_corrected_combined_exploded_added_numericalMetrics.xlsx`
- `Districts_Shapefile/GADM41_IND2_Districts.shp`

Run:

```bash
python3 web/ifi_dashboard/scripts/build_data.py
```

Outputs are written to `web/ifi_dashboard/data/`.
