
import sqlite3
from collections import defaultdict

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT
        asset_id,
        custody_event_id,
        event_type,
        event_at,
        from_location_id,
        to_location_id,
        actor_owner_id,
        notes,
        issue_type
    FROM CustodyEvent
    ORDER BY asset_id, event_at, custody_event_id
""").fetchall()

events_by_asset = defaultdict(list)

for row in rows:
    events_by_asset[row["asset_id"]].append(dict(row))

movement_types = {
    "DISPATCH",
    "RETURN_RECEIVED",
    "CUSTODY_TRANSFER"
}

movement_events = 0
same_location_handoffs = 0
confirmation_events = 0
status_events = 0
continuity_issues = []

for asset_id, events in events_by_asset.items():

    previous_location = None
    previous_event_id = None

    for event in events:

        event_type = event["event_type"]
        source = event["from_location_id"]
        destination = event["to_location_id"]

        # Delivery is a confirmation, not a new movement.
        if event_type == "DELIVERY":
            confirmation_events += 1
            continue

        # Lost declaration changes status, not location.
        if event_type == "LOST_DECLARED":
            status_events += 1
            continue


        # Only valid, reliable physical movements count.
        if event_type not in movement_types:
            continue

        if event["actor_owner_id"] is None:
            continue

        if event["issue_type"] is not None:
            continue

        if event["from_location_id"] == event["to_location_id"]:
            continue




        # Same-location custody records are informational.
        if event_type == "CUSTODY_TRANSFER" and source == destination:
            same_location_handoffs += 1
            continue

        movement_events += 1

        # Check location continuity.
        if (
            previous_location is not None
            and previous_location != source
        ):
            continuity_issues.append({
                "asset_id": asset_id,
                "previous_event": previous_event_id,
                "previous_location": previous_location,
                "next_event": event["custody_event_id"],
                "next_source": source,
                "event_type": event_type
            })

        previous_location = destination
        previous_event_id = event["custody_event_id"]


print("========== SEMANTIC CUSTODY AUDIT ==========")

print("Assets with history:", len(events_by_asset))
print("Physical movement events:", movement_events)
print("Same-location custody records:", same_location_handoffs)
print("Delivery confirmations:", confirmation_events)
print("Status events:", status_events)

print("\n========== LOCATION CONTINUITY ==========")

print("Potential continuity issues:", len(continuity_issues))

for issue in continuity_issues[:15]:
    print(issue)

print("\n========== END OF AUDIT ==========")

conn.close()
