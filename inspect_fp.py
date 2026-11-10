import sqlite3

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

event_id = "CUST-ASSET-0000413-000003"

print("\n========== FALSE POSITIVE EVENT ==========")

event = conn.execute("""
    SELECT *
    FROM CustodyEvent
    WHERE custody_event_id = ?
""", (event_id,)).fetchone()

print(dict(event) if event else "Event not found")


print("\n========== COMPLETE ASSET HISTORY ==========")

rows = conn.execute("""
    SELECT custody_event_id, event_at,
           event_type, from_location_id,
           to_location_id, actor_owner_id,
           notes, issue_type
    FROM CustodyEvent
    WHERE asset_id = ?
    ORDER BY event_at, custody_event_id
""", (event["asset_id"],)).fetchall()

for row in rows:
    print(dict(row))


print("\n========== SAME TIMESTAMP EVENTS ==========")

rows = conn.execute("""
    SELECT custody_event_id, event_at,
           from_location_id, to_location_id,
           notes, issue_type
    FROM CustodyEvent
    WHERE asset_id = ?
      AND event_at = ?
    ORDER BY custody_event_id
""", (event["asset_id"], event["event_at"])).fetchall()

for row in rows:
    print(dict(row))

conn.close()
