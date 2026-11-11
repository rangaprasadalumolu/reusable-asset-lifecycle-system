BEGIN IMMEDIATE;

CREATE INDEX IF NOT EXISTS idx_asset_status
ON ReusableAsset(current_status);

CREATE INDEX IF NOT EXISTS idx_custody_asset_event
ON CustodyEvent(asset_id, event_at, custody_event_id);

CREATE INDEX IF NOT EXISTS idx_return_asset_status
ON ReturnAuthorization(asset_id, return_status);

CREATE INDEX IF NOT EXISTS idx_inspection_rma
ON Inspection(rma_id);

CREATE INDEX IF NOT EXISTS idx_repair_asset_status
ON Repair(asset_id, repair_status);

CREATE INDEX IF NOT EXISTS idx_deposit_asset_rma_currency
ON DepositLedger(asset_id, rma_id, currency);

COMMIT;