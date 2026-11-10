import sqlite3

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

print("\n========== SIMULTANEOUS LOCATION PAIR ==========")

rows = conn.execute("""
    SELECT custody_event_id, event_at,
           from_location_id, to_location_id,
           notes, issue_type
    FROM CustodyEvent
    WHERE asset_id = ?
      AND event_at = ?
    ORDER BY custody_event_id
""", ("ASSET-0000001", "2026-11-10T12:00:00"))

for row in rows:
    print(dict(row))


print("\n========== RETURN TIMESTAMPS ==========")

rows = conn.execute("""
    SELECT rma_id, requested_at, authorized_at, received_at
    FROM ReturnAuthorization
    WHERE rma_id = ?
""", ("RMA-2026-000810",))

for row in rows:
    print(dict(row))


print("\n========== EXTRA ALERT SAMPLE ==========")

rows = conn.execute("""
    SELECT custody_event_id, asset_id, event_at,
           from_location_id, to_location_id,
           notes, issue_type
    FROM CustodyEvent
    WHERE asset_id IN (?, ?)
    ORDER BY asset_id, event_at, custody_event_id
""", ("ASSET-0000003", "ASSET-0000007"))

for row in rows:
    print(dict(row))

conn.close()
