
import sqlite3

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

asset_id = "ASSET-0000010"

print("========== ASSET LOCATION ==========")

asset = conn.execute("""
    SELECT asset_id, home_location_id, current_status
    FROM ReusableAsset
    WHERE asset_id = ?
""", (asset_id,)).fetchone()

print(dict(asset))

print("\n========== CHRONOLOGICAL CUSTODY HISTORY ==========")

events = conn.execute("""
    SELECT
        custody_event_id,
        event_type,
        event_at,
        from_location_id,
        to_location_id
    FROM CustodyEvent
    WHERE asset_id = ?
    ORDER BY event_at, custody_event_id
""", (asset_id,)).fetchall()

for event in events:
    print(dict(event))

print("\n========== LATEST EVENT BEFORE RETURN ==========")

previous = conn.execute("""
    SELECT *
    FROM CustodyEvent
    WHERE asset_id = ?
      AND event_type != 'RETURN_RECEIVED'
    ORDER BY event_at DESC, custody_event_id DESC
    LIMIT 1
""", (asset_id,)).fetchone()

print(dict(previous) if previous else "No previous event")

conn.close()
