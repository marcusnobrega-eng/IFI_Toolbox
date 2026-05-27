#!/usr/bin/env python3
"""Build browser-ready data assets for the IFI dashboard."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "Districts_Shapefile" / "GADM41_IND2_Districts.shp").exists():
            return parent
    raise FileNotFoundError("Could not locate IFI_Toolbox repository root from build_data.py")


ROOT = find_repo_root()
APP_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = APP_DIR / "data"

SOURCE_DATA = ROOT / "India_Flood_Inventory_v7_corrected_combined_exploded_added_numericalMetrics.xlsx"
DISTRICT_SHP = ROOT / "Districts_Shapefile" / "GADM41_IND2_Districts.shp"

MIN_SCORED_EVENTS = 3
SIMPLIFY_TOLERANCE_DEGREES = 0.012
USD_INR_2026 = 96.0622
INR_PER_LAKH = 100_000
HECTARE_TO_KM2 = 0.01

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CAUSE_ORDER = [
    "Pluvial",
    "Fluvial",
    "Compound",
    "Coastal",
    "Compound coastal",
    "Flash flood",
    "Landslide-related",
    "Flash + landslide",
    "Dam/reservoir",
    "Unspecified",
    "Unknown",
]

CAUSE_COLORS = {
    "Pluvial": "#2f80ed",
    "Fluvial": "#1f9d78",
    "Compound": "#7b61ff",
    "Coastal": "#00a7b5",
    "Compound coastal": "#2d9cdb",
    "Flash flood": "#f2994a",
    "Landslide-related": "#a56b43",
    "Flash + landslide": "#d46a6a",
    "Dam/reservoir": "#6f4e37",
    "Unspecified": "#9aa4ad",
    "Unknown": "#59636d",
    "No IFI record": "#d8dde3",
}

METRIC_SPECS = {
    "fatalities": {
        "label": "Human fatalities",
        "unit": "people",
        "columns": ["human_fatality_num_v7", "human_fatality_num_v6", "Human fatality"],
        "flags": ["human_fatality_num_v7_above_sanity_cap_v7", "human_fatality_num_v6_above_sanity_cap_v6"],
        "additive": True,
    },
    "injured": {
        "label": "Human injured",
        "unit": "people",
        "columns": ["human_injured_num_v7", "human_injured_num_v6", "Human injured"],
        "flags": ["human_injured_num_v7_above_sanity_cap_v7", "human_injured_num_v6_above_sanity_cap_v6"],
        "additive": True,
    },
    "displaced": {
        "label": "Human displaced",
        "unit": "people",
        "columns": ["human_displaced_num_v7", "human_displaced_num_v6", "Human Displaced"],
        "flags": ["human_displaced_num_v7_above_sanity_cap_v7", "human_displaced_num_v6_above_sanity_cap_v6"],
        "additive": True,
    },
    "people_affected": {
        "label": "People affected",
        "unit": "people",
        "columns": ["extracted_people_affected_v7", "extracted_people_affected_v6"],
        "flags": ["extracted_people_affected_v7_above_sanity_cap_v7", "extracted_people_affected_v6_above_sanity_cap_v6"],
        "additive": True,
    },
    "houses_damaged": {
        "label": "Houses damaged",
        "unit": "structures",
        "columns": ["extracted_houses_damaged_total_v7", "extracted_houses_damaged_total_v6"],
        "flags": [
            "extracted_houses_damaged_total_v7_above_sanity_cap_v7",
            "extracted_houses_damaged_total_v6_above_sanity_cap_v6",
        ],
        "additive": True,
    },
    "crop_area_ha": {
        "label": "Crop area affected",
        "unit": "ha",
        "columns": ["extracted_crop_area_ha_v7", "extracted_crop_area_ha_v6"],
        "flags": ["extracted_crop_area_ha_v7_above_sanity_cap_v7", "extracted_crop_area_ha_v6_above_sanity_cap_v6"],
        "additive": True,
    },
    "road_length_km": {
        "label": "Road damaged",
        "unit": "km",
        "columns": ["extracted_road_length_damaged_km_v7", "extracted_road_length_damaged_km_v6"],
        "flags": [
            "extracted_road_length_damaged_km_v7_above_sanity_cap_v7",
            "extracted_road_length_damaged_km_v6_above_sanity_cap_v6",
        ],
        "additive": True,
    },
    "bridges_damaged": {
        "label": "Bridges damaged",
        "unit": "count",
        "columns": ["extracted_bridges_damaged_count_v7", "extracted_bridges_damaged_count_v6"],
        "flags": [
            "extracted_bridges_damaged_count_v7_above_sanity_cap_v7",
            "extracted_bridges_damaged_count_v6_above_sanity_cap_v6",
        ],
        "additive": True,
    },
    "loss_inr_lakh": {
        "label": "Monetary loss",
        "unit": "INR lakh",
        "columns": ["extracted_monetary_loss_inr_lakh_v7", "extracted_monetary_loss_inr_lakh_v6"],
        "flags": [
            "extracted_monetary_loss_inr_lakh_v7_above_sanity_cap_v7",
            "extracted_monetary_loss_inr_lakh_v6_above_sanity_cap_v6",
        ],
        "additive": True,
    },
    "duration_days": {
        "label": "Duration",
        "unit": "days",
        "columns": ["duration_days_num_v7", "duration_days_num_v6", "Duration(Days)"],
        "flags": ["duration_days_num_v7_above_sanity_cap_v7", "duration_days_num_v6_above_sanity_cap_v6"],
        "additive": False,
    },
    "rainfall_max_mm": {
        "label": "Maximum rainfall",
        "unit": "mm",
        "columns": ["extracted_rainfall_max_mm_v7", "extracted_rainfall_max_mm_v6"],
        "flags": ["extracted_rainfall_max_mm_v7_above_sanity_cap_v7", "extracted_rainfall_max_mm_v6_above_sanity_cap_v6"],
        "additive": False,
    },
    "flood_depth_max_m": {
        "label": "Maximum flood depth",
        "unit": "m",
        "columns": ["extracted_flood_depth_max_m_v7", "extracted_flood_depth_max_m_v6"],
        "flags": [
            "extracted_flood_depth_max_m_v7_above_sanity_cap_v7",
            "extracted_flood_depth_max_m_v6_above_sanity_cap_v6",
        ],
        "additive": False,
    },
    "inundation_hours": {
        "label": "Inundation duration",
        "unit": "hours",
        "columns": ["extracted_inundation_duration_hours_v7", "extracted_inundation_duration_hours_v6"],
        "flags": [
            "extracted_inundation_duration_hours_v7_above_sanity_cap_v7",
            "extracted_inundation_duration_hours_v6_above_sanity_cap_v6",
        ],
        "additive": False,
    },
}


def find_column(df: pd.DataFrame, candidates: list[str], required: bool = False) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    if required:
        raise ValueError(f"Missing required column. Tried: {candidates}")
    return None


def parse_boolean(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y", "t"])


def clean_text(series: pd.Series, fill_value: str = "Unknown") -> pd.Series:
    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.replace({"": fill_value, "nan": fill_value, "None": fill_value, "NONE": fill_value})
    return cleaned.fillna(fill_value)


def format_cause(value: object) -> str:
    label_map = {
        "pluvial": "Pluvial",
        "fluvial": "Fluvial",
        "compound": "Compound",
        "compound_pluvial_fluvial": "Compound",
        "compound_coastal_rainfall_or_fluvial": "Compound coastal",
        "coastal": "Coastal",
        "compound coastal": "Compound coastal",
        "flash_flood": "Flash flood",
        "flash flood": "Flash flood",
        "flash_flood_or_cloudburst": "Flash flood",
        "landslide_related": "Landslide-related",
        "landslide-related": "Landslide-related",
        "compound_flash_flood_landslide": "Flash + landslide",
        "flash + landslide": "Flash + landslide",
        "dam_or_reservoir_related_fluvial": "Dam/reservoir",
        "dam_reservoir": "Dam/reservoir",
        "dam/reservoir": "Dam/reservoir",
        "unspecified": "Unspecified",
        "unspecified_flood": "Unspecified",
        "unknown": "Unknown",
        "unknown_or_insufficient_text": "Unknown",
    }
    text = str(value).strip()
    if not text or text.lower() in ["nan", "none"]:
        return "Unknown"
    return label_map.get(text.lower(), text.replace("_", " ").title())


def finite_or_none(value: object, digits: int | None = None) -> float | int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if digits is not None:
        number = round(number, digits)
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return number


def quantile_or_nan(series: pd.Series, q: float) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return np.nan
    return float(np.nanpercentile(clean, q))


def first_non_null(series: pd.Series):
    clean = series.dropna()
    if clean.empty:
        return np.nan
    return clean.iloc[0]


def sum_or_nan(series: pd.Series) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return np.nan
    return float(clean.sum())


def classify_tertiles(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=series.index)
    clean = values.dropna()
    if clean.empty:
        return out
    if clean.nunique() == 1:
        out.loc[clean.index] = 1
        return out
    try:
        out.loc[clean.index] = pd.qcut(clean.rank(method="first"), q=3, labels=[0, 1, 2]).astype(float)
    except ValueError:
        q1, q2 = np.nanpercentile(clean, [33.333, 66.667])
        out.loc[clean.index] = clean.map(lambda x: 0 if x <= q1 else (1 if x <= q2 else 2))
    return out


def normalize_percentile(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    if clean.dropna().empty:
        return pd.Series(0.0, index=series.index)
    return clean.rank(pct=True).fillna(0.0)


def add_si_and_usd_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add display-ready SI and 2026 USD fields while keeping source fields."""

    if "crop_area_ha_apportioned_sum" in df.columns:
        df["crop_area_km2_apportioned_sum"] = df["crop_area_ha_apportioned_sum"] * HECTARE_TO_KM2
    if "loss_inr_lakh_apportioned_sum" in df.columns:
        df["loss_2026_usd_apportioned_sum"] = df["loss_inr_lakh_apportioned_sum"] * INR_PER_LAKH / USD_INR_2026
    return df


