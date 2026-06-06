"""Build a cleaned annual USDA actuals file from QuickStats extracts."""

from __future__ import annotations

import csv
import argparse
from collections import defaultdict
from pathlib import Path


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

SELECTED_ANNUAL_ITEMS_BASE = {
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


def parse_value(value: str) -> float | None:
    """Parse QuickStats numeric values, returning None for suppressed values."""
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def year_label(years: list[int]) -> str:
    """Create a stable filename label for one or more years."""
    if len(years) == 1:
        return str(years[0])
    return f"{min(years)}_{max(years)}"


def selected_annual_items(label: str) -> dict[str, dict[str, str | Path]]:
    """Attach expected raw paths for a year label."""
    items: dict[str, dict[str, str | Path]] = {}
    for commodity_key, spec in SELECTED_ANNUAL_ITEMS_BASE.items():
        item = dict(spec)
        item["path"] = RAW_DIR / (
            f"usda_quickstats_{commodity_key.lower()}_{label}_annual_production.csv"
        )
        items[commodity_key] = item
    return items


def load_selected_rows(years: set[str], label: str) -> list[dict[str, str | int | float]]:
    """Filter raw annual QuickStats extracts to the project commodity totals."""
    selected_rows: list[dict[str, str | int | float]] = []

    for commodity_key, spec in selected_annual_items(label).items():
        path = spec["path"]
        if not path.exists():
            raise FileNotFoundError(f"Missing raw extract: {path}")

        with path.open(newline="", encoding="utf-8-sig") as file:
            for row in csv.DictReader(file):
                if row["year"] not in years:
                    continue
                if row["short_desc"] != spec["short_desc"]:
                    continue
                if row["unit_desc"] != spec["unit_desc"]:
                    continue
                if not row["state_ansi"].strip():
                    continue
                if row["state_alpha"] == "OT":
                    continue

                value = parse_value(row["Value"])
                if value is None:
                    continue

                selected_rows.append(
                    {
                        "State": row["state_name"].strip().upper(),
                        "state_ansi": int(row["state_ansi"]),
                        "Year": int(row["year"]),
                        "commodity": spec["commodity"],
                        "total_production": value,
                        "unit": spec["unit_desc"],
                        "short_desc": spec["short_desc"],
                        "load_time": row["load_time"],
                        "source_file": path.name,
                        "source": "USDA NASS QuickStats",
                    }
                )

    latest_rows: dict[tuple[str, int, str], dict[str, str | int | float]] = {}
    for row in selected_rows:
        key = (str(row["State"]), int(row["Year"]), str(row["commodity"]))
        previous = latest_rows.get(key)
        if previous is None or str(row["load_time"]) > str(previous["load_time"]):
            latest_rows[key] = row

    return sorted(latest_rows.values(), key=lambda r: (r["Year"], r["commodity"], r["State"]))


def write_rows(rows: list[dict[str, str | int | float]], output_path: Path) -> None:
    """Write dictionaries to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_coverage_summary(rows: list[dict[str, str | int | float]]) -> list[dict[str, str | int | float]]:
    """Summarize selected annual actual coverage by commodity and year."""
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
                "source": "USDA NASS QuickStats",
            }
        )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build selected USDA annual actuals.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        help="One or more years to include from matching raw extracts.",
    )
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument(
        "--output",
        default=None,
        help="Output selected annual actuals CSV path.",
    )
    parser.add_argument(
        "--coverage-output",
        default=None,
        help="Output coverage summary CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.start_year is not None or args.end_year is not None:
        if args.start_year is None or args.end_year is None:
            raise SystemExit("Use --start-year and --end-year together.")
        years = list(range(args.start_year, args.end_year + 1))
    else:
        years = args.years or [2023, 2024]

    years = sorted(set(years))
    label = year_label(years)
    year_set = {str(year) for year in years}

    output_path = Path(args.output) if args.output else PROCESSED_DIR / f"usda_production_{label}_complete.csv"
    coverage_path = (
        Path(args.coverage_output)
        if args.coverage_output
        else PROCESSED_DIR / f"usda_production_{label}_coverage_summary.csv"
    )

    rows = load_selected_rows(year_set, label)
    summary = build_coverage_summary(rows)

    write_rows(rows, output_path)
    write_rows(summary, coverage_path)

    print(f"Wrote {len(rows):,} selected annual actual rows to {output_path}")
    print(f"Wrote coverage summary to {coverage_path}")


if __name__ == "__main__":
    main()
