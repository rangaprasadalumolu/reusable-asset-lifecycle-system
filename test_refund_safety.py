
import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

import app as app_module
from concurrent.futures import ThreadPoolExecutor


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    # Copy the real database into a temporary test folder
    original_db = app_module.DB_PATH
    test_db = tmp_path / "test_assets.db"

    shutil.copy2(original_db, test_db)

    # Redirect the application to the temporary database
    monkeypatch.setattr(app_module, "DB_PATH", test_db)

    with TestClient(app_module.app) as client:
        yield client, test_db


def refund_payload(asset_id, rma_id, amount, reference):
    return {
        "asset_id": asset_id,
        "rma_id": rma_id,
        "entry_type": "DEPOSIT_REFUND",
        "amount": amount,
        "currency": "INR",
        "reference": reference
    }


def refund_count(db_path, asset_id, rma_id):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            """
            SELECT COUNT(*)
            FROM DepositLedger
            WHERE asset_id = ?
              AND rma_id = ?
              AND entry_type = 'DEPOSIT_REFUND'
            """,
            (asset_id, rma_id)
        ).fetchone()[0]


def test_duplicate_refund_rejected(test_client):
    client, db = test_client

    before = refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    )

    response = client.post(
        "/deposits",
        json=refund_payload(
            "ASSET-0000005",
            "RMA-2026-000812",
            500,
            "TEST-DUPLICATE-REFUND"
        )
    )

    assert response.status_code == 409
    assert refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    ) == before


def test_valid_additional_refund_accepted(test_client):
    client, db = test_client

    before = refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    )

    response = client.post(
        "/deposits",
        json=refund_payload(
            "ASSET-0000005",
            "RMA-2026-000812",
                        700,
            "TEST-VALID-REFUND-001"
        )
    )

    assert response.status_code == 200
    assert response.json()["amount"] == 700

    assert refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    ) == before + 1


def test_excessive_refund_rejected(test_client):
    client, db = test_client

    before = refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    )

    response = client.post(
        "/deposits",
        json=refund_payload(
            "ASSET-0000005",
            "RMA-2026-000812",
            2001,
            "TEST-EXCESSIVE-REFUND"
        )
    )

    assert response.status_code == 409
    assert refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    ) == before


def test_unlinked_deposit_cannot_fund_refund(test_client):
    client, db = test_client

    before = refund_count(
        db, "ASSET-0000010", "RMA-2026-000811"
    )

    response = client.post(
        "/deposits",
        json=refund_payload(
            "ASSET-0000010",
            "RMA-2026-000811",
            100,
            "TEST-ASSET10-REFUND"
        )
    )

    assert response.status_code == 409
    assert "No eligible RMA-linked deposit" in response.json()["detail"]

    assert refund_count(
        db, "ASSET-0000010", "RMA-2026-000811"
    ) == before


@pytest.mark.parametrize("amount", [0, -100])
def test_non_positive_amount_rejected(test_client, amount):
    client, db = test_client

    before = refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    )

    response = client.post(
        "/deposits",
        json=refund_payload(
            "ASSET-0000005",
            "RMA-2026-000812",
            amount,
            "TEST-INVALID-AMOUNT"
        )
    )

    assert response.status_code == 422

    assert refund_count(
        db, "ASSET-0000005", "RMA-2026-000812"
    ) == before


def test_simultaneous_refunds_cannot_exceed_balance(test_client):
    client, db = test_client

    asset_id = "ASSET-0000005"
    rma_id = "RMA-2026-000812"

    before = refund_count(db, asset_id, rma_id)

    requests = [
        refund_payload(
            asset_id,
            rma_id,
            1200,
            "TEST-CONCURRENT-REFUND-A"
        ),
        refund_payload(
            asset_id,
            rma_id,
            1000,
            "TEST-CONCURRENT-REFUND-B"
        )
    ]

    # Submit both refund requests simultaneously
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                client.post,
                "/deposits",
                json=payload
            )
            for payload in requests
        ]

        responses = [future.result() for future in futures]

    status_codes = sorted(
        response.status_code for response in responses
    )

    # Exactly one refund must succeed
    assert status_codes == [200, 409]

    # Only one new refund must be recorded
    after = refund_count(db, asset_id, rma_id)
    assert after == before + 1

    # Remaining balance must never be negative
    with sqlite3.connect(db) as conn:
        balance = conn.execute(
            """
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
              AND currency = 'INR'
            """,
            (asset_id, rma_id)
        ).fetchone()[0]

    assert balance >= 0

