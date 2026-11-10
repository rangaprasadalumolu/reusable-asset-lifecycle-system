# Reusable Asset Lifecycle & Return Management

## Quick start
Requires Python 3.10+; no third-party packages required.

```bash
# Starter: 1,000 assets, 500 shipments, 5,000 baseline custody events + labelled anomalies
python generate.py --scale 1000 --seed 20261022 --out data/starter

# Full requested scale: 20,000 assets, 10,000 shipments, 100,000 baseline custody events + labelled anomalies
python generate.py --scale 20000 --seed 20261022 --out data/full
```

The generator uses one fixed seed and deterministic ID counters. `ground_truth.csv` is a separate evaluation-only file; do not load it into model features. `source_manifest.json` contains SHA-256 hashes for generated CSVs. `validation_summary.json` records counts and basic validation metadata.

## Files
- `generate.py`: deterministic synthetic generator; scale parameter preserves the same rules.
- `schema.sql`: relational schema with primary keys, foreign keys, constraints and ShipmentAsset bridge.
- `docs/data_dictionary.md`: fields, types, constraints and cardinalities.
- `data/`: starter sample and validation artifacts in this package.

## Workflow
1. Load master data: Owner, Location, AssetType.
2. Load ReusableAsset and Shipment.
3. Load ShipmentAsset bridge.
4. Load event/transaction tables: CustodyEvent, ReturnAuthorization, Inspection, Repair, DepositLedger.
5. Derive asset location from ordered custody events, not by trusting a mutable location field.
6. Calculate days outstanding as snapshot date minus latest valid dispatch/delivery date for assets not returned/closed.
7. Reconcile deposit balance per asset: charges + adjustments - refunds (apply signed transaction convention in analytics).
8. Route exceptions to operations review; never silently repair source history.

## Ground-truth anomaly policy
Five intentional negative scenarios are appended after valid baseline generation: simultaneous locations, return before dispatch, duplicate deposit refund, repair completed without inspection, and missing custody actor. The anomaly rows retain parent IDs where applicable; missing actor and missing inspection are nullable relationships by design. Use `issue_type` plus `ground_truth.csv` for evaluation. These anomalies are not random labels.

## Important implementation note
This is a synthetic-data and relational foundation, not a production logistics integration. Before production, add authentication, authorization, idempotency keys, audit controls, timezone policy, event ingestion contracts, operational retry/dead-letter handling, and a formally approved lost-asset policy.
