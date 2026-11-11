
import sqlite3

connection = sqlite3.connect("assets.db")

queries = {
    "Asset status filter": """
        SELECT * FROM ReusableAsset
        WHERE current_status = ?
    """,

    "Asset custody history": """
        SELECT * FROM CustodyEvent
        WHERE asset_id = ?
        ORDER BY event_at, custody_event_id
    """,

    "Pending returns": """
        SELECT * FROM ReturnAuthorization
        WHERE asset_id = ?
          AND return_status IN ('REQUESTED', 'AUTHORIZED')
    """,

    "Inspection by RMA": """
        SELECT * FROM Inspection
        WHERE rma_id = ?
    """,

    "Open repairs": """
        SELECT * FROM Repair
        WHERE asset_id = ?
          AND repair_status IN ('OPEN', 'IN_PROGRESS')
    """,

    "Deposit refund balance": """
        SELECT SUM(
            CASE
                WHEN entry_type = 'DEPOSIT_CHARGE'
                    THEN amount
                WHEN entry_type = 'DEPOSIT_REFUND'
                    THEN -amount
                ELSE 0
            END
        )
        FROM DepositLedger
        WHERE asset_id = ?
          AND rma_id = ?
          AND currency = ?
    """
}

parameters = {
    "Asset status filter": ("AVAILABLE",),
    "Asset custody history": ("ASSET-0000005",),
    "Pending returns": ("ASSET-0000005",),
    "Inspection by RMA": ("RMA-2026-000812",),
    "Open repairs": ("ASSET-0000005",),
    "Deposit refund balance": (
        "ASSET-0000005",
        "RMA-2026-000812",
        "INR"
    )
}

print("========== SQLITE QUERY PLAN AUDIT ==========")

for name, sql in queries.items():
    print(f"\nQUERY: {name}")

    plan = connection.execute(
        "EXPLAIN QUERY PLAN " + sql,
        parameters[name]
    ).fetchall()

    for row in plan:
        print(row)

connection.close()
