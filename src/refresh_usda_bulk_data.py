"""Refresh project USDA production data from QuickStats bulk exports.

The script filters official USDA NASS QuickStats bulk files down to this
project's annual state-level production measures, writes an
audit-rich processed file, and replaces the dashboard-ready CSV.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path
from typing import Iterable


BULK_SOURCE_URLS = [
    "https://www.nass.usda.gov/datasets/qs.animals_products_20260605.txt.gz",
    "https://www.nass.usda.gov/datasets/qs.crops_20260605.txt.gz",
]
SOURCE_LABEL = "USDA NASS QuickStats bulk export"

PROJECT_ITEMS = {
    "MILK": {
        "commodity": "Milk",
        "short_desc": "MILK - PRODUCTION, MEASURED IN LB",
        "unit_desc": "LB",
    },
    "CHEESE": {
        "commodity": "Cheese",
        "short_desc": "CHEESE - PRODUCTION, MEASURED IN LB",
        "unit_desc": "LB",
    },
    "HONEY": {
        "commodity": "Honey",
        "short_desc": "HONEY - PRODUCTION, MEASURED IN LB",
        "unit_desc": "LB",
    },
    "YOGURT": {
        "commodity": "Yogurt",
        "short_desc": "YOGURT, PLAIN & FLAVORED - PRODUCTION, MEASURED IN LB",
        "unit_desc": "LB",
    },
    "COFFEE": {
        "commodity": "Coffee",
        "short_desc": "COFFEE - PRODUCTION, MEASURED IN LB, CHERRY BASIS",
        "unit_desc": "LB, CHERRY BASIS",
    },
}

RAW_QUICKSTATS_FIELDS = [
    "SOURCE_DESC",
    "SECTOR_DESC",
    "GROUP_DESC",
    "COMMODITY_DESC",
    "CLASS_DESC",
    "PRODN_PRACTICE_DESC",
    "UTIL_PRACTICE_DESC",
    "STATISTICCAT_DESC",
    "UNIT_DESC",
    "SHORT_DESC",
    "DOMAIN_DESC",
    "DOMAINCAT_DESC",
    "AGG_LEVEL_DESC",
    "STATE_ANSI",
    "STATE_FIPS_CODE",
    "STATE_ALPHA",
    "STATE_NAME",
    "ASD_CODE",
    "ASD_DESC",
    "COUNTY_ANSI",
    "COUNTY_CODE",
    "COUNTY_NAME",
    "REGION_DESC",
    "ZIP_5",
    "WATERSHED_CODE",
    "WATERSHED_DESC",
    "CONGR_DISTRICT_CODE",
    "COUNTRY_CODE",
    "COUNTRY_NAME",
    "LOCATION_DESC",
    "YEAR",
    "FREQ_DESC",
    "BEGIN_CODE",
    "END_CODE",
    "REFERENCE_PERIOD_DESC",
    "WEEK_ENDING",
    "LOAD_TIME",
    "VALUE",
    "CV_%",
]


def parse_value(value: str) -> float | None:
    """Parse QuickStats numeric values, returning None for suppressed values."""
    cleaned = value.replace(",", "").strip().replace("\x00", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def detect_delimiter(first_line: str) -> str:
    """Detect whether a QuickStats bulk file is tab- or comma-delimited."""
    return "\t" if first_line.count("\t") >= first_line.count(",") else ","


def open_bulk_reader(path: Path) -> Iterable[dict[str, str]]:
    """Open a gzip QuickStats bulk file as dictionaries."""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="") as file:
        first_line = file.readline()
        if not first_line:
            return
        delimiter = detect_delimiter(first_line)
        reader = csv.DictReader(chain([first_line], file), delimiter=delimiter)
        for row in reader:
            yield {str(key).upper(): value for key, value in row.items() if key is not None}


def matches_project_item(row: dict[str, str], start_year: int, end_year: int) -> bool:
    """Return True when a QuickStats row is one of the project annual measures."""
    try:
        year = int(row.get("YEAR", ""))
    except ValueError:
        return False

    if not start_year <= year <= end_year:
        return False
    if row.get("AGG_LEVEL_DESC") != "STATE":
        return False
    if row.get("STATISTICCAT_DESC") != "PRODUCTION":
        return False
    if row.get("FREQ_DESC") != "ANNUAL":
        return False
    if not row.get("STATE_ANSI", "").strip():
        return False
    if row.get("STATE_ALPHA") == "OT":
        return False

    spec = PROJECT_ITEMS.get(row.get("COMMODITY_DESC", ""))
    if spec is None:
        return False
    if row.get("SHORT_DESC") != spec["short_desc"]:
        return False
    if row.get("UNIT_DESC") != spec["unit_desc"]:
        return False

    return parse_value(row.get("VALUE", "")) is not None


def filtered_bulk_rows(paths: list[Path], start_year: int, end_year: int) -> list[dict[str, str]]:
    """Read and filter the bulk export to project rows."""
    rows: list[dict[str, str]] = []
    for path in paths:
        source_file = path.name
        for row in open_bulk_reader(path):
            if matches_project_item(row, start_year, end_year):
                row["SOURCE_FILE"] = source_file
                rows.append(row)
    return rows


def processed_rows(rows: list[dict[str, str]]) -> list[dict[str, str | int | float]]:
    """Normalize filtered QuickStats rows to the project data contract."""
    latest_rows: dict[tuple[str, int, str], dict[str, str | int | float]] = {}

    for row in rows:
        spec = PROJECT_ITEMS[row["COMMODITY_DESC"]]
        key = (
            row["STATE_NAME"].strip().upper(),
            int(row["YEAR"]),
            str(spec["commodity"]),
        )
        normalized = {
            "State": key[0],
            "state_ansi": int(row["STATE_ANSI"]),
            "Year": key[1],
            "commodity": key[2],
            "total_production": float(parse_value(row["VALUE"]) or 0),
            "unit": spec["unit_desc"],
            "short_desc": spec["short_desc"],
            "load_time": row["LOAD_TIME"],
            "source_file": row["SOURCE_FILE"],
            "source": SOURCE_LABEL,
        }
        previous = latest_rows.get(key)
        if previous is None or str(normalized["load_time"]) > str(previous["load_time"]):
            latest_rows[key] = normalized

    return sorted(latest_rows.values(), key=lambda r: (r["Year"], r["commodity"], r["State"]))


def dashboard_rows(rows: list[dict[str, str | int | float]]) -> list[dict[str, str | int | float]]:
    """Create the lean CSV shape used by SQL examples and the Dash app."""
    return [
        {
            "State": row["State"],
            "Year": row["Year"],
            "commodity": row["commodity"],
            "total_production": row["total_production"],
        }
        for row in rows
    ]


def write_rows(path: Path, rows: list[dict[str, str | int | float]], fieldnames: list[str] | None = None) -> None:
    """Write a list of dictionaries to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []

    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_coverage_summary(rows: list[dict[str, str | int | float]]) -> list[dict[str, str | int | float]]:
    """Summarize annual state coverage by commodity and year."""
    grouped: dict[tuple[str, int], list[dict[str, str | int | float]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["commodity"]), int(row["Year"]))].append(row)

    summary: list[dict[str, str | int | float]] = []
    for (commodity, year), group_rows in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        values = [float(row["total_production"]) for row in group_rows]
        states = sorted({str(row["State"]) for row in group_rows})
        summary.append(
            {
                "Year": year,
                "commodity": commodity,
                "rows": len(group_rows),
                "states": len(states),
                "unit": group_rows[0]["unit"],
                "min_total_production": min(values),
                "max_total_production": max(values),
                "source": SOURCE_LABEL,
            }
        )

    return summary


