import sqlite3
import json

DB_PATH = "assets.db"

ASSET_ID = "ASSET-0000010"
RMA_ID = "RMA-2026-000811"
INSPECTION_ID = "INSP-0000810"
REPAIR_ID = "REP-2026-000172"
REFUND_ID = "LED-00001811"

connection = sqlite3.connect(DB_PATH)
connection.row_factory = sqlite3.Row

def show(title, query, params=()):
    print(f"\n========== {title} ==========")
    rows = connection.execute(query, params).fetchall()

    for row in rows:
        print(json.dumps(dict(row), indent=2))

    if not rows:
        print("No records found.")

# 1. Asset
show(
    "ASSET",
    """
    SELECT asset_id, current_status, is_active
    FROM ReusableAsset
    WHERE asset_id = ?
    """,
    (ASSET_ID,)
)

# 2. Return authorization
show(
    "RETURN AUTHORIZATION",
    """
    SELECT rma_id, asset_id, return_status,
           requested_at, authorized_at, received_at
    FROM ReturnAuthorization
    WHERE rma_id = ?
    """,
    (RMA_ID,)
)

# 3. Inspection
show(
    "INSPECTION",
    """
    SELECT inspection_id, rma_id, asset_id,
           result, damage_cost, inspected_at
    FROM Inspection
    WHERE inspection_id = ?
    """,
    (INSPECTION_ID,)
)

# 4. Repair
show(
    "REPAIR",
    """
    SELECT repair_id, asset_id, inspection_id,
           repair_status, repair_cost, opened_at, closed_at
    FROM Repair
    WHERE repair_id = ?
    """,
    (REPAIR_ID,)
)

# 5. Custody history
show(
    "CUSTODY HISTORY",
    """
    SELECT custody_event_id, event_type,
           event_at, from_location_id,
           to_location_id, actor_owner_id
    FROM CustodyEvent
    WHERE asset_id = ?
    ORDER BY event_at, custody_event_id
    """,
    (ASSET_ID,)
)

# 6. Deposit transactions
show(
    "DEPOSIT LEDGER",
    """
    SELECT ledger_entry_id, rma_id, entry_type,
           amount, currency, reference
    FROM DepositLedger
    WHERE asset_id = ?
    ORDER BY posted_at, ledger_entry_id
    """,
    (ASSET_ID,)
)

# 7. Deposit balance
show(
    "DEPOSIT BALANCE",
    """
    SELECT currency,
           SUM(
               CASE
                   WHEN entry_type = 'DEPOSIT_CHARGE'
                       THEN amount
                   WHEN entry_type = 'DEPOSIT_REFUND'
                       THEN -amount
                   ELSE 0
               END
           ) AS balance
    FROM DepositLedger
    WHERE asset_id = ?
    GROUP BY currency
    """,
    (ASSET_ID,)
)

# 8. Duplicate refund check
show(
    "DUPLICATE REFUND CHECK",
    """
    SELECT asset_id, rma_id, amount, currency,
           COUNT(*) AS transaction_count
    FROM DepositLedger
    WHERE asset_id = ?
      AND rma_id = ?
      AND entry_type = 'DEPOSIT_REFUND'
    GROUP BY asset_id, rma_id, amount, currency
    HAVING COUNT(*) > 1
    """,
    (ASSET_ID, RMA_ID)
)

# 9. Foreign key integrity
print("\n========== FOREIGN KEY CHECK ==========")
fk_errors = connection.execute(
    "PRAGMA foreign_key_check"
).fetchall()

print("PASS: No foreign key errors." if not fk_errors
      else [tuple(row) for row in fk_errors])

connection.close()
