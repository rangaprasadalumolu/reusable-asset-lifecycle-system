from fastapi import FastAPI, HTTPException, Query
import sqlite3
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field
from streamlit import connection

app = FastAPI(
    title="Reusable Asset Lifecycle API",
    description="Track reusable assets, shipments, custody and exceptions.",
    version="1.0.0"
)

DB_PATH = Path(__file__).parent / "assets.db"

# ==========================================
# REQUEST MODELS
# ==========================================

class ReturnCreate(BaseModel):
    asset_id: str
    source_location_id: str
    destination_location_id: str
    reason: str
    requested_at: str | None = None


class ReturnReceive(BaseModel):
    actor_owner_id: str
    received_at: str | None = None
    notes: str | None = None


class InspectionCreate(BaseModel):
    rma_id: str
    inspector_owner_id: str
    result: str
    damage_cost: float = Field(default=0, ge=0)
    notes: str | None = None
    inspected_at: str | None = None


class RepairCreate(BaseModel):
    asset_id: str
    inspection_id: str
    repair_center_location_id: str
    repair_cost: float = Field(default=0, ge=0)


class DepositCreate(BaseModel):
    asset_id: str
    rma_id: str | None = None
    entry_type: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    reference: str


class RepairClose(BaseModel):
    closed_at: str | None = None


# ==========================================
# COMMON HELPER FUNCTIONS
# ==========================================

def current_timestamp():
    return datetime.now().replace(microsecond=0).isoformat()


def validate_timestamp(value):
    try:
        datetime.fromisoformat(value)
        return value
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid timestamp. Use ISO format: YYYY-MM-DDTHH:MM:SS"
        )


def next_id(connection, table, column, prefix, width=6):
    query = f"""
        SELECT {column}
        FROM {table}
        WHERE {column} LIKE ?
    """

    rows = connection.execute(
        query, (prefix + "%",)
    ).fetchall()

    numbers = []

    for row in rows:
        value = row[0]

        try:
            numbers.append(int(value[len(prefix):]))
        except (ValueError, TypeError):
            continue

    next_number = max(numbers, default=0) + 1

    return prefix + str(next_number).zfill(width)


def check_active_owner(connection, owner_id):
    owner = connection.execute(
        """
        SELECT owner_id
        FROM Owner
        WHERE owner_id = ? AND active = 1
        """,
        (owner_id,)
    ).fetchone()

    if not owner:
        raise HTTPException(
            status_code=400,
            detail="Owner not found or inactive"
        )


def check_active_location(connection, location_id):
    location = connection.execute(
        """
        SELECT location_id
        FROM Location
        WHERE location_id = ? AND active = 1
        """,
        (location_id,)
    ).fetchone()

    if not location:
        raise HTTPException(
            status_code=400,
            detail="Location not found or inactive"
        )



def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def fetch_all(sql, params=()):
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def fetch_one(sql, params=()):
    with get_connection() as connection:
        row = connection.execute(sql, params).fetchone()
        return dict(row) if row else None


@app.get("/")
def home():
    return {
        "message": "Reusable Asset Lifecycle API is running",
        "documentation": "/docs"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database_exists": DB_PATH.exists()
    }


