"""Command-line helpers for the CleanRun IQ Python port."""

from __future__ import annotations

import argparse
from pathlib import Path

from cleanrun_iq.report_builder import build_report_html, filter_items
from cleanrun_iq.store import JsonStore


def main() -> None:
    """Run a small command-line interface."""
    parser = argparse.ArgumentParser(description="CleanRun IQ Python port CLI")
    parser.add_argument("--data-dir", default="./data", help="Path to JSON data directory")
    parser.add_argument("--report", choices=["handover", "open", "client", "incomplete"], help="Generate a report")
    parser.add_argument("--out", default="report.html", help="Output HTML path")
    args = parser.parse_args()

    store = JsonStore(args.data_dir)
    if args.report:
        items = filter_items(store.get_items(), args.report)
        html = build_report_html(items, args.report, store.get_settings())
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(f"Loaded {len(store.get_items())} items for {store.get_settings().active_project}")


if __name__ == "__main__":
    main()
