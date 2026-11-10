
import sqlite3

connection = sqlite3.connect("assets.db")

tables = [
    "ReusableAsset",
    "ReturnAuthorization",
    "Inspection",
    "Repair",
    "DepositLedger"
]

for table in tables:
    print(f"\n========== {table} ==========")

    columns = connection.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    print("COLUMNS:")
    for column in columns:
        print(column[1], "| Type:", column[2])

    primary_key = [
        column[1] for column in columns if column[5] == 1
    ]

    if primary_key:
        pk = primary_key[0]

        latest = connection.execute(
            f"SELECT {pk} FROM {table} ORDER BY {pk} DESC LIMIT 3"
        ).fetchall()

        print("LATEST IDS:", latest)

print("\n========== EXISTING STATUS VALUES ==========")

checks = {
    "ReusableAsset": "current_status",
    "ReturnAuthorization": "return_status",
    "Inspection": "result",
    "Repair": "repair_status",
    "DepositLedger": "entry_type"
}

for table, column in checks.items():
    values = connection.execute(
        f"SELECT DISTINCT {column} FROM {table}"
    ).fetchall()

    print(table, ":", [row[0] for row in values])

connection.close()
print("\nWorkflow verification completed.")
