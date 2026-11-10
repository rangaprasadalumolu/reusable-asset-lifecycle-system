
import sqlite3

connection = sqlite3.connect("assets.db")
connection.row_factory = sqlite3.Row

print("========== ELIGIBLE ASSETS ==========")

assets = connection.execute("""
    SELECT
        a.asset_id,
        a.current_status,
        a.home_location_id,
        l.location_name
    FROM ReusableAsset a
    JOIN Location l
        ON a.home_location_id = l.location_id
    WHERE a.current_status = 'AT_CUSTOMER'
      AND a.is_active = 1
      AND NOT EXISTS (
          SELECT 1
          FROM ReturnAuthorization r
          WHERE r.asset_id = a.asset_id
            AND r.return_status IN ('REQUESTED', 'AUTHORIZED')
      )
    LIMIT 10
""").fetchall()

for asset in assets:
    print(dict(asset))

print("\n========== ACTIVE OWNERS ==========")

owners = connection.execute("""
    SELECT owner_id, owner_name, owner_type
    FROM Owner
    WHERE active = 1
""").fetchall()

for owner in owners:
    print(dict(owner))

print("\n========== ACTIVE LOCATIONS ==========")

locations = connection.execute("""
    SELECT location_id, location_name, location_type
    FROM Location
    WHERE active = 1
""").fetchall()

for location in locations:
    print(dict(location))

if not assets:
    print("\nNo eligible assets found.")

connection.close()
