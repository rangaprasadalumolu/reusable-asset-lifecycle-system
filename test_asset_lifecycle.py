import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

import app as app_module


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    original_db = app_module.DB_PATH
    test_db = tmp_path / "test_assets.db"

    shutil.copy2(original_db, test_db)
    monkeypatch.setattr(app_module, "DB_PATH", test_db)

    with TestClient(app_module.app) as client:
        yield client, test_db


def get_asset_status(db_path, asset_id):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT current_status FROM ReusableAsset WHERE asset_id = ?",
            (asset_id,)
        ).fetchone()
        return row[0]


def create_received_return(client):
    response = client.post(
        "/returns",
        json={
            "asset_id": "ASSET-0000008",
            "source_location_id": "LOC-0033",
            "destination_location_id": "LOC-0001",
            "reason": "TEST_LIFECYCLE"
        }
    )
    assert response.status_code == 200, response.text

    rma_id = response.json()["rma_id"]

    response = client.post(
        f"/returns/{rma_id}/receive",
        json={"actor_owner_id": "OWN-0001"}
    )
    assert response.status_code == 200, response.text

    return rma_id


def test_passed_inspection_makes_asset_available(test_client):
    client, db = test_client
    asset_id = "ASSET-0000008"

    assert get_asset_status(db, asset_id) == "AT_CUSTOMER"

    rma_id = create_received_return(client)

    assert get_asset_status(db, asset_id) == "INSPECTION"

    response = client.post(
        "/inspections",
        json={
            "rma_id": rma_id,
            "inspector_owner_id": "OWN-0001",
            "result": "PASS",
            "damage_cost": 0
        }
    )
    assert response.status_code == 200, response.text
    assert get_asset_status(db, asset_id) == "AVAILABLE"


def test_damaged_asset_becomes_available_after_repair(test_client):
    client, db = test_client
    asset_id = "ASSET-0000008"

    rma_id = create_received_return(client)

    assert get_asset_status(db, asset_id) == "INSPECTION"

    response = client.post(
        "/inspections",
        json={
            "rma_id": rma_id,
            "inspector_owner_id": "OWN-0001",
            "result": "MAJOR_DAMAGE",
            "damage_cost": 1500
        }
    )
    assert response.status_code == 200, response.text

    inspection_id = response.json()["inspection_id"]

    assert get_asset_status(db, asset_id) == "INSPECTION"

    response = client.post(
        "/repairs",
        json={
            "asset_id": asset_id,
            "inspection_id": inspection_id,
            "repair_center_location_id": "LOC-0001",
            "repair_cost": 500
        }
    )
    assert response.status_code == 200, response.text

    repair_id = response.json()["repair_id"]

    assert get_asset_status(db, asset_id) == "REPAIR"

    response = client.post(
        f"/repairs/{repair_id}/close",
        json={}
    )
    assert response.status_code == 200, response.text

    assert get_asset_status(db, asset_id) == "AVAILABLE"
