"""Compare existing dashboard annual data against downloaded USDA actuals."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_existing(path: Path, year: int) -> dict[tuple[str, str], dict[str, str | float]]:
    """Read existing dashboard-style annual data for one year."""
    rows: dict[tuple[str, str], dict[str, str | float]] = {}
    with path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            if int(row["Year"]) != year:
                continue
            key = (row["State"].strip().upper(), row["commodity"].strip())
            rows[key] = {
                "State": key[0],
                "commodity": key[1],
                "existing_total_production": float(row["total_production"]),
            }
    return rows


def read_downloaded(path: Path, year: int) -> dict[tuple[str, str], dict[str, str | float]]:
    """Read downloaded USDA actuals for one year."""
    rows: dict[tuple[str, str], dict[str, str | float]] = {}
    with path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            if int(row["Year"]) != year:
                continue
            key = (row["State"].strip().upper(), row["commodity"].strip())
            rows[key] = {
                "State": key[0],
                "commodity": key[1],
                "downloaded_total_production": float(row["total_production"]),
                "downloaded_unit": row.get("unit", ""),
                "downloaded_short_desc": row.get("short_desc", ""),
                "downloaded_load_time": row.get("load_time", ""),
                "downloaded_source": row.get("source", ""),
            }
    return rows


def compare(
    existing: dict[tuple[str, str], dict[str, str | float]],
    downloaded: dict[tuple[str, str], dict[str, str | float]],
    tolerance: float,
) -> list[dict[str, str | float]]:
    """Create row-level comparison records."""
    output_rows: list[dict[str, str | float]] = []
    for key in sorted(set(existing) | set(downloaded)):
        old = existing.get(key, {})
        new = downloaded.get(key, {})
        old_value = old.get("existing_total_production")
        new_value = new.get("downloaded_total_production")

        if old_value is None:
            status = "downloaded_only"
            diff = ""
            pct_diff = ""
            within_tolerance = ""
        elif new_value is None:
            status = "existing_only"
            diff = ""
            pct_diff = ""
            within_tolerance = ""
        else:
            old_float = float(old_value)
            new_float = float(new_value)
            diff_float = new_float - old_float
            pct_float = diff_float / old_float * 100.0 if old_float else 0.0
            status = "matched"
            diff = diff_float
            pct_diff = pct_float
            within_tolerance = abs(diff_float) <= tolerance

        output_rows.append(
            {
                "State": key[0],
                "commodity": key[1],
                "status": status,
                "existing_total_production": old_value if old_value is not None else "",
                "downloaded_total_production": new_value if new_value is not None else "",
                "difference": diff,
                "pct_difference": pct_diff,
                "within_absolute_tolerance": within_tolerance,
                "downloaded_unit": new.get("downloaded_unit", ""),
                "downloaded_short_desc": new.get("downloaded_short_desc", ""),
                "downloaded_load_time": new.get("downloaded_load_time", ""),
                "downloaded_source": new.get("downloaded_source", ""),
            }
        )

    return output_rows


def summarize(rows: list[dict[str, str | float]]) -> list[dict[str, str | int | float]]:
    """Summarize comparison results by commodity."""
    grouped: dict[str, list[dict[str, str | float]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["commodity"])].append(row)

    summary: list[dict[str, str | int | float]] = []
    for commodity, group_rows in sorted(grouped.items()):
        matched = [row for row in group_rows if row["status"] == "matched"]
        exact = [
            row
            for row in matched
            if row["difference"] != "" and float(row["difference"]) == 0.0
        ]
        within_tolerance = [
            row
            for row in matched
            if row["within_absolute_tolerance"] is True
        ]
        abs_diffs = [
            abs(float(row["difference"]))
            for row in matched
            if row["difference"] != ""
        ]
        summary.append(
            {
                "commodity": commodity,
                "rows": len(group_rows),
                "matched": len(matched),
                "exact_matches": len(exact),
                "within_absolute_tolerance": len(within_tolerance),
                "existing_only": sum(1 for row in group_rows if row["status"] == "existing_only"),
                "downloaded_only": sum(1 for row in group_rows if row["status"] == "downloaded_only"),
                "max_abs_difference": max(abs_diffs) if abs_diffs else "",
            }
        )

    return summary


def write_rows(rows: list[dict[str, str | int | float]], output_path: Path) -> None:
    """Write comparison rows to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare existing data to USDA actuals.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--existing", default="SQL/USDA_production_2023.csv")
    parser.add_argument("--downloaded", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument(
        "--absolute-tolerance",
        type=float,
        default=0.0,
        help="Absolute value tolerance for considering rows matched.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    existing = read_existing(Path(args.existing), args.year)
    downloaded = read_downloaded(Path(args.downloaded), args.year)
    comparison = compare(existing, downloaded, args.absolute_tolerance)
    summary = summarize(comparison)

    write_rows(comparison, Path(args.output))
    write_rows(summary, Path(args.summary_output))

    print(f"Compared {len(existing):,} existing rows to {len(downloaded):,} downloaded rows.")
    print(f"Wrote comparison to {args.output}")
    print(f"Wrote summary to {args.summary_output}")


if __name__ == "__main__":
    main()