def load_dashboard_rows_from_iterable(lines: Iterable[str]) -> dict[tuple[str, int, str], float]:
    """Load dashboard-shaped CSV rows from an iterable of lines."""
    existing: dict[tuple[str, int, str], float] = {}
    for row in csv.DictReader(lines):
        try:
            key = (row["State"].strip().upper(), int(row["Year"]), row["commodity"].strip())
            value = float(str(row["total_production"]).replace(",", ""))
        except (KeyError, TypeError, ValueError):
            continue
        existing[key] = value
    return existing


def load_dashboard_rows(path: Path) -> dict[tuple[str, int, str], float]:
    """Load an existing dashboard CSV for comparison."""
    if not path.exists():
        return {}

    with path.open(newline="", encoding="utf-8-sig") as file:
        return load_dashboard_rows_from_iterable(file)


def load_dashboard_rows_from_git(git_spec: str) -> dict[tuple[str, int, str], float]:
    """Load a dashboard CSV from a git object such as HEAD:SQL/file.csv."""
    result = subprocess.run(
        ["git", "show", git_spec],
        check=True,
        capture_output=True,
        text=True,
    )
    return load_dashboard_rows_from_iterable(result.stdout.splitlines())


def compare_dashboard_data(
    old: dict[tuple[str, int, str], float],
    new_rows: list[dict[str, str | int | float]],
) -> tuple[list[dict[str, str | int | float]], list[dict[str, str | int | float]]]:
    """Compare the existing dashboard file with the refreshed rows."""
    new = {
        (str(row["State"]), int(row["Year"]), str(row["commodity"])): float(row["total_production"])
        for row in new_rows
    }
    all_keys = sorted(set(old) | set(new), key=lambda key: (key[1], key[2], key[0]))
    details: list[dict[str, str | int | float]] = []

    for state, year, commodity in all_keys:
        old_value = old.get((state, year, commodity))
        new_value = new.get((state, year, commodity))
        if old_value is None:
            status = "added"
        elif new_value is None:
            status = "removed"
        elif abs(old_value - new_value) > 0.5:
            status = "changed"
        else:
            status = "unchanged"

        if status == "unchanged":
            continue

        difference = None if old_value is None or new_value is None else new_value - old_value
        pct_difference = (
            None
            if old_value in (None, 0) or new_value is None
            else difference / old_value
        )
        details.append(
            {
                "State": state,
                "Year": year,
                "commodity": commodity,
                "status": status,
                "existing_total_production": old_value,
                "bulk_total_production": new_value,
                "difference": difference,
                "pct_difference": pct_difference,
            }
        )

    summary_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for key in old:
        summary_groups[key[2]]["existing_rows"] += 1
    for key in new:
        summary_groups[key[2]]["bulk_rows"] += 1
    for detail in details:
        summary_groups[str(detail["commodity"])][f"{detail['status']}_rows"] += 1

    summary: list[dict[str, str | int | float]] = []
    for commodity in sorted(summary_groups):
        group = summary_groups[commodity]
        summary.append(
            {
                "commodity": commodity,
                "existing_rows": group["existing_rows"],
                "bulk_rows": group["bulk_rows"],
                "added_rows": group["added_rows"],
                "removed_rows": group["removed_rows"],
                "changed_rows": group["changed_rows"],
            }
        )

    summary.append(
        {
            "commodity": "ALL",
            "existing_rows": len(old),
            "bulk_rows": len(new),
            "added_rows": sum(1 for row in details if row["status"] == "added"),
            "removed_rows": sum(1 for row in details if row["status"] == "removed"),
            "changed_rows": sum(1 for row in details if row["status"] == "changed"),
        }
    )
    return details, summary


