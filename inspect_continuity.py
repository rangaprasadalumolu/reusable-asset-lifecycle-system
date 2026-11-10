
import sqlite3

conn = sqlite3.connect("assets.db")
conn.row_factory = sqlite3.Row

asset_ids = [
    "ASSET-0000005",
    "ASSET-0000010"
]

for asset_id in asset_ids:

    print("\n" + "=" * 65)
    print("ASSET:", asset_id)
    print("=" * 65)

    asset = conn.execute("""
        SELECT asset_id, current_status, home_location_id
        FROM ReusableAsset
        WHERE asset_id = ?
    """, (asset_id,)).fetchone()

    print("\nASSET DETAILS:")
    print(dict(asset) if asset else "Not found")

    print("\nCUSTODY HISTORY:")

    events = conn.execute("""
        SELECT
            ce.custody_event_id,
            ce.event_type,
            ce.event_at,
            ce.from_location_id,
            ce.to_location_id,
            ce.actor_owner_id,
            ce.issue_type,
            ce.shipment_id
        FROM CustodyEvent ce
        WHERE ce.asset_id = ?
        ORDER BY ce.event_at, ce.custody_event_id
    """, (asset_id,)).fetchall()

    for event in events:
        print(dict(event))

    print("\nRETURN AUTHORIZATIONS:")

    returns = conn.execute("""
        SELECT *
        FROM ReturnAuthorization
        WHERE asset_id = ?
        ORDER BY requested_at
    """, (asset_id,)).fetchall()

    for item in returns:
        print(dict(item))

conn.close()
