"""Download USDA QuickStats production extracts for project commodities.

The API key is read from QUICKSTATS_API_KEY. Do not commit API keys.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode


API_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
DEFAULT_YEARS = [2023, 2024]
COMMODITIES = ["MILK", "CHEESE", "HONEY", "YOGURT", "COFFEE"]
FREQUENCIES_BY_COMMODITY = {
    "MILK": ["ANNUAL", "MONTHLY"],
    "CHEESE": ["ANNUAL", "MONTHLY"],
    "HONEY": ["ANNUAL"],
    "YOGURT": ["ANNUAL"],
    "COFFEE": ["ANNUAL"],
}
OUTPUT_DIR = Path("data/raw")


def fetch_csv_rows(api_key: str, commodity: str, year: int, frequency: str) -> list[dict[str, str]]:
    """Fetch one year/frequency/commodity response from QuickStats."""
    params = {
        "key": api_key,
        "format": "CSV",
        "commodity_desc": commodity,
        "year": str(year),
        "agg_level_desc": "STATE",
        "statisticcat_desc": "PRODUCTION",
        "freq_desc": frequency,
    }
    url = f"{API_URL}?{urlencode(params)}"
    result = subprocess.run(
        ["curl", "-sS", "-L", url],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    text = result.stdout

    if text.strip().startswith("{"):
        payload = json.loads(text)
        error_text = " ".join(payload.get("error", []))
        if "exceeds limit" in error_text.lower():
            raise RuntimeError(
                f"QuickStats response is too large for {commodity} {year} {frequency}: {text}"
            )
        return []

    return list(csv.DictReader(text.splitlines()))


def year_label(years: list[int]) -> str:
    """Create a stable filename label for one or more years."""
    if len(years) == 1:
        return str(years[0])
    return f"{min(years)}_{max(years)}"


def write_combined_extract(api_key: str, commodity: str, frequency: str, years: list[int]) -> Path:
    """Download selected years and write one combined CSV."""
    rows: list[dict[str, str]] = []
    for year in years:
        rows.extend(fetch_csv_rows(api_key, commodity, year, frequency))
        time.sleep(0.2)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / (
        f"usda_quickstats_{commodity.lower()}_{year_label(years)}_{frequency.lower()}_production.csv"
    )

    if not rows:
        output_path.write_text("", encoding="utf-8")
        return output_path

    fieldnames: list[str] = []
    seen_fields: set[str] = set()
    for row in rows:
        for fieldname in row:
            if fieldname not in seen_fields:
                seen_fields.add(fieldname)
                fieldnames.append(fieldname)

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download USDA QuickStats actuals.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        help="One or more years to download.",
    )
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument(
        "--annual-only",
        action="store_true",
        help="Download only annual extracts for every commodity.",
    )
    parser.add_argument(
        "--commodities",
        nargs="+",
        default=COMMODITIES,
        choices=COMMODITIES,
        help="Commodity names to download.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.start_year is not None or args.end_year is not None:
        if args.start_year is None or args.end_year is None:
            raise SystemExit("Use --start-year and --end-year together.")
        years = list(range(args.start_year, args.end_year + 1))
    else:
        years = args.years or DEFAULT_YEARS

    years = sorted(set(years))

    api_key = os.environ.get("QUICKSTATS_API_KEY")
    if not api_key:
        raise SystemExit("Set QUICKSTATS_API_KEY before running this script.")

    written: list[Path] = []
    for commodity in args.commodities:
        frequencies = ["ANNUAL"] if args.annual_only else FREQUENCIES_BY_COMMODITY[commodity]
        for frequency in frequencies:
            path = write_combined_extract(api_key, commodity, frequency, years)
            written.append(path)
            print(f"Wrote {path}")

    print(f"Downloaded {len(written)} QuickStats extracts.")


if __name__ == "__main__":
    main()