def clean_metric_series(df: pd.DataFrame, spec: dict) -> tuple[pd.Series, str | None, str | None, int]:
    col = find_column(df, spec["columns"])
    if col is None:
        return pd.Series(np.nan, index=df.index), None, None, 0

    series = pd.to_numeric(df[col], errors="coerce")
    series = series.mask(series < 0)

    flag_col = find_column(df, spec.get("flags", []))
    flagged_count = 0
    if flag_col:
        flagged = parse_boolean(df[flag_col])
        flagged_count = int(flagged.sum())
        series = series.mask(flagged)

    return series, col, flag_col, flagged_count


def prepare_event_district(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    gid_col = find_column(df, ["GID_2", "gadm_gid_2"], required=True)
    district_col = find_column(df, ["NAME_2", "District", "district"])
    state_col = find_column(df, ["NAME_1", "State", "state"])
    event_col = find_column(df, ["UEI", "ID", "Event_ID", "event_id", "event_uid", "DisNo.", "disaster_id"])
    if event_col is None:
        df["_event_id_internal"] = np.arange(len(df))
        event_col = "_event_id_internal"

    hazard_col = find_column(
        df,
        [
            "flood_hazard_score_0_100_v7",
            "flood_hazard_score_0_100_v6",
            "flood_hazard_score_0_100_v5",
            "flood_hazard_score_0_100",
            "hazard_score_0_100",
            "flood_hazard_score",
        ],
    )
    hazard_extended_col = find_column(
        df,
        [
            "flood_hazard_score_extended_0_100_v7",
            "flood_hazard_score_extended_0_100_v6",
            "flood_hazard_score_extended_0_100_v5",
        ],
    )
    cause_col = find_column(
        df,
        [
            "event_cause_map_group_v7",
            "event_cause_map_group_v6",
            "event_cause_map_group_v5",
            "event_cause_map_group",
            "event_cause_primary_v7",
            "event_cause_primary_v6",
            "event_cause_primary_v5",
            "event_cause_primary",
            "Main Cause",
        ],
    )
    confidence_col = find_column(
        df,
        [
            "event_cause_confidence_v7",
            "event_cause_confidence_v6",
            "event_cause_confidence_v5",
            "event_cause_confidence",
            "cause_confidence",
        ],
    )
    year_col = find_column(df, ["start_year_v7", "start_year_v6", "start_year_v5", "start_year"])
    month_col = find_column(df, ["start_month_v7", "start_month_v6", "start_month_v5", "start_month"])
    start_date_col = find_column(df, ["Start_Date_parsed_v7", "Start_Date_parsed_v6", "Start_Date_parsed_v5", "Start Date"])
    location_col = find_column(df, ["Location", "location"])
    source_col = find_column(df, ["Event Source", "Event_Source", "source"])
    severity_col = find_column(df, ["Severity", "severity"])
    match_valid_col = find_column(
        df,
        [
            "gadm_match_valid_for_metric_v7",
            "gadm_match_valid_for_metric_v6",
            "gadm_match_valid_for_metric_v5",
            "gadm_match_valid_for_metric",
        ],
    )

    gids = df[gid_col].astype(str).str.strip()
    valid = gids.notna() & (gids != "") & (gids.str.lower() != "nan")
    if match_valid_col:
        valid = valid & parse_boolean(df[match_valid_col])

    valid_df = df.loc[valid].copy()
    valid_df["_GID_2"] = valid_df[gid_col].astype(str).str.strip()
    valid_df["_event_id"] = clean_text(valid_df[event_col], fill_value="Unknown event")
    valid_df["_district_name"] = clean_text(valid_df[district_col], "Unknown district") if district_col else "Unknown district"
    valid_df["_state_name"] = clean_text(valid_df[state_col], "Unknown state") if state_col else "Unknown state"
    valid_df["_cause"] = clean_text(valid_df[cause_col], "Unknown").map(format_cause) if cause_col else "Unknown"
    valid_df["_confidence"] = clean_text(valid_df[confidence_col], "unknown").str.lower() if confidence_col else "unknown"
    valid_df["_hazard"] = pd.to_numeric(valid_df[hazard_col], errors="coerce") if hazard_col else np.nan
    valid_df["_hazard_extended"] = pd.to_numeric(valid_df[hazard_extended_col], errors="coerce") if hazard_extended_col else np.nan
    valid_df["_year"] = pd.to_numeric(valid_df[year_col], errors="coerce") if year_col else np.nan
    valid_df["_month"] = pd.to_numeric(valid_df[month_col], errors="coerce") if month_col else np.nan
    valid_df["_location"] = clean_text(valid_df[location_col], "") if location_col else ""
    valid_df["_source"] = clean_text(valid_df[source_col], "") if source_col else ""
    valid_df["_severity_text"] = clean_text(valid_df[severity_col], "") if severity_col else ""
    valid_df["_start_date_raw"] = clean_text(valid_df[start_date_col], "") if start_date_col else ""

    metric_columns = {}
    for key, spec in METRIC_SPECS.items():
        series, col, flag_col, flagged_count = clean_metric_series(valid_df, spec)
        valid_df[f"_{key}"] = series
        metric_columns[key] = {"column": col, "flag_column": flag_col, "flagged_values_removed": flagged_count}

    event_district = (
        valid_df.sort_values(["_GID_2", "_event_id"])
        .drop_duplicates(subset=["_GID_2", "_event_id"], keep="first")
        .copy()
    )
    districts_touched = event_district.groupby("_event_id")["_GID_2"].nunique().rename("_districts_touched")
    event_district = event_district.merge(districts_touched, on="_event_id", how="left")
    event_district["_districts_touched"] = event_district["_districts_touched"].replace(0, 1).fillna(1)

    for key, spec in METRIC_SPECS.items():
        if spec["additive"]:
            event_district[f"_{key}_apportioned"] = event_district[f"_{key}"] / event_district["_districts_touched"]

    columns_used = {
        "district_id": gid_col,
        "district_name": district_col,
        "state_name": state_col,
        "event_id": event_col,
        "hazard": hazard_col,
        "hazard_extended": hazard_extended_col,
        "cause": cause_col,
        "confidence": confidence_col,
        "year": year_col,
        "month": month_col,
        "start_date": start_date_col,
        "match_valid": match_valid_col,
        "metrics": metric_columns,
    }
    return event_district, columns_used


def build_event_unique(event_district: pd.DataFrame) -> pd.DataFrame:
    grouped = {
        "_year": ("_year", first_non_null),
        "_month": ("_month", first_non_null),
        "_cause": ("_cause", first_non_null),
        "_confidence": ("_confidence", first_non_null),
        "_hazard": ("_hazard", "mean"),
        "_hazard_p95": ("_hazard", lambda x: quantile_or_nan(x, 95)),
        "_districts_touched": ("_GID_2", "nunique"),
    }
    for key in METRIC_SPECS:
        grouped[f"_{key}"] = (f"_{key}", "max")
    return event_district.groupby("_event_id").agg(**grouped).reset_index()


def build_district_summary(event_district: pd.DataFrame, districts: gpd.GeoDataFrame) -> pd.DataFrame:
    grouped = event_district.groupby("_GID_2")
    summary = grouped.agg(
        n_events=("_event_id", "nunique"),
        n_event_district_records=("_event_id", "size"),
        n_scored_events=("_hazard", lambda x: int(pd.to_numeric(x, errors="coerce").notna().sum())),
        mean_hazard_score=("_hazard", "mean"),
        median_hazard_score=("_hazard", "median"),
        p95_hazard_score=("_hazard", lambda x: quantile_or_nan(x, 95)),
        max_hazard_score=("_hazard", "max"),
        mean_extended_hazard_score=("_hazard_extended", "mean"),
        first_year=("_year", "min"),
        last_year=("_year", "max"),
        active_years=("_year", lambda x: int(pd.to_numeric(x, errors="coerce").dropna().nunique())),
        mean_duration_days=("_duration_days", "mean"),
        p95_duration_days=("_duration_days", lambda x: quantile_or_nan(x, 95)),
        mean_rainfall_max_mm=("_rainfall_max_mm", "mean"),
        max_flood_depth_m=("_flood_depth_max_m", "max"),
        high_confidence_count=("_confidence", lambda x: int(x.astype(str).str.lower().eq("high").sum())),
        low_confidence_count=("_confidence", lambda x: int(x.astype(str).str.lower().eq("low").sum())),
    ).reset_index()

    for key, spec in METRIC_SPECS.items():
        if spec["additive"]:
            summary[f"{key}_apportioned_sum"] = grouped[f"_{key}_apportioned"].sum(min_count=1).values
    summary = add_si_and_usd_columns(summary)

    counts = (
        event_district.groupby(["_GID_2", "_cause"])["_event_id"]
        .nunique()
        .rename("cause_event_count")
        .reset_index()
    )
    dominant = (
        counts.sort_values(["_GID_2", "cause_event_count", "_cause"], ascending=[True, False, True])
        .drop_duplicates("_GID_2")
        .rename(columns={"_cause": "dominant_cause", "cause_event_count": "dominant_cause_count"})
    )
    summary = summary.merge(dominant[["_GID_2", "dominant_cause", "dominant_cause_count"]], on="_GID_2", how="left")

    names = districts[["GID_2", "NAME_2", "NAME_1"]].rename(
        columns={"GID_2": "_GID_2", "NAME_2": "district", "NAME_1": "state"}
    )
    summary = names.merge(summary, on="_GID_2", how="left")
    summary["n_events"] = summary["n_events"].fillna(0).astype(int)
    summary["n_event_district_records"] = summary["n_event_district_records"].fillna(0).astype(int)
    summary["n_scored_events"] = summary["n_scored_events"].fillna(0).astype(int)
    summary["dominant_cause"] = summary["dominant_cause"].fillna("No IFI record")
    summary["dominant_cause_count"] = summary["dominant_cause_count"].fillna(0).astype(int)
    summary["dominant_cause_share"] = np.where(
        summary["n_events"] > 0, summary["dominant_cause_count"] / summary["n_events"], 0
    )
    summary["high_confidence_share"] = np.where(
        summary["n_event_district_records"] > 0,
        summary["high_confidence_count"].fillna(0) / summary["n_event_district_records"],
        0,
    )
    summary["low_confidence_share"] = np.where(
        summary["n_event_district_records"] > 0,
        summary["low_confidence_count"].fillna(0) / summary["n_event_district_records"],
        0,
    )

    valid_hotspots = (
        (summary["n_events"] > 0)
        & (summary["n_scored_events"] >= MIN_SCORED_EVENTS)
        & summary["p95_hazard_score"].notna()
    )
    summary["freq_class"] = np.nan
    summary["severity_class"] = np.nan
    summary.loc[valid_hotspots, "freq_class"] = classify_tertiles(summary.loc[valid_hotspots, "n_events"])
    summary.loc[valid_hotspots, "severity_class"] = classify_tertiles(summary.loc[valid_hotspots, "p95_hazard_score"])
    summary["hotspot_score"] = np.where(
        valid_hotspots,
        (summary["freq_class"].fillna(0) + 1) * (summary["severity_class"].fillna(0) + 1),
        0,
    )

    fatality_pct = normalize_percentile(summary["fatalities_apportioned_sum"])
    event_pct = normalize_percentile(summary["n_events"])
    hazard_component = pd.to_numeric(summary["p95_hazard_score"], errors="coerce").fillna(0) / 100.0
    summary["priority_score"] = (100 * (0.42 * event_pct + 0.38 * hazard_component + 0.20 * fatality_pct)).round(1)
    summary.loc[summary["n_events"] == 0, "priority_score"] = 0
    summary["event_rank"] = summary["n_events"].rank(method="min", ascending=False).fillna(len(summary)).astype(int)
    summary["hazard_rank"] = summary["p95_hazard_score"].rank(method="min", ascending=False).fillna(len(summary)).astype(int)
    summary["priority_rank"] = summary["priority_score"].rank(method="min", ascending=False).fillna(len(summary)).astype(int)

    return summary


def build_state_summary(summary: pd.DataFrame, event_district: pd.DataFrame) -> list[dict]:
    state_shell = summary.groupby("state").agg(
        districts=("district", "count"),
        districts_with_records=("n_events", lambda x: int((x > 0).sum())),
    )

    grouped = event_district.groupby("_state_name")
    state = grouped.agg(
        n_events=("_event_id", "nunique"),
        n_event_district_records=("_event_id", "size"),
        mean_hazard_score=("_hazard", "mean"),
        p95_hazard_score=("_hazard", lambda x: quantile_or_nan(x, 95)),
        first_year=("_year", "min"),
        last_year=("_year", "max"),
    )
    for key, spec in METRIC_SPECS.items():
        if spec["additive"]:
            state[f"{key}_apportioned_sum"] = grouped[f"_{key}_apportioned"].sum(min_count=1)

    state = state_shell.merge(state, left_index=True, right_index=True, how="left").fillna({"n_events": 0, "n_event_district_records": 0})

    cause_counts = (
        event_district.groupby(["_state_name", "_cause"])
        .size()
        .rename("n_event_district_records")
        .reset_index()
    )
    cause_lookup = {}
    for state_name, chunk in cause_counts.groupby("_state_name"):
        ordered = chunk.sort_values("n_event_district_records", ascending=False)
        total = ordered["n_event_district_records"].sum()
        cause_lookup[state_name] = {
            row["_cause"]: {
                "records": int(row["n_event_district_records"]),
                "events": int(row["n_event_district_records"]),
                "share": finite_or_none(row["n_event_district_records"] / total, 4),
            }
            for _, row in ordered.iterrows()
            if total > 0
        }

    out = []
    for state_name, row in state.reset_index().rename(columns={"index": "state"}).iterrows():
        name = row["state"]
        cause_obj = cause_lookup.get(name, {})
        dominant = max(cause_obj.items(), key=lambda item: item[1]["records"])[0] if cause_obj else "No IFI record"
        item = {
            "state": name,
            "districts": int(row["districts"]),
            "districts_with_records": int(row["districts_with_records"]),
            "n_events": int(row["n_events"]) if pd.notna(row["n_events"]) else 0,
            "n_event_district_records": int(row["n_event_district_records"]) if pd.notna(row["n_event_district_records"]) else 0,
            "mean_hazard_score": finite_or_none(row["mean_hazard_score"], 2),
            "p95_hazard_score": finite_or_none(row["p95_hazard_score"], 2),
            "first_year": finite_or_none(row["first_year"]),
            "last_year": finite_or_none(row["last_year"]),
            "dominant_cause": dominant,
            "cause_counts": cause_obj,
        }
        for key, spec in METRIC_SPECS.items():
            if spec["additive"]:
                item[f"{key}_apportioned_sum"] = finite_or_none(row.get(f"{key}_apportioned_sum"), 2)
        if item.get("crop_area_ha_apportioned_sum") is not None:
            item["crop_area_km2_apportioned_sum"] = finite_or_none(
                item["crop_area_ha_apportioned_sum"] * HECTARE_TO_KM2,
                3,
            )
        if item.get("loss_inr_lakh_apportioned_sum") is not None:
            item["loss_2026_usd_apportioned_sum"] = finite_or_none(
                item["loss_inr_lakh_apportioned_sum"] * INR_PER_LAKH / USD_INR_2026,
                2,
            )
        out.append(item)
    return sorted(out, key=lambda x: (x["n_event_district_records"], x["n_events"]), reverse=True)


def build_cause_summary(event_district: pd.DataFrame) -> list[dict]:
    grouped = event_district.groupby("_cause")
    cause = grouped.agg(
        n_events=("_event_id", "nunique"),
        n_event_district_records=("_event_id", "size"),
        mean_hazard_score=("_hazard", "mean"),
        p95_hazard_score=("_hazard", lambda x: quantile_or_nan(x, 95)),
        high_confidence_share=("_confidence", lambda x: float(x.astype(str).str.lower().eq("high").mean())),
    ).reset_index()
    total = cause["n_event_district_records"].sum()
    out = []
    for _, row in cause.sort_values("n_event_district_records", ascending=False).iterrows():
        out.append(
            {
                "cause": row["_cause"],
                "n_events": int(row["n_events"]),
                "n_event_district_records": int(row["n_event_district_records"]),
                "record_share": finite_or_none(row["n_event_district_records"] / total, 4) if total else 0,
                "mean_hazard_score": finite_or_none(row["mean_hazard_score"], 2),
                "p95_hazard_score": finite_or_none(row["p95_hazard_score"], 2),
                "high_confidence_share": finite_or_none(row["high_confidence_share"], 4),
            }
        )
    return out


def build_monthly_summary(event_district: pd.DataFrame) -> dict:
    valid = event_district[event_district["_month"].between(1, 12)].copy()
    monthly = valid.groupby(["_cause", "_month"]).size().rename("records").reset_index()
    totals = monthly.groupby("_cause")["records"].sum().sort_values(ascending=False)
    causes = totals.index.tolist()
    for cause in CAUSE_ORDER:
        if cause in causes:
            causes.insert(0, causes.pop(causes.index(cause)))
    seen = set()
    causes = [cause for cause in causes if not (cause in seen or seen.add(cause))]

    counts = []
    percentages = []
    totals_by_cause = []
    for cause in causes:
        row = []
        for month in range(1, 13):
            value = monthly.loc[(monthly["_cause"] == cause) & (monthly["_month"] == month), "records"].sum()
            row.append(int(value))
        total = sum(row)
        totals_by_cause.append(total)
        counts.append(row)
        percentages.append([round((value / total) * 100, 2) if total else 0 for value in row])
    return {
        "months": MONTH_NAMES,
        "causes": causes,
        "cause_totals": totals_by_cause,
        "counts": counts,
        "percentages": percentages,
        "note": "Rows show monthly share within each cause group. Small cause totals can produce large percentages from few records.",
    }


def build_yearly_summary(event_unique: pd.DataFrame, event_district: pd.DataFrame) -> list[dict]:
    event_year = event_unique[event_unique["_year"].notna()].copy()
    event_year["_year"] = event_year["_year"].astype(int)
    district_year = event_district[event_district["_year"].notna()].copy()
    district_year["_year"] = district_year["_year"].astype(int)

    event_grouped = event_year.groupby("_year").agg(
        n_events=("_event_id", "nunique"),
        mean_hazard_score=("_hazard", "mean"),
        fatalities=("_fatalities", sum_or_nan),
        people_affected=("_people_affected", sum_or_nan),
        loss_inr_lakh=("_loss_inr_lakh", sum_or_nan),
    )
    record_grouped = district_year.groupby("_year").agg(n_event_district_records=("_event_id", "size"))
    combined = event_grouped.merge(record_grouped, left_index=True, right_index=True, how="outer").sort_index()

    out = []
    for year, row in combined.iterrows():
        out.append(
            {
                "year": int(year),
                "n_events": int(row["n_events"]) if pd.notna(row["n_events"]) else 0,
                "n_event_district_records": int(row["n_event_district_records"]) if pd.notna(row["n_event_district_records"]) else 0,
                "mean_hazard_score": finite_or_none(row["mean_hazard_score"], 2),
                "fatalities": finite_or_none(row["fatalities"], 2),
                "people_affected": finite_or_none(row["people_affected"], 2),
                "loss_inr_lakh": finite_or_none(row["loss_inr_lakh"], 2),
                "loss_2026_usd": finite_or_none(row["loss_inr_lakh"] * INR_PER_LAKH / USD_INR_2026, 2),
            }
        )
    return out


def series_count_object(series: pd.Series) -> dict:
    counts = series.value_counts(dropna=True)
    return {str(key): int(value) for key, value in counts.items()}


def build_district_details(summary: pd.DataFrame, event_district: pd.DataFrame) -> dict:
    details = {}
    for _, srow in summary.iterrows():
        gid = srow["_GID_2"]
        chunk = event_district[event_district["_GID_2"] == gid].copy()
        detail = {
            "year_counts": [],
            "month_counts": [0] * 12,
            "cause_counts": {},
            "confidence_counts": {},
            "hazard_distribution": {},
            "top_events": [],
        }
        if not chunk.empty:
            years = (
                chunk[chunk["_year"].notna()]
                .assign(_year=lambda x: x["_year"].astype(int))
                .groupby("_year")
                .agg(n_events=("_event_id", "nunique"), mean_hazard_score=("_hazard", "mean"))
                .reset_index()
                .sort_values("_year")
            )
            detail["year_counts"] = [
                {
                    "year": int(row["_year"]),
                    "n_events": int(row["n_events"]),
                    "mean_hazard_score": finite_or_none(row["mean_hazard_score"], 2),
                }
                for _, row in years.iterrows()
            ]

            months = chunk[chunk["_month"].between(1, 12)].copy()
            if not months.empty:
                month_counts = months.groupby(months["_month"].astype(int))["_event_id"].nunique()
                detail["month_counts"] = [int(month_counts.get(month, 0)) for month in range(1, 13)]

            causes = (
                chunk.groupby("_cause")["_event_id"]
                .nunique()
                .sort_values(ascending=False)
            )
            detail["cause_counts"] = {str(cause): int(value) for cause, value in causes.items()}
            detail["confidence_counts"] = series_count_object(chunk["_confidence"])

            hazards = pd.to_numeric(chunk["_hazard"], errors="coerce").dropna()
            if not hazards.empty:
                detail["hazard_distribution"] = {
                    "min": finite_or_none(hazards.min(), 2),
                    "q25": finite_or_none(np.nanpercentile(hazards, 25), 2),
                    "median": finite_or_none(hazards.median(), 2),
                    "q75": finite_or_none(np.nanpercentile(hazards, 75), 2),
                    "p95": finite_or_none(np.nanpercentile(hazards, 95), 2),
                    "max": finite_or_none(hazards.max(), 2),
                }

            event_cols = [
                "_event_id",
                "_year",
                "_month",
                "_start_date_raw",
                "_cause",
                "_confidence",
                "_hazard",
                "_duration_days",
                "_fatalities",
                "_people_affected",
                "_location",
                "_source",
                "_severity_text",
            ]
            events = (
                chunk[event_cols]
                .sort_values(["_hazard", "_year"], ascending=[False, False], na_position="last")
                .head(8)
            )
            for _, row in events.iterrows():
                detail["top_events"].append(
                    {
                        "uei": str(row["_event_id"]),
                        "year": finite_or_none(row["_year"]),
                        "month": finite_or_none(row["_month"]),
                        "date": str(row["_start_date_raw"])[:32],
                        "cause": str(row["_cause"]),
                        "confidence": str(row["_confidence"]),
                        "hazard_score": finite_or_none(row["_hazard"], 2),
                        "duration_days": finite_or_none(row["_duration_days"], 1),
                        "fatalities": finite_or_none(row["_fatalities"], 1),
                        "people_affected": finite_or_none(row["_people_affected"], 1),
                        "location": str(row["_location"])[:90],
                        "source": str(row["_source"])[:60],
                        "severity": str(row["_severity_text"])[:90],
                    }
                )
        details[gid] = detail
    return details


def compact_summary_record(row: pd.Series) -> dict:
    keys = [
        "_GID_2",
        "district",
        "state",
        "n_events",
        "n_event_district_records",
        "n_scored_events",
        "mean_hazard_score",
        "median_hazard_score",
        "p95_hazard_score",
        "max_hazard_score",
        "mean_extended_hazard_score",
        "first_year",
        "last_year",
        "active_years",
        "mean_duration_days",
        "p95_duration_days",
        "mean_rainfall_max_mm",
        "max_flood_depth_m",
        "dominant_cause",
        "dominant_cause_count",
        "dominant_cause_share",
        "high_confidence_share",
        "low_confidence_share",
        "freq_class",
        "severity_class",
        "hotspot_score",
        "priority_score",
        "event_rank",
        "hazard_rank",
        "priority_rank",
    ]
    for key, spec in METRIC_SPECS.items():
        if spec["additive"]:
            keys.append(f"{key}_apportioned_sum")
    keys.extend(["crop_area_km2_apportioned_sum", "loss_2026_usd_apportioned_sum"])

    record = {}
    for key in keys:
        value = row.get(key)
        if key in ["_GID_2", "district", "state", "dominant_cause"]:
            record[key if key != "_GID_2" else "gid"] = "" if pd.isna(value) else str(value)
        else:
            record[key] = finite_or_none(value, 3)
    return record


def make_geojson(summary: pd.DataFrame, districts: gpd.GeoDataFrame) -> dict:
    props = summary.rename(columns={"_GID_2": "GID_2"}).copy()
    merged = districts.merge(props, on="GID_2", how="left", suffixes=("_shape", ""))
    merged = merged.to_crs("EPSG:4326")
    merged["geometry"] = merged.geometry.simplify(SIMPLIFY_TOLERANCE_DEGREES, preserve_topology=True)
    keep = [
        "GID_2",
        "district",
        "state",
        "n_events",
        "n_event_district_records",
        "n_scored_events",
        "mean_hazard_score",
        "median_hazard_score",
        "p95_hazard_score",
        "max_hazard_score",
        "first_year",
        "last_year",
        "active_years",
        "mean_duration_days",
        "p95_duration_days",
        "mean_rainfall_max_mm",
        "max_flood_depth_m",
        "dominant_cause",
        "dominant_cause_count",
        "dominant_cause_share",
        "high_confidence_share",
        "low_confidence_share",
        "freq_class",
        "severity_class",
        "hotspot_score",
        "priority_score",
        "event_rank",
        "hazard_rank",
        "priority_rank",
    ]
    for key, spec in METRIC_SPECS.items():
        if spec["additive"]:
            keep.append(f"{key}_apportioned_sum")
    keep.extend(["crop_area_km2_apportioned_sum", "loss_2026_usd_apportioned_sum"])
    merged = merged[keep + ["geometry"]]
    merged = merged.rename(columns={"GID_2": "gid"})
    return json.loads(merged.to_json(na="null"))


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":")), encoding="utf-8")


