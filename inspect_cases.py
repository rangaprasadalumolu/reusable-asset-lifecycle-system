import sqlite3
import csv
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "assets.db"
GT = BASE / "data" / "starter_run" / "ground_truth.csv"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def show(title, rows):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)

    for row in rows:
        print(dict(row))


# Read the labelled anomaly records.
with open(GT, newline="", encoding="utf-8-sig") as f:
    labels = list(csv.DictReader(f))

# Case 1: Simultaneous locations
case1 = next(
    x for x in labels
    if x["issue_type"] == "SIMULTANEOUS_LOCATIONS"
)

event_id = case1["record_id"]

event = conn.execute("""
    SELECT * FROM CustodyEvent
    WHERE custody_event_id = ?
""", (event_id,)).fetchall()

show("LABELLED SIMULTANEOUS LOCATION EVENT", event)

asset_id = case1["entity"]
asset_id = event[0]["asset_id"] if event else None

if asset_id:
    history = conn.execute("""
        SELECT *
        FROM CustodyEvent
        WHERE asset_id = ?
        ORDER BY event_at, custody_event_id
    """, (asset_id,)).fetchall()

    show("COMPLETE CUSTODY HISTORY FOR AFFECTED ASSET", history)


# Case 2: Return before dispatch
case2 = next(
    x for x in labels
    if x["issue_type"] == "RETURN_BEFORE_DISPATCH"
)

rma_id = case2["record_id"]

return_record = conn.execute("""
    SELECT *
    FROM ReturnAuthorization
    WHERE rma_id = ?
""", (rma_id,)).fetchall()

show("LABELLED RETURN AUTHORIZATION", return_record)

if return_record:
    return_asset = return_record[0]["asset_id"]

    dispatches = conn.execute("""
        SELECT *
        FROM CustodyEvent
        WHERE asset_id = ?
          AND event_type = 'DISPATCH'
        ORDER BY event_at
    """, (return_asset,)).fetchall()

    show("ALL DISPATCH EVENTS FOR RETURN ASSET", dispatches)


conn.close()