def write_manifest(path: Path, args: argparse.Namespace, row_count: int, outputs: dict[str, str]) -> None:
    """Write a lightweight refresh manifest for auditability."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_LABEL,
        "source_urls": args.source_url,
        "bulk_paths": [str(path) for path in args.bulk_path],
        "year_range": {"start_year": args.start_year, "end_year": args.end_year},
        "project_items": PROJECT_ITEMS,
        "selected_rows": row_count,
        "outputs": outputs,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh USDA production data from a bulk export.")
    parser.add_argument(
        "--bulk-path",
        type=Path,
        nargs="+",
        required=True,
        help="Path(s) to QuickStats qs.*.txt.gz bulk files.",
    )
    parser.add_argument("--source-url", nargs="*", default=BULK_SOURCE_URLS)
    parser.add_argument("--start-year", type=int, default=1930)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=Path("data/raw/usda_quickstats_bulk_1930_2023_project_production.csv"),
    )
    parser.add_argument(
        "--processed-output",
        type=Path,
        default=Path("data/processed/usda_production_1930_2023_complete.csv"),
    )
    parser.add_argument(
        "--dashboard-output",
        type=Path,
        default=Path("SQL/USDA_production_2023.csv"),
    )
    parser.add_argument(
        "--coverage-output",
        type=Path,
        default=Path("data/processed/usda_production_1930_2023_coverage_summary.csv"),
    )
    parser.add_argument(
        "--comparison-output",
        type=Path,
        default=Path("data/processed/usda_1930_2023_existing_vs_bulk_comparison.csv"),
    )
    parser.add_argument(
        "--comparison-summary-output",
        type=Path,
        default=Path("data/processed/usda_1930_2023_existing_vs_bulk_summary.csv"),
    )
    parser.add_argument(
        "--comparison-base",
        type=Path,
        default=None,
        help="Existing dashboard CSV to compare against. Defaults to --dashboard-output before overwrite.",
    )
    parser.add_argument(
        "--comparison-base-git-spec",
        default=None,
        help="Git object to use as the comparison base, for example HEAD:SQL/USDA_production_2023.csv.",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("data/processed/usda_bulk_refresh_manifest.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.start_year > args.end_year:
        raise SystemExit("--start-year must be less than or equal to --end-year.")
    missing_paths = [path for path in args.bulk_path if not path.exists()]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise SystemExit(f"Bulk file does not exist: {missing}")

    if args.comparison_base_git_spec:
        comparison_base = load_dashboard_rows_from_git(args.comparison_base_git_spec)
    else:
        comparison_base = load_dashboard_rows(args.comparison_base or args.dashboard_output)

    raw_rows = filtered_bulk_rows(args.bulk_path, args.start_year, args.end_year)
    rows = processed_rows(raw_rows)
    lean_rows = dashboard_rows(rows)
    coverage = build_coverage_summary(rows)
    comparison, comparison_summary = compare_dashboard_data(comparison_base, lean_rows)

    raw_fieldnames = RAW_QUICKSTATS_FIELDS + ["SOURCE_FILE"]
    write_rows(args.raw_output, raw_rows, raw_fieldnames)
    write_rows(args.processed_output, rows)
    write_rows(args.coverage_output, coverage)
    write_rows(args.comparison_output, comparison)
    write_rows(args.comparison_summary_output, comparison_summary)
    write_rows(args.dashboard_output, lean_rows, ["State", "Year", "commodity", "total_production"])
    write_manifest(
        args.manifest_output,
        args,
        len(rows),
        {
            "raw_output": str(args.raw_output),
            "processed_output": str(args.processed_output),
            "dashboard_output": str(args.dashboard_output),
            "coverage_output": str(args.coverage_output),
            "comparison_output": str(args.comparison_output),
            "comparison_summary_output": str(args.comparison_summary_output),
        },
    )

    print(f"Selected {len(raw_rows):,} raw QuickStats rows.")
    print(f"Wrote {len(rows):,} refreshed annual production rows to {args.processed_output}.")
    print(f"Updated dashboard CSV at {args.dashboard_output}.")
    print(f"Wrote {len(comparison):,} changed/added/removed comparison rows.")


if __name__ == "__main__":
    main()