def read_source_data(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, low_memory=False)
    if path.suffix.lower() in [".xlsx", ".xls"]:
        return pd.read_excel(path, sheet_name="in")
    raise ValueError(f"Unsupported source data format: {path}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading source data: {SOURCE_DATA}")
    df = read_source_data(SOURCE_DATA)
    print(f"Source rows: {len(df):,}; columns: {len(df.columns):,}")

    print(f"Reading district shapefile: {DISTRICT_SHP}")
    districts = gpd.read_file(DISTRICT_SHP)
    districts = districts.to_crs("EPSG:4326")

    event_district, columns_used = prepare_event_district(df)
    event_unique = build_event_unique(event_district)
    summary = build_district_summary(event_district, districts)

    state_summary = build_state_summary(summary, event_district)
    cause_summary = build_cause_summary(event_district)
    monthly_summary = build_monthly_summary(event_district)
    yearly_summary = build_yearly_summary(event_unique, event_district)
    district_details = build_district_details(summary, event_district)
    geojson = make_geojson(summary, districts)

    all_years = pd.to_numeric(event_district["_year"], errors="coerce").dropna()
    totals = {
        "source_rows": int(len(df)),
        "valid_event_district_records": int(len(event_district)),
        "unique_events_total": int(df[columns_used["event_id"]].nunique(dropna=True)) if columns_used["event_id"] in df else int(event_unique["_event_id"].nunique()),
        "unique_events_mapped": int(event_unique["_event_id"].nunique()),
        "districts_total": int(len(districts)),
        "districts_with_records": int((summary["n_events"] > 0).sum()),
        "states_total": int(summary["state"].nunique()),
        "states_with_records": int(event_district["_state_name"].nunique()),
        "year_start": int(all_years.min()) if not all_years.empty else None,
        "year_end": int(all_years.max()) if not all_years.empty else None,
        "mean_hazard_score": finite_or_none(event_district["_hazard"].mean(), 2),
        "p95_hazard_score": finite_or_none(quantile_or_nan(event_district["_hazard"], 95), 2),
        "median_duration_days": finite_or_none(event_unique["_duration_days"].median(), 1),
        "total_fatalities": finite_or_none(event_unique["_fatalities"].sum(skipna=True), 1),
        "total_people_affected": finite_or_none(event_unique["_people_affected"].sum(skipna=True), 1),
        "total_crop_area_km2": finite_or_none(event_unique["_crop_area_ha"].sum(skipna=True) * HECTARE_TO_KM2, 3),
        "total_loss_2026_usd": finite_or_none(event_unique["_loss_inr_lakh"].sum(skipna=True) * INR_PER_LAKH / USD_INR_2026, 2),
        "source_total_crop_area_ha": finite_or_none(event_unique["_crop_area_ha"].sum(skipna=True), 1),
        "source_total_loss_inr_lakh": finite_or_none(event_unique["_loss_inr_lakh"].sum(skipna=True), 1),
    }

    district_records = [compact_summary_record(row) for _, row in summary.iterrows()]
    top_districts = {
        "events": sorted(district_records, key=lambda x: (x.get("n_events") or 0), reverse=True)[:15],
        "hazard": sorted(
            [x for x in district_records if x.get("n_scored_events", 0) >= MIN_SCORED_EVENTS],
            key=lambda x: (x.get("p95_hazard_score") or 0),
            reverse=True,
        )[:15],
        "priority": sorted(district_records, key=lambda x: (x.get("priority_score") or 0), reverse=True)[:15],
        "fatalities": sorted(district_records, key=lambda x: (x.get("fatalities_apportioned_sum") or 0), reverse=True)[:15],
        "loss": sorted(district_records, key=lambda x: (x.get("loss_2026_usd_apportioned_sum") or 0), reverse=True)[:15],
    }

    metrics = [
        {
            "key": "n_events",
            "label": "Event frequency",
            "unit": "events",
            "description": "Unique IFI events linked to each district.",
        },
        {
            "key": "p95_hazard_score",
            "label": "P95 hazard",
            "unit": "0-100",
            "description": "District 95th percentile of the IFI hazard score.",
        },
        {
            "key": "hotspot_score",
            "label": "Hotspot class",
            "unit": "1-9",
            "description": "Bivariate frequency x severity class.",
        },
        {
            "key": "dominant_cause",
            "label": "Dominant cause",
            "unit": "category",
            "description": "Most common classified cause among district-linked events.",
        },
        {
            "key": "fatalities_apportioned_sum",
            "label": "Fatalities",
            "unit": "people",
            "description": "Event-level reported fatalities apportioned across affected districts.",
        },
        {
            "key": "crop_area_km2_apportioned_sum",
            "label": "Crop area",
            "unit": "km2",
            "description": "Reported crop area affected, converted from hectares to square kilometres and apportioned across affected districts.",
        },
        {
            "key": "loss_2026_usd_apportioned_sum",
            "label": "Loss",
            "unit": "2026 USD",
            "description": "Reported monetary loss converted from INR lakh to 2026 USD and apportioned across affected districts.",
        },
        {
            "key": "priority_score",
            "label": "Planning priority",
            "unit": "0-100",
            "description": "Composite of event frequency, P95 hazard, and apportioned fatalities.",
        },
    ]

    methodology = [
        {
            "component": "Source records",
            "method": "The dashboard reads the v7 India Flood Inventory workbook and uses the event-district exploded records that contain a valid GADM district identifier.",
            "interpretation": "Each row represents one event linked to one district, so multi-district events can appear once per affected district.",
        },
        {
            "component": "Record de-duplication",
            "method": "Records are filtered with the source GADM match-valid flag when present, then duplicate district-event pairs are removed using GID_2 and the event identifier.",
            "interpretation": "District, state, and cause summaries are based on unique event-district records rather than repeated source rows.",
        },
        {
            "component": "District event frequency",
            "method": "Frequency is the count of unique IFI events mapped to each district after the validity and de-duplication steps.",
            "interpretation": "This is a district exposure-to-recorded-events measure, not a count of newspaper articles or raw database rows.",
        },
        {
            "component": "Hazard metric",
            "method": "The source-provided IFI flood hazard score is read from the v7 hazard-score field. The dashboard reports the district 95th percentile of scored event records, and only classifies hazard where at least three scored events are available.",
            "interpretation": "P95 hazard is a high-end severity indicator on a 0-100 scale; districts with too few scored events are treated as insufficient evidence for hazard-class mapping.",
        },
        {
            "component": "Hotspot class",
            "method": "Districts with events and sufficient scored records are split into low, medium, and high tertiles for event frequency and P95 hazard, then combined into a 3 by 3 frequency-severity class.",
            "interpretation": "The hotspot layer highlights whether a district is high because floods are frequent, severe, or both.",
        },
        {
            "component": "Planning priority score",
            "method": "Priority is 100 x (0.42 x event-frequency percentile + 0.38 x P95 hazard/100 + 0.20 x fatality percentile). Fatalities use apportioned district totals, and districts without mapped events receive zero.",
            "interpretation": "The score ranks districts for screening and planning attention; it is a composite decision-support index, not a probability forecast.",
        },
        {
            "component": "Flood-cause classes",
            "method": "Cause groups are taken from the classified cause field in the inventory and harmonized into the dashboard labels used in maps, charts, and tables.",
            "interpretation": "Cause charts describe classified event-district records, so the same event may contribute to multiple districts if it affected a broader area.",
        },
        {
            "component": "Monthly seasonality",
            "method": "Monthly tables group event-district records by start month and cause. Values are row-normalized percentages within each cause, and the row label shows the cause total as n.",
            "interpretation": "Each row answers: within this cause group, what share of records begin in each month?",
        },
        {
            "component": "Impact rollups",
            "method": "Event-level fatalities, displaced people, crop area, and losses are apportioned equally across affected districts before district and state totals are calculated.",
            "interpretation": "Apportionment avoids multiplying national impacts when one event touches several districts.",
        },
        {
            "component": "Units and currency",
            "method": f"Area is shown as square kilometres, crop area is converted from hectares to km2, and monetary loss is converted from INR lakh to 2026 USD using 1 USD = INR {USD_INR_2026}.",
            "interpretation": "Displayed values use SI or SI-derived units and a consistent 2026 USD monetary basis.",
        },
        {
            "component": "Sanity flags",
            "method": "Reported impact values marked by source sanity-cap flags are excluded from dashboard rollups before apportionment.",
            "interpretation": "This keeps extreme or flagged source values from dominating decision-support summaries.",
        },
        {
            "component": "CSV export",
            "method": "The export button writes the currently filtered district-level metrics, including the selected map score, impact fields, and ranking indicators.",
            "interpretation": "Exports are intended for quick screening and follow-up analysis outside the dashboard.",
        },
    ]

    analytics = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workbook": SOURCE_DATA.name,
            "source_data": SOURCE_DATA.name,
            "district_shapefile": str(DISTRICT_SHP.relative_to(ROOT)),
            "min_scored_events_for_hazard": MIN_SCORED_EVENTS,
            "unit_note": "Dashboard display units use SI or SI-derived units where applicable: km2 for area, km for length, m/mm for depths and rainfall, and 2026 USD for money.",
            "currency_note": f"Monetary values are converted from source INR lakh to 2026 USD using 1 USD = INR {USD_INR_2026}.",
            "usd_inr_2026": USD_INR_2026,
            "impact_rollup_note": "District/state impact totals apportion event-level reported impacts equally across the districts touched by each event to avoid multiplying national impacts after district explosion.",
            "sanity_cap_note": "Values marked by source sanity-cap flags are excluded from dashboard rollups.",
            "papers": [
                {
                    "title": "India flood inventory: creation of a multi-source national geospatial database to facilitate comprehensive flood research",
                    "file": "s11069-021-04698-6.pdf",
                    "doi": "https://doi.org/10.1007/s11069-021-04698-6",
                },
                {
                    "title": "A district-level flood severity index for flood management in India",
                    "file": "s11069-025-07493-9.pdf",
                    "doi": "https://doi.org/10.1007/s11069-025-07493-9",
                },
            ],
            "columns_used": columns_used,
            "methodology": methodology,
        },
        "totals": totals,
        "metrics": metrics,
        "cause_palette": CAUSE_COLORS,
        "cause_order": CAUSE_ORDER,
        "cause_summary": cause_summary,
        "state_summary": state_summary,
        "monthly": monthly_summary,
        "yearly": yearly_summary,
        "top_districts": top_districts,
        "districts": district_records,
        "district_details": district_details,
    }

    summary.rename(columns={"_GID_2": "gid"}).to_csv(OUT_DIR / "district_summary.csv", index=False)
    pd.DataFrame(state_summary).drop(columns=["cause_counts"], errors="ignore").to_csv(OUT_DIR / "state_summary.csv", index=False)

    print("Writing data assets")
    write_json(OUT_DIR / "districts.geojson", geojson)
    write_json(OUT_DIR / "analytics.json", analytics)
    (OUT_DIR / "bootstrap.js").write_text(
        "window.IFI_BOOTSTRAP = {"
        "'analytics':'data/analytics.json',"
        "'districts':'data/districts.geojson'"
        "};\n",
        encoding="utf-8",
    )
    write_json(
        OUT_DIR / "manifest.json",
        {
            "generated_at": analytics["metadata"]["generated_at"],
            "analytics": "analytics.json",
            "districts": "districts.geojson",
            "districts_total": totals["districts_total"],
            "unique_events_mapped": totals["unique_events_mapped"],
        },
    )
    print(f"Done. Wrote assets to: {OUT_DIR}")


if __name__ == "__main__":
    main()