@app.get("/assets")
def list_assets(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    sql = "SELECT * FROM ReusableAsset"
    params = []

    if status:
        sql += " WHERE current_status = ?"
        params.append(status)

    sql += " ORDER BY asset_id LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    assets = fetch_all(sql, params)

    return {
        "count": len(assets),
        "limit": limit,
        "offset": offset,
        "assets": assets
    }


@app.get("/assets/{asset_id}")
def get_asset(asset_id: str):
    asset = fetch_one(
        "SELECT * FROM ReusableAsset WHERE asset_id = ?",
        (asset_id,)
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    return asset


@app.get("/assets/{asset_id}/history")
def asset_history(asset_id: str):
    asset = fetch_one(
        "SELECT asset_id FROM ReusableAsset WHERE asset_id = ?",
        (asset_id,)
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found"
        )

    history = fetch_all(
        """
        SELECT
            custody_event_id,
            event_type,
            event_at,
            shipment_id,
            from_location_id,
            to_location_id,
            actor_owner_id,
            notes,
            issue_type
        FROM CustodyEvent
        WHERE asset_id = ?
        ORDER BY event_at, custody_event_id
        """,
        (asset_id,)
    )

    return {
        "asset_id": asset_id,
        "event_count": len(history),
        "history": history
    }




@app.get("/exceptions")
def get_exceptions():
    exceptions = []

    # 1. SIMULTANEOUS LOCATIONS
    # Detect conflicting self-location claims from custody transfers.

    rows = fetch_all("""
        SELECT
            custody_event_id,
            asset_id,
            event_at,
            from_location_id,
            to_location_id
        FROM CustodyEvent
        WHERE event_type = 'CUSTODY_TRANSFER'
          AND from_location_id = to_location_id
          AND to_location_id IS NOT NULL
        ORDER BY asset_id, event_at, custody_event_id
    """)

    groups = {}

    for row in rows:
        key = (row["asset_id"], row["event_at"])
        groups.setdefault(key, []).append(row)

    for group in groups.values():
        locations = sorted({
            row["to_location_id"] for row in group
        })

        if len(locations) > 1:
            first_event = group[0]

            exceptions.append({
                "type": "SIMULTANEOUS_LOCATIONS",
                "record_id": first_event["custody_event_id"],
                "asset_id": first_event["asset_id"],
                "decision": "QUARANTINE_ASSET",
                "details": {
                    "event_at": first_event["event_at"],
                    "conflicting_locations": locations,
                    "conflicting_event_ids": [
                        row["custody_event_id"] for row in group
                    ]
                }
            })

    # 2. RETURN RECEIVED BEFORE REQUEST / AUTHORIZATION

    rows = fetch_all("""
        SELECT
            rma_id,
            asset_id,
            requested_at,
            authorized_at,
            received_at
        FROM ReturnAuthorization
        WHERE received_at IS NOT NULL
    """)

    for row in rows:
        received = row["received_at"]
        requested = row["requested_at"]
        authorized = row["authorized_at"]

        received_too_early = (
            (requested is not None and received < requested)
            or
            (authorized is not None and received < authorized)
        )

        if received_too_early:
            exceptions.append({
                "type": "RETURN_BEFORE_DISPATCH",
                "record_id": row["rma_id"],
                "asset_id": row["asset_id"],
                "decision": "REJECT_RETURN_AND_REVIEW",
                "details": row
            })

    # 3. DUPLICATE DEPOSIT REFUNDS

    rows = fetch_all("""
        SELECT
            ledger_entry_id,
            asset_id,
            rma_id,
            amount,
            currency,
            posted_at,
            reference
        FROM DepositLedger
        WHERE entry_type = 'DEPOSIT_REFUND'
          AND rma_id IS NOT NULL
        ORDER BY posted_at, ledger_entry_id
    """)

    refund_groups = {}

    for row in rows:
        key = (
            row["asset_id"],
            row["rma_id"],
            row["amount"],
            row["currency"]
        )

        refund_groups.setdefault(key, []).append(row)

    for group in refund_groups.values():
        if len(group) > 1:
            original = group[0]

            for duplicate in group[1:]:
                exceptions.append({
                    "type": "DUPLICATE_DEPOSIT_REFUND",
                    "record_id": duplicate["ledger_entry_id"],
                    "asset_id": duplicate["asset_id"],
                    "decision": "REVERSE_DUPLICATE_AND_FLAG",
                    "details": {
                        "duplicate_refund": duplicate,
                        "original_refund_id": original["ledger_entry_id"],
                        "refund_count": len(group)
                    }
                })

    # 4. REPAIR WITHOUT INSPECTION

    rows = fetch_all("""
        SELECT
            r.repair_id,
            r.asset_id,
            r.inspection_id,
            r.repair_status
        FROM Repair r
        LEFT JOIN Inspection i
            ON r.inspection_id = i.inspection_id
        WHERE r.inspection_id IS NULL
           OR i.inspection_id IS NULL
    """)

    for row in rows:
        exceptions.append({
            "type": "REPAIR_WITHOUT_INSPECTION",
            "record_id": row["repair_id"],
            "asset_id": row["asset_id"],
            "decision": "REOPEN_REPAIR_AND_REQUIRE_INSPECTION",
            "details": row
        })

    # 5. MISSING CUSTODY ACTOR

    rows = fetch_all("""
        SELECT
            custody_event_id,
            asset_id,
            event_type,
            event_at,
            from_location_id,
            to_location_id
        FROM CustodyEvent
        WHERE actor_owner_id IS NULL
    """)

    for row in rows:
        exceptions.append({
            "type": "MISSING_CUSTODY_ACTOR",
            "record_id": row["custody_event_id"],
            "asset_id": row["asset_id"],
            "decision": "HOLD_EVENT_FOR_REVIEW",
            "details": row
        })

    # 6. RETURN SOURCE LOCATION MISMATCH
    # Compare the return source with the asset's last
    # reliable physical location before the return request.

    rows = fetch_all("""
        SELECT
        rma_id,
        asset_id,
        source_location_id,
        requested_at,
        authorized_at,
        received_at
    FROM ReturnAuthorization
    WHERE requested_at IS NOT NULL
    """)

    for row in rows:

        # Skip location comparison when the return chronology
        # is already invalid. The chronology rule handles it.

        received = row["received_at"]
        requested = row["requested_at"]
        authorized = row["authorized_at"]

        if received is not None:
            if received < requested:
                continue

            if authorized is not None and received < authorized:
                continue


        last_movement = fetch_one("""
            SELECT
                custody_event_id,
                event_type,
                event_at,
                to_location_id
            FROM CustodyEvent
            WHERE asset_id = ?
              AND event_type IN (
                  'DISPATCH',
                  'RETURN_RECEIVED',
                  'CUSTODY_TRANSFER'
              )
              AND from_location_id <> to_location_id
              AND actor_owner_id IS NOT NULL
              AND issue_type IS NULL
              AND event_at <= ?
            ORDER BY event_at DESC, custody_event_id DESC
            LIMIT 1
        """, (row["asset_id"], row["requested_at"]))

        if not last_movement:
            continue

        expected_location = last_movement["to_location_id"]
        provided_location = row["source_location_id"]

        if expected_location != provided_location:
            exceptions.append({
                "type": "RETURN_SOURCE_LOCATION_MISMATCH",
                "record_id": row["rma_id"],
                "asset_id": row["asset_id"],
                "decision": "HOLD_RETURN_AND_VERIFY_LOCATION",
                "details": {
                    "expected_source_location": expected_location,
                    "provided_source_location": provided_location,
                    "last_movement_event": last_movement["custody_event_id"],
                    "last_movement_type": last_movement["event_type"],
                    "last_movement_at": last_movement["event_at"],
                    "return_requested_at": row["requested_at"]
                }
            })


    return {
        "total_exceptions": len(exceptions),
        "exceptions": exceptions
    }


@app.get("/analytics")
def analytics():
    asset_count = fetch_one(
        "SELECT COUNT(*) AS total FROM ReusableAsset"
    )["total"]

    shipment_count = fetch_one(
        "SELECT COUNT(*) AS total FROM Shipment"
    )["total"]

    event_count = fetch_one(
        "SELECT COUNT(*) AS total FROM CustodyEvent"
    )["total"]

    status_counts = fetch_all(
        """
        SELECT current_status, COUNT(*) AS total
        FROM ReusableAsset
        GROUP BY current_status
        """
    )

    inspection_counts = fetch_all(
        """
        SELECT result, COUNT(*) AS total
        FROM Inspection
        GROUP BY result
        """
    )

    return {
        "total_assets": asset_count,
        "total_shipments": shipment_count,
        "total_custody_events": event_count,
        "asset_status_breakdown": status_counts,
        "inspection_result_breakdown": inspection_counts
    }

# ==========================================
# RETURN AUTHORIZATION API
# ==========================================

@app.post("/returns")
def create_return(data: ReturnCreate):

    with get_connection() as connection:

        asset = connection.execute(
            """
            SELECT asset_id, current_status, is_active
            FROM ReusableAsset
            WHERE asset_id = ?
            """,
            (data.asset_id,)
        ).fetchone()

        if not asset:
            raise HTTPException(404, "Asset not found")

        if not asset["is_active"]:
            raise HTTPException(400, "Asset is inactive")

        if asset["current_status"] != "AT_CUSTOMER":
            raise HTTPException(
                409,
                "Only assets currently AT_CUSTOMER can be returned"
            )

        existing = connection.execute(
            """
            SELECT rma_id
            FROM ReturnAuthorization
            WHERE asset_id = ?
              AND return_status IN ('REQUESTED', 'AUTHORIZED')
            """,
            (data.asset_id,)
        ).fetchone()

        if existing:
            raise HTTPException(
                409,
                f"An active return already exists: {existing['rma_id']}"
            )

        check_active_location(connection, data.source_location_id)
        check_active_location(connection, data.destination_location_id)

        # Verify the asset's last reliable physical location.

        last_movement = connection.execute("""
            SELECT
                event_type,
                to_location_id,
                event_at
            FROM CustodyEvent
            WHERE asset_id = ?
            AND event_type IN (
                'DISPATCH',
                'RETURN_RECEIVED',
                'CUSTODY_TRANSFER'
            )
            AND from_location_id <> to_location_id
            AND actor_owner_id IS NOT NULL
            AND issue_type IS NULL
            ORDER BY event_at DESC, custody_event_id DESC
            LIMIT 1
        """, (data.asset_id,)).fetchone()

        if not last_movement:
            raise HTTPException(
                status_code=409,
                detail="Cannot verify the asset's last reliable physical location"
            )

        if last_movement["to_location_id"] != data.source_location_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Return source location does not match the asset's last reliable location",
                    "expected_source_location": last_movement["to_location_id"],
                    "provided_source_location": data.source_location_id,
                    "last_movement_event": last_movement["event_type"],
                    "last_movement_at": last_movement["event_at"]
                }
            )


        requested_at = validate_timestamp(
            data.requested_at or current_timestamp()
        )

        authorized_at = current_timestamp()

        if datetime.fromisoformat(requested_at) > datetime.fromisoformat(authorized_at):
            raise HTTPException(
                400,
                "Requested time cannot be in the future"
            )

        rma_id = next_id(
            connection,
            "ReturnAuthorization",
            "rma_id",
            f"RMA-{datetime.now().year}-"
        )

        connection.execute(
            """
            INSERT INTO ReturnAuthorization (
                rma_id,
                asset_id,
                requested_at,
                authorized_at,
                received_at,
                return_status,
                source_location_id,
                destination_location_id,
                reason
            )
            VALUES (?, ?, ?, ?, NULL, 'AUTHORIZED', ?, ?, ?)
            """,
            (
                rma_id,
                data.asset_id,
                requested_at,
                authorized_at,
                data.source_location_id,
                data.destination_location_id,
                data.reason
            )
        )

        return {
            "message": "Return authorization created successfully",
            "rma_id": rma_id,
            "asset_id": data.asset_id,
            "return_status": "AUTHORIZED",
            "requested_at": requested_at,
            "authorized_at": authorized_at
        }


