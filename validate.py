
import sqlite3
import csv
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent / "assets.db"
GT_PATH = Path(__file__).parent / "data" / "starter_run" / "ground_truth.csv"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

detected = set()


def add_detection(issue_type, record_id):
    if record_id:
        detected.add((issue_type, record_id))


# 1. SIMULTANEOUS LOCATIONS
# Only compare self-location claims.
# Normal transfers are excluded because they are not independent
# claims that an asset is physically present at a location.

rows = conn.execute("""
    SELECT custody_event_id, asset_id, event_at, to_location_id
FROM CustodyEvent
WHERE to_location_id IS NOT NULL
  AND from_location_id = to_location_id
  AND event_type = 'CUSTODY_TRANSFER'
ORDER BY asset_id, event_at, custody_event_id
""").fetchall()

groups = defaultdict(list)

for row in rows:
    key = (row["asset_id"], row["event_at"])
    groups[key].append(row)

for group in groups.values():
    locations = {row["to_location_id"] for row in group}

    if len(locations) > 1:
        # Flag the first event in the conflicting group.
        first = min(group, key=lambda row: row["custody_event_id"])

        add_detection(
            "SIMULTANEOUS_LOCATIONS",
            first["custody_event_id"]
        )


# 2. RETURN BEFORE DISPATCH
# Check whether the return was received before it was requested
# or authorized. This is the actual chronology issue in our
# labelled example.

rows = conn.execute("""
    SELECT
        r.rma_id,
        r.requested_at,
        r.authorized_at,
        r.received_at
    FROM ReturnAuthorization r
    WHERE r.received_at IS NOT NULL
""").fetchall()

for row in rows:
    received = row["received_at"]
    requested = row["requested_at"]
    authorized = row["authorized_at"]

    received_too_early = (
        (requested is not None and received < requested)
        or
        (authorized is not None and received < authorized)
    )

    if received_too_early:
        add_detection(
            "RETURN_BEFORE_DISPATCH",
            row["rma_id"]
        )


# 3. DUPLICATE DEPOSIT REFUND

rows = conn.execute("""
    SELECT ledger_entry_id, asset_id, amount, currency, posted_at
    FROM DepositLedger
    WHERE entry_type = 'DEPOSIT_REFUND'
    ORDER BY posted_at, ledger_entry_id
""").fetchall()

refund_groups = defaultdict(list)

for row in rows:
    key = (row["asset_id"], row["amount"], row["currency"])
    refund_groups[key].append(row)

for group in refund_groups.values():
    for duplicate in group[1:]:
        add_detection(
            "DUPLICATE_DEPOSIT_REFUND",
            duplicate["ledger_entry_id"]
        )


# 4. REPAIR WITHOUT INSPECTION

rows = conn.execute("""
    SELECT r.repair_id
    FROM Repair r
    LEFT JOIN Inspection i
        ON r.inspection_id = i.inspection_id
    WHERE r.inspection_id IS NULL
       OR i.inspection_id IS NULL
""").fetchall()

for row in rows:
    add_detection(
        "REPAIR_WITHOUT_INSPECTION",
        row["repair_id"]
    )


# 5. MISSING CUSTODY ACTOR

rows = conn.execute("""
    SELECT custody_event_id
    FROM CustodyEvent
    WHERE actor_owner_id IS NULL
""").fetchall()

for row in rows:
    add_detection(
        "MISSING_CUSTODY_ACTOR",
        row["custody_event_id"]
    )


# LOAD GROUND TRUTH

with open(GT_PATH, "r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    ground_truth = {
        (row["issue_type"], row["record_id"]): row
        for row in reader
    }

expected = set(ground_truth.keys())


# CALCULATE METRICS

true_positives = detected & expected
false_positives = detected - expected
false_negatives = expected - detected

precision = (
    len(true_positives) / len(detected)
    if detected else 0
)

recall = (
    len(true_positives) / len(expected)
    if expected else 0
)

f1 = (
    2 * precision * recall / (precision + recall)
    if precision + recall else 0
)


# DISPLAY RESULTS

print("\n========== ANOMALY VALIDATION ==========")

print(f"Labelled anomalies: {len(expected)}")
print(f"Detected records:   {len(detected)}")
print(f"True positives:     {len(true_positives)}")
print(f"False positives:    {len(false_positives)}")
print(f"False negatives:    {len(false_negatives)}")

print("\nPrecision:", round(precision, 4))
print("Recall:   ", round(recall, 4))
print("F1 Score: ", round(f1, 4))


print("\n========== LABEL-BY-LABEL RESULTS ==========")

for key, row in ground_truth.items():
    result = "PASS" if key in detected else "MISSED"

    print(
        f"{result} | {row['issue_type']} | "
        f"{row['record_id']} | {row['expected_decision']}"
    )


if false_positives:
    print("\n========== EXTRA DETECTIONS ==========")

    for issue_type, record_id in sorted(false_positives):
        print(issue_type, "|", record_id)


if false_negatives:
    print("\n========== MISSED LABELS ==========")

    for issue_type, record_id in sorted(false_negatives):
        print(issue_type, "|", record_id)


print("\n========================================")

conn.close()
