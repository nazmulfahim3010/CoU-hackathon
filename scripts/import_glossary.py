#!/usr/bin/env python3
"""
Import glossary terms from CSV into backend/app/data/dialects/*.json.
Usage:
    python scripts/import_glossary.py --csv path/to/glossary.csv [--output-dir backend/app/data/dialects] [--dry-run]
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.schemas.glossary import GlossaryEntry


def import_csv_to_json(csv_path: Path, output_dir: Path, dry_run: bool = False) -> dict[str, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    by_dialect: dict[str, list[dict]] = defaultdict(list)

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            dialect = row.get("dialect", "standard_bangla").strip().lower()
            entry = GlossaryEntry.from_raw(row, default_dialect=dialect, idx=idx)
            by_dialect[dialect].append(entry.to_dict())

    counts = {}
    for dialect, entries in by_dialect.items():
        counts[dialect] = len(entries)
        if not dry_run:
            out_file = output_dir / f"{dialect}.json"
            n_ver = sum(1 for e in entries if e["verification_status"] == "verified")
            if dialect == "standard_bangla":
                status = "REFERENCE STANDARD"
            elif n_ver == len(entries):
                status = "TEAM-VERIFIED - all entries reviewed by named team members; not tested on real speech"
            elif n_ver:
                status = f"PARTLY VERIFIED - {n_ver}/{len(entries)} entries team-verified"
            else:
                status = "UNVERIFIED DRAFT - not reviewed by native speakers"
            data = {
                "dialect": dialect,
                "status": status,
                "entries": entries,
            }
            out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Wrote {len(entries)} entries to {out_file}")
        else:
            print(f"[DRY RUN] Would write {len(entries)} entries to {output_dir / f'{dialect}.json'}")

    return counts


def main():
    parser = argparse.ArgumentParser(description="Import dialect glossary terms from CSV to JSON.")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "backend" / "app" / "data" / "dialects"),
        help="Target dialects directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing files")

    args = parser.parse_args()
    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)

    print(f"Importing glossary from {csv_path}...")
    counts = import_csv_to_json(csv_path, output_dir, dry_run=args.dry_run)
    total = sum(counts.values())
    print(f"Successfully processed {total} entries across {len(counts)} dialects.")


if __name__ == "__main__":
    main()