# ==========================================
# RECEIVE RETURNED ASSET API
# ==========================================

@app.post("/returns/{rma_id}/receive")
def receive_return(rma_id: str, data: ReturnReceive):

    with get_connection() as connection:

        rma = connection.execute(
            """
            SELECT *
            FROM ReturnAuthorization
            WHERE rma_id = ?
            """,
            (rma_id,)
        ).fetchone()

        if not rma:
            raise HTTPException(404, "Return authorization not found")

        if rma["return_status"] != "AUTHORIZED":
            raise HTTPException(
                409,
                "Only authorized returns can be received"
            )

        check_active_owner(connection, data.actor_owner_id)

        received_at = validate_timestamp(
            data.received_at or current_timestamp()
        )

        authorized_at = datetime.fromisoformat(rma["authorized_at"])
        received_datetime = datetime.fromisoformat(received_at)

        if received_datetime < authorized_at:
            raise HTTPException(
                400,
                "Received time cannot be earlier than authorization time"
            )

        asset_id = rma["asset_id"]

        connection.execute(
            """
            UPDATE ReturnAuthorization
            SET received_at = ?,
                return_status = 'RECEIVED'
            WHERE rma_id = ?
            """,
            (received_at, rma_id)
        )

        connection.execute(
            """
            UPDATE ReusableAsset
            SET current_status = 'AVAILABLE'
            WHERE asset_id = ?
            """,
            (asset_id,)
        )

        custody_prefix = f"CUST-{asset_id}-"

        custody_id = next_id(
            connection,
            "CustodyEvent",
            "custody_event_id",
            custody_prefix
        )

        connection.execute(
            """
            INSERT INTO CustodyEvent (
                custody_event_id,
                asset_id,
                shipment_id,
                event_type,
                event_at,
                from_location_id,
                to_location_id,
                actor_owner_id,
                notes,
                issue_type
            )
            VALUES (?, ?, NULL, 'RETURN_RECEIVED', ?, ?, ?, ?, ?, NULL)
            """,
            (
                custody_id,
                asset_id,
                received_at,
                rma["source_location_id"],
                rma["destination_location_id"],
                data.actor_owner_id,
                data.notes or "Asset physically received at return destination"
            )
        )

        return {
            "message": "Asset return received successfully",
            "rma_id": rma_id,
            "asset_id": asset_id,
            "return_status": "RECEIVED",
            "asset_status": "AVAILABLE",
            "custody_event_id": custody_id,
            "received_at": received_at
        }

