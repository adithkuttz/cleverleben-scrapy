#!/usr/bin/env python3
# validate_output.py
# Quick check for cleaned_output.json / cleaned_output.csv consistency

import json
import csv
from pathlib import Path

JSON_FILE = Path("cleaned_output.json")
CSV_FILE = Path("cleaned_output.csv")

def check_json():
    if not JSON_FILE.exists():
        print(f"❌ {JSON_FILE} not found")
        return
    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    print(f"✅ Loaded {len(data)} items from {JSON_FILE}")

    # Basic field checks
    missing_fields = {}
    for i, item in enumerate(data, 1):
        for key in ["product_name", "product_url", "price", "currency", "images"]:
            if not item.get(key):
                missing_fields[key] = missing_fields.get(key, 0) + 1

    if missing_fields:
        print("⚠️ Missing fields found:")
        for k, v in missing_fields.items():
            print(f"   - {k}: {v} missing values")
    else:
        print("✅ All key fields are present in JSON")

def check_csv():
    if not CSV_FILE.exists():
        print(f"❌ {CSV_FILE} not found")
        return
    with CSV_FILE.open(encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        print(f"✅ Loaded {len(reader)} rows from {CSV_FILE}")

        # Sanity check: same count as JSON
        json_count = len(json.loads(JSON_FILE.read_text(encoding="utf-8")))
        if len(reader) == json_count:
            print("✅ CSV and JSON item counts match")
        else:
            print(f"⚠️ CSV rows: {len(reader)}, JSON items: {json_count}")

if __name__ == "__main__":
    print("🔍 Validating cleaned output files...\n")
    check_json()
    print()
    check_csv()
    print("\n✅ Validation complete.")
