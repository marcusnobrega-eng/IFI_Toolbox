#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IFI Flood Hazard Classification — Main Visualization Atlas, v3
==============================================================

This script reads the district-exploded IFI flood database and GADM district
shapefile, aggregates the data at district/state/month levels, and creates one
publication-style multi-panel figure.

Updates in v3
-------------
1. Removed the figure subtitle below the main title.
2. Increased fonts throughout the figure.
3. Added a clearer legend for the state-level cause-composition plot.
4. Added a state-reference map with state names.
5. Added white boxes behind heatmap numbers so labels remain readable.
6. Reduced map footnote clutter and improved colorbar readability.

Inputs
------
District-exploded IFI database:
    /oak/stanford/groups/gorelick/Marcus/India/IFI_FloodHazard_Classification/
    Expanded_IFI_with_No_Discrepancies_v4_enriched_hazard_with_cause_district_exploded.csv

District shapefile:
    /oak/stanford/groups/gorelick/Marcus/India/IFI_FloodHazard_Classification/
    Districts_Shapefile/GADM41_IND2_Districts.shp

Country boundary:
    /oak/stanford/groups/gorelick/Marcus/India/Shapefile/India_Country_Boundary.shp

State boundary:
    /oak/stanford/groups/gorelick/Marcus/India/Shapefile/India_State_Boundary.shp

Outputs
-------
    Figures_IFI_Exploded/IFI_main_flood_hazard_atlas_v5b_fixed.png
    Figures_IFI_Exploded/IFI_main_flood_hazard_atlas_v5b_fixed.pdf
    Figures_IFI_Exploded/IFI_main_flood_hazard_atlas_v5b_fixed.svg
    Figures_IFI_Exploded/IFI_district_summary_from_exploded_database_v5b_fixed.csv
