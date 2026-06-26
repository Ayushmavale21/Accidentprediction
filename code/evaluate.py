from __future__ import annotations

import argparse
import csv
from pathlib import Path


KEY_COLUMNS = [
    "evidence_standard_met",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "supporting_image_ids",
    "valid_image",
    "severity",
]


def normalize(value: str) -> str:
    return str(value or "").strip().lower()


def load_by_key(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        (
            normalize(row.get("user_id")),
            normalize(row.get("image_paths")),
            normalize(row.get("user_claim")),
        ): row
        for row in rows
    }


def evaluate(expected_csv: Path, predicted_csv: Path) -> None:
    expected = load_by_key(expected_csv)
    predicted = load_by_key(predicted_csv)

    compared = 0
    exact_rows = 0
    field_hits = {column: 0 for column in KEY_COLUMNS}
    field_totals = {column: 0 for column in KEY_COLUMNS}

    for key, expected_row in expected.items():
        predicted_row = predicted.get(key)
        if not predicted_row:
            continue
        compared += 1
        row_exact = True
        for column in KEY_COLUMNS:
            if column not in expected_row or expected_row.get(column, "") == "":
                continue
            field_totals[column] += 1
            if normalize(expected_row.get(column)) == normalize(predicted_row.get(column)):
                field_hits[column] += 1
            else:
                row_exact = False
        exact_rows += int(row_exact)

    print(f"rows_compared={compared}")
    print(f"exact_row_match={exact_rows}/{compared}" if compared else "exact_row_match=0/0")
    for column in KEY_COLUMNS:
        total = field_totals[column]
        hit = field_hits[column]
        if total:
            print(f"{column}={hit}/{total} ({hit / total:.1%})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate claim predictions against labelled rows.")
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--predicted", required=True, type=Path)
    args = parser.parse_args()
    evaluate(args.expected, args.predicted)


if __name__ == "__main__":
    main()