# ==========================================
# CREATE ASSET INSPECTION API
# ==========================================

@app.post("/inspections")
def create_inspection(data: InspectionCreate):

    allowed_results = [
        "PASS",
        "MINOR_DAMAGE",
        "MAJOR_DAMAGE",
        "MISSING_PARTS"
    ]

    if data.result not in allowed_results:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid result. Choose: {allowed_results}"
        )

    with get_connection() as connection:

        # 1. Check return authorization
        rma = connection.execute(
            """
            SELECT rma_id, asset_id, return_status, received_at
            FROM ReturnAuthorization
            WHERE rma_id = ?
            """,
            (data.rma_id,)
        ).fetchone()

        if not rma:
            raise HTTPException(
                status_code=404,
                detail="Return authorization not found"
            )

        if rma["return_status"] != "RECEIVED":
            raise HTTPException(
                status_code=409,
                detail="Asset must be physically received before inspection"
            )

        # 2. Prevent duplicate inspections for the same return
        existing = connection.execute(
            """
            SELECT inspection_id
            FROM Inspection
            WHERE rma_id = ?
            """,
            (data.rma_id,)
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Inspection already exists: {existing['inspection_id']}"
            )

        # 3. Validate inspector
        check_active_owner(connection, data.inspector_owner_id)

        # 4. Validate inspection timestamp
        inspected_at = validate_timestamp(
            data.inspected_at or current_timestamp()
        )

        if rma["received_at"]:
            received_at = datetime.fromisoformat(rma["received_at"])
            inspection_time = datetime.fromisoformat(inspected_at)

            if inspection_time < received_at:
                raise HTTPException(
                    status_code=400,
                    detail="Inspection cannot happen before asset receipt"
                )

        # 5. Generate inspection ID
        inspection_id = next_id(
            connection,
            "Inspection",
            "inspection_id",
            "INSP-",
            width=7
        )

        # 6. Save inspection
        connection.execute(
            """
            INSERT INTO Inspection (
                inspection_id,
                rma_id,
                asset_id,
                inspected_at,
                inspector_owner_id,
                result,
                damage_cost,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inspection_id,
                data.rma_id,
                rma["asset_id"],
                inspected_at,
                data.inspector_owner_id,
                data.result,
                data.damage_cost,
                data.notes
            )
        )

        return {
            "message": "Asset inspection recorded successfully",
            "inspection_id": inspection_id,
            "rma_id": data.rma_id,
            "asset_id": rma["asset_id"],
            "result": data.result,
            "damage_cost": data.damage_cost,
            "inspected_at": inspected_at
        }


# ==========================================
# CREATE REPAIR API
# ==========================================

@app.post("/repairs")
def create_repair(data: RepairCreate):

    with get_connection() as connection:

        # 1. Verify inspection
        inspection = connection.execute(
            """
            SELECT inspection_id, asset_id, result, inspected_at
            FROM Inspection
            WHERE inspection_id = ?
            """,
            (data.inspection_id,)
        ).fetchone()

        if not inspection:
            raise HTTPException(404, "Inspection not found")

        if inspection["asset_id"] != data.asset_id:
            raise HTTPException(
                400,
                "Inspection does not belong to this asset"
            )

        if inspection["result"] not in (
            "MINOR_DAMAGE",
            "MAJOR_DAMAGE",
            "MISSING_PARTS"
        ):
            raise HTTPException(
                409,
                "Repair cannot be opened for a PASS inspection"
            )

        # 2. Verify asset
        asset = connection.execute(
            """
            SELECT asset_id, current_status, is_active
            FROM ReusableAsset
            WHERE asset_id = ?
            """,
            (data.asset_id,)
        ).fetchone()

        if not asset:
            raise HTTPException(404, "Asset not found")

        if not asset["is_active"]:
            raise HTTPException(400, "Asset is inactive")

        # 3. Validate repair location
        check_active_location(
            connection,
            data.repair_center_location_id
        )

        # 4. Prevent multiple active repairs
        existing = connection.execute(
            """
            SELECT repair_id
            FROM Repair
            WHERE asset_id = ?
              AND repair_status IN ('OPEN', 'IN_PROGRESS')
            """,
            (data.asset_id,)
        ).fetchone()

        if existing:
            raise HTTPException(
                409,
                f"An active repair already exists: {existing['repair_id']}"
            )

        # 5. Generate repair ID
        repair_id = next_id(
            connection,
            "Repair",
            "repair_id",
            f"REP-{datetime.now().year}-",
            width=6
        )

        opened_at = current_timestamp()

        # 6. Save repair
        connection.execute(
            """
            INSERT INTO Repair (
                repair_id,
                asset_id,
                inspection_id,
                opened_at,
                closed_at,
                repair_status,
                repair_cost,
                repair_center_location_id
            )
            VALUES (?, ?, ?, ?, NULL, 'OPEN', ?, ?)
            """,
            (
                repair_id,
                data.asset_id,
                data.inspection_id,
                opened_at,
                data.repair_cost,
                data.repair_center_location_id
            )
        )

        return {
            "message": "Repair opened successfully",
            "repair_id": repair_id,
            "asset_id": data.asset_id,
            "inspection_id": data.inspection_id,
            "repair_status": "OPEN",
            "opened_at": opened_at
        }


# ==========================================
# CLOSE REPAIR API
# ==========================================

@app.post("/repairs/{repair_id}/close")
def close_repair(
    repair_id: str,
    data: RepairClose
):

    with get_connection() as connection:

        repair = connection.execute(
            """
            SELECT *
            FROM Repair
            WHERE repair_id = ?
            """,
            (repair_id,)
        ).fetchone()

        if not repair:
            raise HTTPException(404, "Repair not found")

        if repair["repair_status"] not in ("OPEN", "IN_PROGRESS"):
            raise HTTPException(
                409,
                "Only open or in-progress repairs can be closed"
            )

        if not repair["inspection_id"]:
            raise HTTPException(
                409,
                "Repair cannot close without a valid inspection"
            )

        inspection = connection.execute(
            """
            SELECT inspection_id
            FROM Inspection
            WHERE inspection_id = ?
              AND asset_id = ?
            """,
            (repair["inspection_id"], repair["asset_id"])
        ).fetchone()

        if not inspection:
            raise HTTPException(
                409,
                "A valid matching inspection is required"
            )

        closed_at = validate_timestamp(
            data.closed_at or current_timestamp()
        )

        opened_at = datetime.fromisoformat(repair["opened_at"])
        closing_time = datetime.fromisoformat(closed_at)

        if closing_time < opened_at:
            raise HTTPException(
                400,
                "Repair cannot close before it was opened"
            )

        connection.execute(
            """
            UPDATE Repair
            SET closed_at = ?,
                repair_status = 'COMPLETED'
            WHERE repair_id = ?
            """,
            (closed_at, repair_id)
        )

        return {
            "message": "Repair completed successfully",
            "repair_id": repair_id,
            "asset_id": repair["asset_id"],
            "repair_status": "COMPLETED",
            "closed_at": closed_at
        }


# ==========================================
# CREATE DEPOSIT TRANSACTION API
# ==========================================

@app.post("/deposits")
def create_deposit(data: DepositCreate):

    allowed_types = [
        "DEPOSIT_CHARGE",
        "DEPOSIT_REFUND"
    ]

    if data.entry_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entry_type. Choose: {allowed_types}"
        )

    if not data.reference.strip():
        raise HTTPException(
            status_code=400,
            detail="Transaction reference cannot be empty"
        )

    if not data.currency.strip():
        raise HTTPException(
            status_code=400,
            detail="Currency cannot be empty"
        )

    with get_connection() as connection:

        # 1. Verify asset
        asset = connection.execute(
            """
            SELECT asset_id
            FROM ReusableAsset
            WHERE asset_id = ?
            """,
            (data.asset_id,)
        ).fetchone()

        if not asset:
            raise HTTPException(404, "Asset not found")

        # 2. Verify RMA, when supplied
        if data.rma_id:
            rma = connection.execute(
                """
                SELECT rma_id, asset_id, return_status
                FROM ReturnAuthorization
                WHERE rma_id = ?
                """,
                (data.rma_id,)
            ).fetchone()

            if not rma:
                raise HTTPException(
                    404,
                    "Return authorization not found"
                )

            if rma["asset_id"] != data.asset_id:
                raise HTTPException(
                    400,
                    "Return authorization does not belong to this asset"
                )

        # 3. Refund-specific validation
        if data.entry_type == "DEPOSIT_REFUND":

            if not data.rma_id:
                raise HTTPException(
                    400,
                    "A return authorization is required for a refund"
                )

            if rma["return_status"] != "RECEIVED":
                raise HTTPException(
                    409,
                    "Refund is allowed only after the asset is received"
                )

            # Prevent duplicate refunds for the same return and amount
            duplicate = connection.execute(
                """
                SELECT ledger_entry_id
                FROM DepositLedger
                WHERE asset_id = ?
                  AND rma_id = ?
                  AND entry_type = 'DEPOSIT_REFUND'
                  AND amount = ?
                  AND currency = ?
                """,
                (
                    data.asset_id,
                    data.rma_id,
                    data.amount,
                    data.currency
                )
            ).fetchone()

            if duplicate:
                raise HTTPException(
                    409,
                    f"Duplicate refund detected: {duplicate['ledger_entry_id']}"
                )

            # Calculate available refundable balance
            balance = connection.execute(
                """
                SELECT
                    COALESCE(
                        SUM(
                            CASE
                                WHEN entry_type = 'DEPOSIT_CHARGE'
                                THEN amount
                                WHEN entry_type = 'DEPOSIT_REFUND'
                                THEN -amount
                                ELSE 0
                            END
                        ), 0
                    ) AS available_balance
                FROM DepositLedger
                WHERE asset_id = ?
                  AND currency = ?
                """,
                (data.asset_id, data.currency)
            ).fetchone()["available_balance"]

            if data.amount > balance:
                raise HTTPException(
                    409,
                    f"Refund exceeds available deposit balance: {balance}"
                )

        # 4. Generate ledger ID
        ledger_id = next_id(
            connection,
            "DepositLedger",
            "ledger_entry_id",
            "LED-",
            width=8
        )

        posted_at = current_timestamp()

        # 5. Save transaction
        connection.execute(
            """
            INSERT INTO DepositLedger (
                ledger_entry_id,
                asset_id,
                rma_id,
                entry_type,
                amount,
                currency,
                posted_at,
                reference
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ledger_id,
                data.asset_id,
                data.rma_id,
                data.entry_type,
                data.amount,
                data.currency,
                posted_at,
                data.reference
            )
        )

        return {
            "message": "Deposit transaction recorded successfully",
            "ledger_entry_id": ledger_id,
            "asset_id": data.asset_id,
            "rma_id": data.rma_id,
            "entry_type": data.entry_type,
            "amount": data.amount,
            "currency": data.currency,
            "posted_at": posted_at
        }