"""

# ============================================================
# 1. Imports
# ============================================================

import os
import textwrap
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import BoundaryNorm
from matplotlib.patches import Patch, Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


# ============================================================
# 2. User configuration
# ============================================================

BASE_DIR = Path("/oak/stanford/groups/gorelick/Marcus/India/IFI_FloodHazard_Classification")

CSV_PATH = "/oak/stanford/groups/gorelick/Marcus/India/IFI_FloodHazard_Classification/IFI_v5c_from_raw_comprehensive_outputs/India_Flood_Inventory_v5c_comprehensive_from_raw_district_exploded.csv"

DISTRICT_SHP = BASE_DIR / "Districts_Shapefile" / "GADM41_IND2_Districts.shp"

COUNTRY_SHP = Path("/oak/stanford/groups/gorelick/Marcus/India/Shapefile/India_Country_Boundary.shp")
STATE_SHP = Path("/oak/stanford/groups/gorelick/Marcus/India/Shapefile/India_State_Boundary.shp")

OUT_DIR = BASE_DIR / "Figures_IFI_Exploded"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FIG_PNG = OUT_DIR / "IFI_main_flood_hazard_atlas_v5b_fixed.png"
OUT_FIG_PDF = OUT_DIR / "IFI_main_flood_hazard_atlas_v5b_fixed.pdf"
OUT_FIG_SVG = OUT_DIR / "IFI_main_flood_hazard_atlas_v5b_fixed.svg"
OUT_DISTRICT_SUMMARY = OUT_DIR / "IFI_district_summary_from_exploded_database_v5b_fixed.csv"

# Minimum number of scored events required to show district hazard percentile.
MIN_SCORED_EVENTS_FOR_HAZARD_MAP = 3

# Number of states to show in the stacked bar panel.
TOP_N_STATES_FOR_BAR = 18

# Projection for plotting. EPSG:7755 is useful for India-centered projected maps.
PLOT_CRS = "EPSG:7755"

# Optional Helvetica font used in several previous publication plots.
HELVETICA_PATH = Path("/groups/patroch/maria/extra/helvetica.ttf")

# Set this to True if state names become too crowded.
USE_STATE_ABBREVIATIONS_ON_MAP = False


# ============================================================
# 3. Plot style
# ============================================================

def setup_plot_style():
    """Configure publication-style matplotlib settings."""

    if HELVETICA_PATH.exists():
        try:
            from matplotlib import font_manager
            font_manager.fontManager.addfont(str(HELVETICA_PATH))
            mpl.rcParams["font.family"] = "Helvetica"
        except Exception:
            mpl.rcParams["font.family"] = "DejaVu Sans"
    else:
        mpl.rcParams["font.family"] = "DejaVu Sans"

    mpl.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 450,
        "axes.linewidth": 1.25,
        "axes.edgecolor": "black",
        "axes.labelsize": 13,
        "axes.titlesize": 16,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 10.5,
        "legend.title_fontsize": 11.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    })


# ============================================================
# 4. Helper functions
# ============================================================

def find_first_existing_column(df, candidates, required=True, label="column"):
    """Find the first available column from a list of possible names."""

    for col in candidates:
        if col in df.columns:
            return col

    if required:
        raise ValueError(
            f"Could not find required {label}. Tried: {candidates}\n"
            f"Available columns include:\n{list(df.columns)[:100]}"
        )

    return None


def parse_boolean_series(series):
    """Robustly parse boolean-like values."""

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y", "t"])
    )


def clean_text_series(series, fill_value="unknown"):
    """Clean string columns used for grouping."""

    return (
        series.astype(str)
        .str.strip()
        .replace({"": fill_value, "nan": fill_value, "None": fill_value, "NONE": fill_value})
        .fillna(fill_value)
    )


def format_cause_label(x):
    """
    Convert cause codes to plot-friendly labels.
    This does not modify the source database.
    """

    label_map = {
        "pluvial": "Pluvial",
        "fluvial": "Fluvial",
        "compound": "Compound",
        "compound_pluvial_fluvial": "Compound",
        "compound_coastal_rainfall_or_fluvial": "Compound coastal",
        "coastal": "Coastal",
        "flash_flood": "Flash flood",
        "flash_flood_or_cloudburst": "Flash flood",
        "landslide_related": "Landslide-related",
        "compound_flash_flood_landslide": "Flash + landslide",
        "dam_or_reservoir_related_fluvial": "Dam/reservoir",
        "dam_reservoir": "Dam/reservoir",
        "unspecified": "Unspecified",
        "unspecified_flood": "Unspecified",
        "unknown": "Unknown",
        "unknown_or_insufficient_text": "Unknown",
    }

    s = str(x).strip().lower()
    return label_map.get(s, str(x).replace("_", " ").title())


def add_panel_label(ax, label):
    """Add bold panel label in the upper-left corner."""

    ax.text(
        0.012, 0.985, label,
        transform=ax.transAxes,
        ha="left", va="top",
        fontsize=18,
        fontweight="bold",
        bbox=dict(
            boxstyle="round,pad=0.18",
            facecolor="white",
            edgecolor="black",
            linewidth=1.0,
            alpha=0.97,
        ),
        zorder=50,
    )


def style_map_axis(ax):
    """Remove map axes and keep a clean geographic figure style."""

    ax.set_axis_off()
    ax.set_aspect("equal")


def make_unique_boundaries(values, percentiles):
    """Build robust percentile-based color boundaries."""

    values = pd.Series(values).replace([np.inf, -np.inf], np.nan).dropna()
    values = values[values > 0]

    if len(values) == 0:
        return np.array([0, 1], dtype=float)

    raw = np.nanpercentile(values, percentiles)
    bounds = np.unique(np.round(raw, 6))

    if bounds[0] > 0:
        bounds = np.insert(bounds, 0, 0)

    if len(bounds) < 4:
        vmin = float(values.min())
        vmax = float(values.max())
        if vmin == vmax:
            bounds = np.array([0, vmax], dtype=float)
        else:
            bounds = np.linspace(vmin, vmax, 7)
            bounds = np.insert(bounds, 0, 0)
            bounds = np.unique(bounds)

    return bounds.astype(float)


def choose_colorbar_ticks(bounds, max_ticks=7):
    """Choose readable ticks from a boundary vector."""

    bounds = np.asarray(bounds, dtype=float)
    if len(bounds) <= max_ticks:
        return bounds

    idx = np.linspace(0, len(bounds) - 1, max_ticks).round().astype(int)
    idx = np.unique(idx)
    return bounds[idx]


def format_cb_tick(x):
    """Format colorbar tick labels compactly."""

    if abs(x - round(x)) < 1e-6:
        return f"{int(round(x))}"
    return f"{x:.1f}"


def add_colorbar(fig, ax, cmap, norm, label, ticks=None, extend="neither"):
    """Add a thick, publication-style colorbar below a map panel."""

    cax = inset_axes(
        ax,
        width="68%",
        height="5.0%",
        loc="lower center",
        bbox_to_anchor=(0.0, -0.055, 1.0, 1.0),
        bbox_transform=ax.transAxes,
        borderpad=0,
    )

    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    cbar = fig.colorbar(
        sm,
        cax=cax,
        orientation="horizontal",
        ticks=ticks,
        extend=extend,
    )

    cbar.set_label(label, fontsize=11.5, labelpad=4)
    cbar.ax.tick_params(labelsize=10, width=1.15, length=3.5)
    cbar.outline.set_linewidth(1.45)

    if ticks is not None:
        cbar.ax.set_xticklabels([format_cb_tick(t) for t in ticks])

    return cbar


def get_cause_color_dict(causes):
    """Assign clear, distinguishable colors to flood-cause groups."""

    base_colors = {
        "Pluvial": "#2ca25f",             # green
        "Fluvial": "#3182bd",             # blue
        "Compound": "#756bb1",            # purple
        "Compound coastal": "#b35806",    # brown/orange
        "Coastal": "#e6550d",             # orange-red
        "Flash flood": "#fdae61",         # light orange
        "Landslide-related": "#8c510a",   # brown
        "Flash + landslide": "#a63603",   # dark orange-red
        "Dam/reservoir": "#de2d26",       # red
        "Unspecified": "#969696",         # gray
        "Unknown": "#d9d9d9",             # light gray
        "No IFI record": "#f0f0f0",       # very light gray
    }

    fallback = list(mpl.cm.tab20.colors)
    color_dict = {}

    for i, cause in enumerate(causes):
        key = str(cause)
        color_dict[key] = base_colors.get(key, fallback[i % len(fallback)])

    return color_dict


def classify_tertiles(values):
    """Classify values into low / medium / high using tertiles."""

    s = pd.Series(values).replace([np.inf, -np.inf], np.nan)

    if s.notna().sum() < 3:
        return pd.Series(np.nan, index=s.index)

    q1, q2 = np.nanpercentile(s.dropna(), [33.333, 66.667])

    if q1 == q2:
        try:
            return pd.qcut(s.rank(method="first"), q=3, labels=[0, 1, 2]).astype(float)
        except Exception:
            return pd.Series(np.nan, index=s.index)

    out = pd.Series(np.nan, index=s.index)
    out[s <= q1] = 0
    out[(s > q1) & (s <= q2)] = 1
    out[s > q2] = 2

    return out


def add_bivariate_legend(ax, color_matrix, title="Frequency × severity"):
    """Add a small 3x3 bivariate legend to the hotspot map."""

    leg_ax = inset_axes(
        ax,
        width="30%",
        height="30%",
        loc="lower left",
        bbox_to_anchor=(0.04, 0.03, 1.0, 1.0),
        bbox_transform=ax.transAxes,
        borderpad=0,
    )

    leg_ax.set_xlim(0, 3)
    leg_ax.set_ylim(0, 3)

    for freq_class in range(3):
        for sev_class in range(3):
            color = color_matrix[(freq_class, sev_class)]
            leg_ax.add_patch(
                Rectangle(
                    (freq_class, sev_class),
                    1, 1,
                    facecolor=color,
                    edgecolor="white",
                    linewidth=0.95,
                )
            )

    leg_ax.set_xticks([0.5, 1.5, 2.5])
    leg_ax.set_yticks([0.5, 1.5, 2.5])
    leg_ax.set_xticklabels(["Low", "Med", "High"], fontsize=8)
    leg_ax.set_yticklabels(["Low", "Med", "High"], fontsize=8)
    leg_ax.tick_params(length=0)

    leg_ax.set_xlabel("Frequency", fontsize=8.5, labelpad=1)
    leg_ax.set_ylabel("Severity", fontsize=8.5, labelpad=1)
    leg_ax.set_title(title, fontsize=9.0, pad=2)

    for spine in leg_ax.spines.values():
        spine.set_linewidth(1.0)
        spine.set_edgecolor("black")

    leg_ax.set_facecolor("white")


def wrap_state_label(name, width=13):
    """Wrap long state names for map labels."""

    name = str(name).strip()

    abbreviations = {
        "Andaman and Nicobar": "A&N",
        "Andaman and Nicobar Islands": "A&N",
        "Andhra Pradesh": "Andhra\nPradesh",
        "Arunachal Pradesh": "Arunachal\nPradesh",
        "Dadra and Nagar Haveli and Daman and Diu": "DNH & DD",
        "Himachal Pradesh": "Himachal\nPradesh",
        "Jammu and Kashmir": "Jammu &\nKashmir",
        "Madhya Pradesh": "Madhya\nPradesh",
        "Tamil Nadu": "Tamil\nNadu",
        "Uttar Pradesh": "Uttar\nPradesh",
        "West Bengal": "West\nBengal",
    }

    if USE_STATE_ABBREVIATIONS_ON_MAP and name in abbreviations:
        return abbreviations[name]

    return textwrap.fill(name, width=width, break_long_words=False)


# ============================================================
# 5. Data loading and aggregation
# ============================================================

def load_and_prepare_data():
    """Load exploded IFI database and map shapefiles."""

    print("\n============================================================")
    print("Loading IFI district-exploded database")
    print("============================================================")
    print(f"CSV: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, low_memory=False)

    print(f"Rows in exploded database: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")

    print("\n============================================================")
    print("Loading district, state, and country shapefiles")
    print("============================================================")
    print(f"Districts: {DISTRICT_SHP}")
    print(f"States:    {STATE_SHP}")
    print(f"Country:   {COUNTRY_SHP}")

    districts = gpd.read_file(DISTRICT_SHP)
    states = gpd.read_file(STATE_SHP) if STATE_SHP.exists() else None
    country = gpd.read_file(COUNTRY_SHP) if COUNTRY_SHP.exists() else None

    print(f"District polygons: {len(districts):,}; CRS: {districts.crs}")
    if states is not None:
        print(f"State polygons:    {len(states):,}; CRS: {states.crs}")
    else:
        print("WARNING: State shapefile was not found. State reference map will be skipped.")
    if country is not None:
        print(f"Country polygons:  {len(country):,}; CRS: {country.crs}")
    else:
        print("WARNING: Country shapefile was not found. Country outline will be skipped.")

    # Required and optional database columns.
    gid_col = find_first_existing_column(df, ["GID_2", "gadm_gid_2"], required=True, label="district ID")

    district_name_col = find_first_existing_column(
        df,
        ["NAME_2", "District", "district"],
        required=False,
        label="district name",
    )

    state_name_col = find_first_existing_column(
        df,
        ["NAME_1", "State", "state"],
        required=False,
        label="state name",
    )

    event_id_col = find_first_existing_column(
        df,
        ["UEI", "ID", "Event_ID", "event_id", "event_uid", "DisNo.", "disaster_id"],
        required=False,
        label="event identifier",
    )

    if event_id_col is None:
        warnings.warn(
            "No event ID column found. The script will use the row index as event ID. "
            "This is not ideal for event counting."
        )
        df["_event_id_internal"] = np.arange(len(df))
        event_id_col = "_event_id_internal"

    hazard_col = find_first_existing_column(
        df,
        ["flood_hazard_score_0_100_v5", "flood_hazard_score_0_100", "hazard_score_0_100", "flood_hazard_score"],
        required=False,
        label="hazard score",
    )

    cause_col = find_first_existing_column(
        df,
        ["event_cause_map_group_v5", "event_cause_map_group", "event_cause_primary_v5", "event_cause_primary", "Main Cause"],
        required=False,
        label="cause group",
    )

    confidence_col = find_first_existing_column(
        df,
        ["event_cause_confidence_v5", "event_cause_confidence", "cause_confidence"],
        required=False,
        label="cause confidence",
    )

    start_date_col = find_first_existing_column(
        df,
        ["Start_Date_parsed_v5", "Start Date", "start_date", "START_DATE", "Start_Date"],
        required=False,
        label="start date",
    )

    # Keep only rows with a valid exploded district ID.
    df[gid_col] = df[gid_col].astype(str).str.strip()
    valid = df[gid_col].notna() & (df[gid_col] != "") & (df[gid_col].str.lower() != "nan")

    # Honor gadm_match_valid_for_metric if present.
    if "gadm_match_valid_for_metric" in df.columns:
        valid_bool = parse_boolean_series(df["gadm_match_valid_for_metric"])
        valid = valid & valid_bool

    df_valid = df.loc[valid].copy()

    print("\n============================================================")
    print("Spatially valid exploded rows")
    print("============================================================")
    print(f"Valid event-district rows: {len(df_valid):,}")
    print(f"Unique districts in valid rows: {df_valid[gid_col].nunique():,}")
    print(f"Event ID column used: {event_id_col}")

    # Standard internal columns for plotting.
    df_valid["_GID_2"] = df_valid[gid_col].astype(str).str.strip()
    df_valid["_event_id"] = df_valid[event_id_col].astype(str)

    if district_name_col is not None:
        df_valid["_district_name"] = clean_text_series(df_valid[district_name_col], fill_value="Unknown district")
    else:
        df_valid["_district_name"] = "Unknown district"

    if state_name_col is not None:
        df_valid["_state_name"] = clean_text_series(df_valid[state_name_col], fill_value="Unknown state")
    else:
        df_valid["_state_name"] = "Unknown state"

    if cause_col is not None:
        raw_cause = clean_text_series(df_valid[cause_col], fill_value="unknown")
        df_valid["_cause_raw"] = raw_cause
        df_valid["_cause_plot"] = raw_cause.map(format_cause_label)
    else:
        df_valid["_cause_raw"] = "unknown"
        df_valid["_cause_plot"] = "Unknown"

    if confidence_col is not None:
        df_valid["_confidence"] = clean_text_series(df_valid[confidence_col], fill_value="unknown")
    else:
        df_valid["_confidence"] = "unknown"

    if hazard_col is not None:
        df_valid["_hazard_score"] = pd.to_numeric(df_valid[hazard_col], errors="coerce")
    else:
        df_valid["_hazard_score"] = np.nan

    # Prefer the already-corrected v5 year/month columns. If absent, parse
    # day-first to avoid the January/month-swap bug.
    if "start_year_v5" in df_valid.columns and "start_month_v5" in df_valid.columns:
        df_valid["_year"] = pd.to_numeric(df_valid["start_year_v5"], errors="coerce")
        df_valid["_month"] = pd.to_numeric(df_valid["start_month_v5"], errors="coerce")
        if start_date_col is not None:
            df_valid["_start_date"] = pd.to_datetime(df_valid[start_date_col], errors="coerce")
        else:
            df_valid["_start_date"] = pd.NaT
    elif start_date_col is not None:
        df_valid["_start_date"] = pd.to_datetime(df_valid[start_date_col], dayfirst=True, errors="coerce")
        df_valid["_year"] = df_valid["_start_date"].dt.year
        df_valid["_month"] = df_valid["_start_date"].dt.month
    else:
        df_valid["_start_date"] = pd.NaT
        df_valid["_year"] = np.nan
        df_valid["_month"] = np.nan

    # Remove accidental duplicate event-district combinations.
    event_district = (
        df_valid
        .sort_values(["_GID_2", "_event_id"])
        .drop_duplicates(subset=["_GID_2", "_event_id"], keep="first")
        .copy()
    )

    print(f"Unique event-district records after duplicate protection: {len(event_district):,}")

    return df_valid, event_district, districts, states, country


def build_district_summary(event_district, districts):
    """Build one-row-per-district summary table."""

    print("\n============================================================")
    print("Building district summary table")
    print("============================================================")

    counts = (
        event_district
        .groupby("_GID_2")["_event_id"]
        .nunique()
        .rename("n_events")
        .reset_index()
    )

    hazard = (
        event_district
        .groupby("_GID_2")["_hazard_score"]
        .agg(
            n_scored_events=lambda x: x.notna().sum(),
            mean_hazard_score="mean",
            median_hazard_score="median",
            p95_hazard_score=lambda x: np.nanpercentile(x.dropna(), 95) if x.notna().sum() > 0 else np.nan,
        )
        .reset_index()
    )

    cause_counts = (
        event_district
        .groupby(["_GID_2", "_cause_plot"])["_event_id"]
        .nunique()
        .rename("cause_event_count")
        .reset_index()
    )

    dominant = (
        cause_counts
        .sort_values(["_GID_2", "cause_event_count"], ascending=[True, False])
        .drop_duplicates("_GID_2", keep="first")
        .rename(columns={
            "_cause_plot": "dominant_cause",
            "cause_event_count": "dominant_cause_count",
        })
    )

    district_total = counts.rename(columns={"n_events": "total_events_for_dominance"})
    dominant = dominant.merge(district_total, on="_GID_2", how="left")
    dominant["dominant_cause_share"] = (
        dominant["dominant_cause_count"] / dominant["total_events_for_dominance"]
    )

    dominant = dominant[[
        "_GID_2",
        "dominant_cause",
        "dominant_cause_count",
        "dominant_cause_share",
    ]]

    conf = event_district.copy()
    conf["_is_low_confidence"] = conf["_confidence"].str.lower().eq("low")

    confidence_summary = (
        conf
        .groupby("_GID_2")
        .agg(
            low_confidence_count=("_is_low_confidence", "sum"),
            total_confidence_records=("_is_low_confidence", "count"),
        )
        .reset_index()
    )
    confidence_summary["low_confidence_share"] = (
        confidence_summary["low_confidence_count"] /
        confidence_summary["total_confidence_records"]
    )

    cause_wide = cause_counts.pivot_table(
        index="_GID_2",
        columns="_cause_plot",
        values="cause_event_count",
        fill_value=0,
        aggfunc="sum",
    )

    cause_wide.columns = [
        f"cause_count_{str(c).lower().replace(' ', '_').replace('/', '_').replace('+', 'plus')}"
        for c in cause_wide.columns
    ]
    cause_wide = cause_wide.reset_index()

    summary = counts.merge(hazard, on="_GID_2", how="left")
    summary = summary.merge(dominant, on="_GID_2", how="left")
    summary = summary.merge(confidence_summary, on="_GID_2", how="left")
    summary = summary.merge(cause_wide, on="_GID_2", how="left")

    name_cols = [c for c in ["GID_2", "NAME_2", "NAME_1"] if c in districts.columns]
    district_names = districts[name_cols].copy()
    district_names = district_names.rename(columns={"GID_2": "_GID_2"})

    summary = district_names.merge(summary, on="_GID_2", how="left")

    summary["n_events"] = summary["n_events"].fillna(0).astype(int)
    summary["n_scored_events"] = summary["n_scored_events"].fillna(0).astype(int)
    summary["dominant_cause"] = summary["dominant_cause"].fillna("No IFI record")
    summary["dominant_cause_count"] = summary["dominant_cause_count"].fillna(0).astype(int)
    summary["dominant_cause_share"] = summary["dominant_cause_share"].fillna(0)

    summary.to_csv(OUT_DISTRICT_SUMMARY, index=False)
    print(f"Saved district summary: {OUT_DISTRICT_SUMMARY}")

    return summary


def project_gdf(gdf, target_crs=PLOT_CRS, name="geodataframe"):
    """Project a GeoDataFrame with a safe fallback."""

    if gdf is None:
        return None

    try:
        out = gdf.to_crs(target_crs)
        print(f"Projected {name} to {target_crs}")
        return out
    except Exception as exc:
        warnings.warn(f"Could not project {name} to {target_crs}. Using original CRS. Reason: {exc}")
        return gdf


def merge_summary_with_geometry(summary, districts):
    """Merge district summary onto district geometries."""

    if "GID_2" not in districts.columns:
        raise ValueError("The district shapefile must contain a GID_2 column.")

    merged = districts.merge(
        summary,
        left_on="GID_2",
        right_on="_GID_2",
        how="left",
    )

    return project_gdf(merged, name="districts")


# ============================================================
# 6. Panel plotting functions
# ============================================================

def plot_event_frequency_map(fig, ax, gdf):
    """Panel A: event frequency map."""

    style_map_axis(ax)
    add_panel_label(ax, "A")

    ax.set_title("District-level IFI flood-event frequency", fontweight="bold", pad=8)

    gdf.plot(ax=ax, color="#f2f2f2", edgecolor="white", linewidth=0.13, zorder=1)

    values = gdf["n_events"].replace(0, np.nan)

    bounds = make_unique_boundaries(values, percentiles=[0, 20, 40, 60, 80, 90, 97, 100])
    cmap = mpl.cm.get_cmap("YlOrRd", len(bounds) - 1)
    norm = BoundaryNorm(bounds, cmap.N)

    gdf.assign(_plot_value=values).plot(
        column="_plot_value",
        ax=ax,
        cmap=cmap,
        norm=norm,
        edgecolor="white",
        linewidth=0.09,
        missing_kwds={"color": "#f2f2f2"},
        zorder=2,
    )

    ticks = choose_colorbar_ticks(bounds, max_ticks=7)
    add_colorbar(
        fig,
        ax,
        cmap=cmap,
        norm=norm,
        label="Unique IFI events per district",
        ticks=ticks,
        extend="max",
    )


def plot_hazard_map(fig, ax, gdf):
    """Panel B: p95 hazard score map."""

    style_map_axis(ax)
    add_panel_label(ax, "B")

    ax.set_title("District-level 95th percentile hazard score", fontweight="bold", pad=8)

    gdf.plot(ax=ax, color="#eeeeee", edgecolor="white", linewidth=0.13, zorder=1)

    plot_value = gdf["p95_hazard_score"].copy()
    plot_value[gdf["n_scored_events"] < MIN_SCORED_EVENTS_FOR_HAZARD_MAP] = np.nan

    bounds = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=float)
    cmap = mpl.cm.get_cmap("viridis", len(bounds) - 1)
    norm = BoundaryNorm(bounds, cmap.N)

    gdf.assign(_plot_value=plot_value).plot(
        column="_plot_value",
        ax=ax,
        cmap=cmap,
        norm=norm,
        edgecolor="white",
        linewidth=0.09,
        missing_kwds={"color": "#eeeeee", "edgecolor": "white"},
        zorder=2,
    )

    add_colorbar(
        fig,
        ax,
        cmap=cmap,
        norm=norm,
        label=f"P95 hazard score, 0–100; gray if n < {MIN_SCORED_EVENTS_FOR_HAZARD_MAP}",
        ticks=np.array([0, 20, 40, 60, 80, 100]),
        extend="neither",
    )


def plot_dominant_cause_map(ax, gdf):
    """Panel C: dominant cause map."""

    style_map_axis(ax)
    add_panel_label(ax, "C")

    ax.set_title("Dominant classified flood cause by district", fontweight="bold", pad=8)

    plot_gdf = gdf.copy()
    plot_gdf["_dominant_plot"] = plot_gdf["dominant_cause"].fillna("No IFI record")

    present_dominant_causes = (
        plot_gdf.loc[plot_gdf["n_events"] > 0, "_dominant_plot"]
        .dropna()
        .unique()
        .tolist()
    )

    # Keep a fixed legend order so panels C and E use the same colors.
    # Some categories may appear in panel E or the database but not be the
    # dominant category in any district. They are still shown in the legend
    # to make the cause-color dictionary explicit and stable.
    preferred_order = [
        "Pluvial", "Fluvial", "Compound", "Coastal", "Compound coastal",
        "Flash flood", "Landslide-related", "Flash + landslide",
        "Dam/reservoir", "Unspecified", "Unknown",
    ]

    extra_causes = [c for c in sorted(present_dominant_causes) if c not in preferred_order]
    causes = preferred_order + extra_causes

    color_dict = get_cause_color_dict(causes + ["No IFI record"])

    plot_gdf["_cause_color"] = plot_gdf["_dominant_plot"].map(color_dict)
    plot_gdf.loc[plot_gdf["n_events"] == 0, "_cause_color"] = color_dict["No IFI record"]

    plot_gdf.plot(
        ax=ax,
        color=plot_gdf["_cause_color"],
        edgecolor="white",
        linewidth=0.09,
        zorder=2,
    )

    weak = plot_gdf[(plot_gdf["n_events"] > 0) & (plot_gdf["dominant_cause_share"] < 0.50)]
    if len(weak) > 0:
        weak.boundary.plot(ax=ax, color="black", linewidth=0.24, alpha=0.38, zorder=3)

    legend_handles = [
        Patch(facecolor=color_dict[c], edgecolor="black", linewidth=0.55, label=c)
        for c in causes
    ]
    legend_handles.append(Patch(facecolor=color_dict["No IFI record"], edgecolor="black", linewidth=0.55, label="No IFI record"))

    leg = ax.legend(
        handles=legend_handles,
        loc="lower left",
        bbox_to_anchor=(0.02, -0.015),
        frameon=True,
        ncol=2,
        title="Dominant cause",
        borderpad=0.7,
        handlelength=1.3,
        columnspacing=0.8,
    )
    leg.get_frame().set_edgecolor("black")
    leg.get_frame().set_linewidth(1.0)
    leg.get_frame().set_alpha(0.97)


def plot_bivariate_hotspot_map(ax, gdf):
    """Panel D: bivariate map combining event frequency and p95 hazard score."""

    style_map_axis(ax)
    add_panel_label(ax, "D")

    ax.set_title("Frequency–severity flood hotspot classes", fontweight="bold", pad=8)

    plot_gdf = gdf.copy()

    valid = (
        (plot_gdf["n_events"] > 0) &
        (plot_gdf["n_scored_events"] >= MIN_SCORED_EVENTS_FOR_HAZARD_MAP) &
        (plot_gdf["p95_hazard_score"].notna())
    )

    plot_gdf["_freq_class"] = np.nan
    plot_gdf["_sev_class"] = np.nan

    plot_gdf.loc[valid, "_freq_class"] = classify_tertiles(plot_gdf.loc[valid, "n_events"])
    plot_gdf.loc[valid, "_sev_class"] = classify_tertiles(plot_gdf.loc[valid, "p95_hazard_score"])

    color_matrix = {
        (0, 0): "#e8e8e8",
        (1, 0): "#ace4e4",
        (2, 0): "#5ac8c8",
        (0, 1): "#dfb0d6",
        (1, 1): "#a5add3",
        (2, 1): "#5698b9",
        (0, 2): "#be64ac",
        (1, 2): "#8c62aa",
        (2, 2): "#3b4994",
    }

    def assign_bivar_color(row):
        if pd.isna(row["_freq_class"]) or pd.isna(row["_sev_class"]):
            return "#f0f0f0"
        return color_matrix[(int(row["_freq_class"]), int(row["_sev_class"]))]

    plot_gdf["_bivar_color"] = plot_gdf.apply(assign_bivar_color, axis=1)

    plot_gdf.plot(
        ax=ax,
        color=plot_gdf["_bivar_color"],
        edgecolor="white",
        linewidth=0.09,
        zorder=2,
    )

    add_bivariate_legend(ax, color_matrix)


def plot_state_stacked_bar(ax, event_district):
    """Panel E: state-level 100% stacked bars by cause."""

    add_panel_label(ax, "E")

    ax.set_title("State-level flood-cause composition", fontweight="bold", pad=8)

    data = event_district.copy()

    # This intentionally counts event-district records, not unique event IDs.
    # It measures the spatial footprint of classified events inside each state.
    state_cause = (
        data
        .groupby(["_state_name", "_cause_plot"])
        .size()
        .rename("n_event_district_records")
        .reset_index()
    )

    state_total = (
        state_cause
        .groupby("_state_name")["n_event_district_records"]
        .sum()
        .sort_values(ascending=False)
    )

    top_states = state_total.head(TOP_N_STATES_FOR_BAR).index.tolist()
    plot_data = state_cause[state_cause["_state_name"].isin(top_states)].copy()

    table = plot_data.pivot_table(
        index="_state_name",
        columns="_cause_plot",
        values="n_event_district_records",
        fill_value=0,
        aggfunc="sum",
    )

    table = table.loc[top_states]
    percent = table.div(table.sum(axis=1), axis=0) * 100.0

    preferred = [
        "Pluvial", "Unspecified", "Fluvial", "Compound", "Flash flood",
        "Landslide-related", "Unknown", "Coastal", "Compound coastal",
        "Flash + landslide", "Dam/reservoir",
    ]
    cause_order = [c for c in preferred if c in percent.columns] + [c for c in percent.columns if c not in preferred]
    percent = percent[cause_order]

    color_dict = get_cause_color_dict(cause_order)

    y = np.arange(len(percent.index))
    left = np.zeros(len(percent.index))

    for cause in cause_order:
        vals = percent[cause].values
        ax.barh(
            y,
            vals,
            left=left,
            color=color_dict[cause],
            edgecolor="white",
            linewidth=0.45,
            height=0.78,
            label=cause,
        )
        left += vals

    labels = [f"{state}  (n={int(table.loc[state].sum()):,})" for state in percent.index]

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()

    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of event-district records (%)", fontsize=12.5)
    ax.grid(axis="x", color="0.84", linewidth=0.85)
    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    leg = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.075),
        ncol=3,
        frameon=True,
        title="Colors = classified flood-cause groups",
        columnspacing=0.9,
        handlelength=1.35,
        borderpad=0.75,
    )
    leg.get_frame().set_edgecolor("black")
    leg.get_frame().set_linewidth(0.9)
    leg.get_frame().set_alpha(0.98)


def plot_state_reference_map(ax, states, country):
    """Panel G: state reference map with state names."""

    style_map_axis(ax)
    add_panel_label(ax, "G")

    ax.set_title("State reference map", fontweight="bold", pad=8)

    if states is None:
        ax.text(0.5, 0.5, "State shapefile not found", ha="center", va="center", transform=ax.transAxes)
        return

    state_name_col = find_first_existing_column(
        states,
        ["NAME_1", "ST_NM", "STATE", "State_Name", "STATE_NAME", "NAME", "state_name", "stname", "state"],
        required=False,
        label="state name in state shapefile",
    )

    if state_name_col is None:
        state_name_col = states.columns[0]
        warnings.warn(f"Could not identify state-name column. Using first column: {state_name_col}")

    if country is not None:
        country.plot(ax=ax, color="#f7f7f7", edgecolor="black", linewidth=0.8, zorder=1)

    states.plot(ax=ax, color="#f7fbff", edgecolor="0.30", linewidth=0.75, zorder=2)

    # Add state labels at representative points. The white halo makes text readable.
    label_gdf = states.copy()
    label_gdf["_label_point"] = label_gdf.geometry.representative_point()

    for _, row in label_gdf.iterrows():
        geom = row["_label_point"]
        if geom is None or geom.is_empty:
            continue

        state_name = str(row[state_name_col]).strip()
        if state_name.lower() in ["nan", "none", ""]:
            continue

        label = wrap_state_label(state_name, width=13)

        # Smaller font for very small states/territories and northeast labels.
        fontsize = 8.0
        if len(state_name) > 18:
            fontsize = 7.0
        if row.geometry.area < label_gdf.geometry.area.quantile(0.18):
            fontsize = 6.2

        ax.text(
            geom.x,
            geom.y,
            label,
            ha="center",
            va="center",
            fontsize=fontsize,
            color="black",
            zorder=5,
            path_effects=[pe.withStroke(linewidth=3.3, foreground="white")],
        )


def plot_monthly_heatmap(fig, ax, event_district):
    """Panel F: monthly seasonality heatmap by cause group."""

    add_panel_label(ax, "F")

    ax.set_title("Monthly seasonality of flood-cause groups", fontweight="bold", pad=10)

    data = event_district[event_district["_month"].between(1, 12)].copy()

    monthly = (
        data
        .groupby(["_cause_plot", "_month"])
        .size()
        .rename("n_event_district_records")
        .reset_index()
    )

    table = monthly.pivot_table(
        index="_cause_plot",
        columns="_month",
        values="n_event_district_records",
        fill_value=0,
        aggfunc="sum",
    )

    for m in range(1, 13):
        if m not in table.columns:
            table[m] = 0

    table = table[range(1, 13)]
    table = table.loc[table.sum(axis=1).sort_values(ascending=False).index]

    # Row-normalized percentage to show seasonal concentration independent of cause abundance.
    table_pct = table.div(table.sum(axis=1).replace(0, np.nan), axis=0) * 100.0
    table_pct = table_pct.fillna(0)

    vmax = np.nanpercentile(table_pct.values, 98) if np.isfinite(table_pct.values).any() else 100
    vmax = max(vmax, 20)

    im = ax.imshow(
        table_pct.values,
        aspect="auto",
        interpolation="nearest",
        cmap="magma",
        vmin=0,
        vmax=vmax,
    )

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    ax.set_xticks(np.arange(12))
    ax.set_xticklabels(month_labels, fontsize=12)

    ax.set_yticks(np.arange(len(table_pct.index)))
    ax.set_yticklabels(table_pct.index, fontsize=12)

    ax.set_xlabel("Event start month", fontsize=13)
    ax.set_ylabel("Cause group", fontsize=13)

    ax.set_xticks(np.arange(-0.5, 12, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(table_pct.index), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.95)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Labels: black text inside semi-transparent white boxes.
    for i in range(table_pct.shape[0]):
        for j in range(12):
            val = float(table_pct.values[i, j])
            if val <= 0:
                continue
            ax.text(
                j,
                i,
                f"{val:.0f}",
                ha="center",
                va="center",
                fontsize=9.0,
                fontweight="bold",
                color="black",
                bbox=dict(
                    boxstyle="round,pad=0.16",
                    facecolor="white",
                    edgecolor="none",
                    alpha=0.82,
                ),
                zorder=10,
            )

    cbar = fig.colorbar(im, ax=ax, orientation="vertical", fraction=0.018, pad=0.012)
    cbar.set_label("Monthly share within cause group (%)", fontsize=11.5)
    cbar.ax.tick_params(labelsize=10, width=1.1, length=3.5)
    cbar.outline.set_linewidth(1.45)


# ============================================================
# 7. Main figure
# ============================================================

def create_main_atlas(gdf, event_district, states, country):
    """Create one large multi-panel figure."""

    print("\n============================================================")
    print("Creating main IFI flood hazard atlas, v3")
    print("============================================================")

    states_plot = project_gdf(states, name="states") if states is not None else None
    country_plot = project_gdf(country, name="country") if country is not None else None

    fig = plt.figure(figsize=(31, 18.5), constrained_layout=False)

    gs = fig.add_gridspec(
        nrows=3,
        ncols=4,
        height_ratios=[1.0, 1.0, 0.78],
        width_ratios=[1.0, 1.0, 1.34, 0.92],
        hspace=0.23,
        wspace=0.15,
    )

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])
    ax_e = fig.add_subplot(gs[0:2, 2])
    ax_g = fig.add_subplot(gs[0:2, 3])
    ax_f = fig.add_subplot(gs[2, :])

    plot_event_frequency_map(fig, ax_a, gdf)
    plot_hazard_map(fig, ax_b, gdf)
    plot_dominant_cause_map(ax_c, gdf)
    plot_bivariate_hotspot_map(ax_d, gdf)
    plot_state_stacked_bar(ax_e, event_district)
    plot_state_reference_map(ax_g, states_plot, country_plot)
    plot_monthly_heatmap(fig, ax_f, event_district)

    fig.suptitle(
        "IFI flood-event frequency, severity, and classified flood causes across India",
        fontsize=22,
        fontweight="bold",
        y=0.985,
    )

    fig.subplots_adjust(left=0.030, right=0.992, top=0.945, bottom=0.070, hspace=0.23, wspace=0.15)

    fig.savefig(OUT_FIG_PNG, bbox_inches="tight")
    fig.savefig(OUT_FIG_PDF, bbox_inches="tight")
    fig.savefig(OUT_FIG_SVG, bbox_inches="tight", format="svg")

    print(f"Saved figure PNG: {OUT_FIG_PNG}")
    print(f"Saved figure PDF: {OUT_FIG_PDF}")
    print(f"Saved figure SVG: {OUT_FIG_SVG}")

    plt.close(fig)


# ============================================================
# 8. Main execution
# ============================================================

def main():
    setup_plot_style()

    df_valid, event_district, districts, states, country = load_and_prepare_data()

    district_summary = build_district_summary(event_district=event_district, districts=districts)

    gdf = merge_summary_with_geometry(summary=district_summary, districts=districts)

    create_main_atlas(gdf=gdf, event_district=event_district, states=states, country=country)

    print("\n============================================================")
    print("Done")
    print("============================================================")
    print(f"Output folder:\n{OUT_DIR}")
    print(f"Main atlas PNG:\n{OUT_FIG_PNG}")
    print(f"Main atlas PDF:\n{OUT_FIG_PDF}")
    print(f"District summary CSV:\n{OUT_DISTRICT_SUMMARY}")


if __name__ == "__main__":
    main()
