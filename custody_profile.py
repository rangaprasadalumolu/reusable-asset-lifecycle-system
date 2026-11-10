
import sqlite3

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

print("========== EVENT TYPE COUNTS ==========")

rows = conn.execute("""
    SELECT
        event_type,
        COUNT(*) AS total_events,
        COUNT(DISTINCT asset_id) AS affected_assets
    FROM CustodyEvent
    GROUP BY event_type
    ORDER BY total_events DESC
""").fetchall()

for row in rows:
    print(dict(row))


print("\n========== SELF-TRANSFER COUNTS BY TYPE ==========")

rows = conn.execute("""
    SELECT
        event_type,
        COUNT(*) AS total
    FROM CustodyEvent
    WHERE from_location_id = to_location_id
    GROUP BY event_type
""").fetchall()

for row in rows:
    print(dict(row))


print("\n========== SAMPLE EVENTS FOR ONE ASSET ==========")

rows = conn.execute("""
    SELECT
        custody_event_id,
        event_type,
        event_at,
        from_location_id,
        to_location_id,
        issue_type,
        notes
    FROM CustodyEvent
    WHERE asset_id = 'ASSET-0000001'
    ORDER BY event_at, custody_event_id
""").fetchall()

for row in rows:
    print(dict(row))


conn.close()
