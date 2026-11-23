import csv
import json
from pathlib import Path

source = Path("data/catalogue.csv")
output = Path("data/catalogue.repaired.csv")

with source.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    header = next(reader)
    rows = list(reader)

if len(header) != 23:
    raise SystemExit(f"STOP: Expected 23 headers, found {len(header)}")

repaired = []

for line_number, row in enumerate(rows, start=2):
    if len(row) != 25:
        raise SystemExit(
            f"STOP: Row {line_number} has {len(row)} columns, expected 25"
        )

    first, middle, last = row[5], row[6], row[7]

    if not first.startswith("[") or "]" not in last:
        raise SystemExit(f"STOP: Unexpected audience_tags format at row {line_number}")

    tags = [
        first.lstrip("[").strip('"'),
        middle.strip('"'),
        last.rstrip('"').rstrip("]").strip('"')
    ]

    if any(not tag for tag in tags):
        raise SystemExit(f"STOP: Empty audience tag at row {line_number}")

    row[5] = json.dumps(tags, ensure_ascii=False)
    row = row[:6] + row[8:]

    if len(row) != 23:
        raise SystemExit(f"STOP: Repair failed at row {line_number}")

    parsed_tags = json.loads(row[5])
    if not isinstance(parsed_tags, list) or len(parsed_tags) != 3:
        raise SystemExit(f"STOP: Invalid audience_tags at row {line_number}")

    repaired.append(row)

with output.open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(repaired)

with output.open("r", encoding="utf-8", newline="") as f:
    check = list(csv.reader(f))

assert len(check) == 151, f"Expected 151 lines including header, found {len(check)}"
assert all(len(row) == 23 for row in check), "A row still has an incorrect column count"

print("Repair successful.")
print("Destination rows:", len(repaired))
print("Header columns:", len(header))
print("All data rows have 23 columns.")
print("Sample audience_tags:", repaired[0][5])
print("Repaired file:", output)
