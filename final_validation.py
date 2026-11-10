
import sqlite3
import requests
import sys

DB_PATH = "assets.db"
API_URL = "http://127.0.0.1:8000"

EXPECTED_EXCEPTIONS = {
    "SIMULTANEOUS_LOCATIONS",
    "RETURN_BEFORE_DISPATCH",
    "DUPLICATE_DEPOSIT_REFUND",
    "REPAIR_WITHOUT_INSPECTION",
    "MISSING_CUSTODY_ACTOR",
    "RETURN_SOURCE_LOCATION_MISMATCH"
}

PRIMARY_KEYS = {
    "ReusableAsset": "asset_id",
    "CustodyEvent": "custody_event_id",
    "Shipment": "shipment_id",
    "ReturnAuthorization": "rma_id",
    "Inspection": "inspection_id",
    "Repair": "repair_id",
    "DepositLedger": "ledger_entry_id"
}


def main():
    print("=" * 55)
    print("REUSABLE ASSET SYSTEM - FINAL VALIDATION")
    print("=" * 55)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    # 1. DATABASE RECORD COUNTS
    print("\n1. DATABASE RECORD COUNTS")

    for table in PRIMARY_KEYS:
        count = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table}: {count}")

    # 2. FOREIGN KEY VALIDATION
    print("\n2. FOREIGN KEY VALIDATION")

    fk_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if fk_errors:
        print("FAIL: Foreign key errors found")
        for error in fk_errors:
            print(tuple(error))
    else:
        print("PASS: No foreign key errors")

    # 3. PRIMARY KEY DUPLICATE VALIDATION
    print("\n3. PRIMARY KEY VALIDATION")

    pk_pass = True

    for table, column in PRIMARY_KEYS.items():
        duplicates = connection.execute(
            f"""
            SELECT {column}, COUNT(*) AS total
            FROM {table}
            GROUP BY {column}
            HAVING COUNT(*) > 1
            """
        ).fetchall()

        if duplicates:
            pk_pass = False
            print(f"FAIL: Duplicate IDs in {table}")
        else:
            print(f"PASS: {table}")

    connection.close()

    # 4. API HEALTH CHECK
    print("\n4. API HEALTH CHECK")

    try:
        health_response = requests.get(
            f"{API_URL}/health",
            timeout=10
        )
        health_response.raise_for_status()
        print("PASS: FastAPI health endpoint")
    except requests.RequestException as error:
        print("FAIL: API is unavailable")
        print(error)
        sys.exit(1)

    # 5. EXCEPTION ENGINE VALIDATION
    print("\n5. EXCEPTION ENGINE VALIDATION")

    try:
        response = requests.get(
            f"{API_URL}/exceptions",
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

    except requests.RequestException as error:
        print("FAIL: Could not retrieve exceptions")
        print(error)
        sys.exit(1)

    detected_types = {
        item["type"]
        for item in result["exceptions"]
    }

    print("Total detected exceptions:", result["total_exceptions"])

    for exception_type in sorted(EXPECTED_EXCEPTIONS):
        if exception_type in detected_types:
            print(f"PASS: {exception_type}")
        else:
            print(f"FAIL: {exception_type} not detected")

    missing = EXPECTED_EXCEPTIONS - detected_types

    # 6. FINAL RESULT
    print("\n" + "=" * 55)
    print("FINAL VALIDATION RESULT")
    print("=" * 55)

    if fk_errors or not pk_pass or missing:
        print("RESULT: FAILED")
        sys.exit(1)

    print("RESULT: ALL CHECKS PASSED")
    print("Database integrity: PASS")
    print("Primary keys: PASS")
    print("Foreign keys: PASS")
    print("API health: PASS")
    print("Six exception categories: PASS")


if __name__ == "__main__":
    main()
