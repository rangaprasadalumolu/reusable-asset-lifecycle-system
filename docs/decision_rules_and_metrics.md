# Decision rules and evaluation

## Derived operational measures
- `days_outstanding`: max(0, snapshot date - dispatch/delivery effective date) for assets with no valid return receipt.
- `is_overdue`: days_outstanding > AssetType.return_sla_days.
- `potential_loss`: no valid return and days_outstanding > AssetType.loss_threshold_days.
- `deposit_balance`: total deposit charges + positive adjustments - deposit refunds; report negative balances as financial exceptions.
- `custody_conflict`: overlapping active location claims for the same asset.
- `duplicate_refund`: more than one deposit refund for the same asset/deposit cycle.
- `repair_without_inspection`: completed repair with no linked inspection.
- `missing_actor`: custody event actor is null.

## Expected anomaly decisions (ground truth)
1. SIMULTANEOUS_LOCATIONS -> quarantine asset and request evidence.
2. RETURN_BEFORE_DISPATCH -> reject return receipt and review event chronology.
3. DUPLICATE_DEPOSIT_REFUND -> reverse duplicate credit after approval and flag financial control.
4. REPAIR_WITHOUT_INSPECTION -> reopen / hold repair closure pending inspection evidence.
5. MISSING_CUSTODY_ACTOR -> hold event for accountable actor/evidence.

## Metrics
- Traceability coverage = assets with a reconstructable latest location / assets with custody history.
- On-time return rate = valid returns within type SLA / all valid returns.
- Potential loss rate = potential-loss assets / dispatched assets.
- Damage rate = inspected assets with non-PASS result / inspected assets.
- Deposit reconciliation rate = assets whose ledger balance matches expected deposit liability / assets with deposit entries.
- Exception precision/recall/F1 = predicted exception labels compared with ground_truth.csv.
- Data integrity = FK-valid rows / rows subject to FK constraints; PK uniqueness = distinct PK / rows.

Ground truth is held separately and excluded from model input. For robust evaluation, split by asset ID so events from one asset cannot leak across train/test.