# ==========================================
# GET DEPOSIT TRANSACTION HISTORY
# ==========================================

@app.get("/deposits/{asset_id}")
def get_deposit_history(asset_id: str):

    with get_connection() as connection:

        asset = connection.execute(
            """
            SELECT asset_id
            FROM ReusableAsset
            WHERE asset_id = ?
            """,
            (asset_id,)
        ).fetchone()

        if not asset:
            raise HTTPException(404, "Asset not found")

        transactions = connection.execute(
            """
            SELECT *
            FROM DepositLedger
            WHERE asset_id = ?
            ORDER BY posted_at, ledger_entry_id
            """,
            (asset_id,)
        ).fetchall()

        return {
            "asset_id": asset_id,
            "transaction_count": len(transactions),
            "transactions": [
                dict(row) for row in transactions
            ]
        }


# ==========================================
# GET DEPOSIT BALANCE
# ==========================================

@app.get("/deposits/{asset_id}/balance")
def get_deposit_balance(asset_id: str):

    with get_connection() as connection:

        asset = connection.execute(
            """
            SELECT asset_id
            FROM ReusableAsset
            WHERE asset_id = ?
            """,
            (asset_id,)
        ).fetchone()

        if not asset:
            raise HTTPException(404, "Asset not found")

        balances = connection.execute(
            """
            SELECT
                currency,
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
            (asset_id,)
        ).fetchall()

        return {
            "asset_id": asset_id,
            "balances": [
                {
                    "currency": row["currency"],
                    "balance": round(row["balance"], 2)
                }
                for row in balances
            ]
        }
