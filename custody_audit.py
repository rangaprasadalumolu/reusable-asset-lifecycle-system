
import sqlite3
from collections import defaultdict

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

events = conn.execute("""
    SELECT
        asset_id,
        custody_event_id,
        event_type,
        event_at,
        from_location_id,
        to_location_id
    FROM CustodyEvent
    ORDER BY asset_id, event_at, custody_event_id
""").fetchall()

grouped = defaultdict(list)

for event in events:
    grouped[event["asset_id"]].append(dict(event))

continuity_issues = []
self_transfers = []

for asset_id, records in grouped.items():

    for i, event in enumerate(records):

        # Detect transfers without actual movement
        if (
            event["event_type"] == "CUSTODY_TRANSFER"
            and event["from_location_id"] == event["to_location_id"]
        ):
            self_transfers.append(event)

        # Compare consecutive custody locations
        if i > 0:
            previous = records[i - 1]

            if previous["to_location_id"] != event["from_location_id"]:
                continuity_issues.append({
                    "asset_id": asset_id,
                    "previous_event": previous["custody_event_id"],
                    "previous_location": previous["to_location_id"],
                    "next_event": event["custody_event_id"],
                    "next_source": event["from_location_id"]
                })

print("========== CUSTODY AUDIT ==========")

print("\nTotal assets with custody history:", len(grouped))

print("Location continuity issues:", len(continuity_issues))

for issue in continuity_issues[:20]:
    print(issue)

print("\nSelf-transfer events:", len(self_transfers))

for event in self_transfers[:20]:
    print({
        "asset_id": event["asset_id"],
        "event_id": event["custody_event_id"],
        "location": event["from_location_id"]
    })

conn.close()
