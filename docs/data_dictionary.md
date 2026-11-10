# Data dictionary

All timestamps are ISO-8601 local synthetic timestamps; currency amounts are INR. `required` means non-null in valid baseline records. Empty actor/inspection links occur only in explicitly labelled anomaly cases.

| Entity | Field | Type | Req. | Validation / meaning |
|---|---|---:|:---:|---|
| AssetType | asset_type_id | string PK | Y | AT-### immutable |
| AssetType | type_code, description | string | Y | type_code unique |
| AssetType | return_sla_days, loss_threshold_days, repair_sla_days | integer days | Y | positive |
| AssetType | deposit_amount | decimal INR | Y | >= 0 |
| AssetType | active | boolean | Y | 0/1 |
| ReusableAsset | asset_id | string PK | Y | ASSET-####### immutable |
| ReusableAsset | asset_type_id, owner_id, home_location_id | FK string | Y | must reference master rows |
| ReusableAsset | serial_number | string | Y | unique |
| ReusableAsset | created_at | timestamp | Y | <= snapshot time |
| ReusableAsset | current_status | enum | Y | AVAILABLE, IN_TRANSIT, AT_CUSTOMER, RETURN_PENDING, INSPECTION, REPAIR, LOST, RETIRED |
| ReusableAsset | deposit_amount | decimal INR | Y | >= 0; sourced from AssetType |
| ReusableAsset | is_active | boolean | Y | 0/1 |
| Owner | owner_id | string PK | Y | OWN-#### |
| Owner | owner_name, owner_type | string / enum | Y | supplier, customer, carrier, warehouse, pool operator |
| Owner | active | boolean | Y | 0/1 |
| Location | location_id | string PK | Y | LOC-#### |
| Location | location_name, city, country | string | Y | synthetic operational location |
| Location | location_type | enum | Y | DEPOT, CUSTOMER, WAREHOUSE, REPAIR_CENTER |
| Location | active | boolean | Y | 0/1 |
| Shipment | shipment_id | string PK | Y | SHP-2026-###### |
| Shipment | origin_location_id, destination_location_id, carrier_owner_id | FK string | Y | valid master IDs |
| Shipment | dispatch_at, expected_delivery_at | timestamp | Y | expected >= dispatch |
| Shipment | shipment_status | enum | Y | PLANNED, IN_TRANSIT, DELIVERED, EXCEPTION |
| Shipment | tracking_reference | string | Y | unique |
| ShipmentAsset | shipment_id, asset_id | FK string | Y | composite PK; bridge for shipment/assets M:N |
| ShipmentAsset | quantity | integer | Y | > 0 |
| CustodyEvent | custody_event_id | string PK | Y | CUST-<asset-id>-###### |
| CustodyEvent | asset_id | FK string | Y | valid asset |
| CustodyEvent | shipment_id | nullable FK | N | valid shipment when present |
| CustodyEvent | event_type | enum | Y | DISPATCH, CUSTODY_TRANSFER, DELIVERY, RETURN_RECEIVED, INSPECTION, REPAIR_OPENED, REPAIR_CLOSED, LOST_DECLARED |
| CustodyEvent | event_at | timestamp | Y | chronological ordering checked per asset |
| CustodyEvent | from_location_id, to_location_id | nullable FK | N | valid locations |
| CustodyEvent | actor_owner_id | nullable FK | normally Y | null only for labelled MISSING_CUSTODY_ACTOR |
| CustodyEvent | notes, issue_type | string | N | anomaly label kept on event |
| ReturnAuthorization | rma_id | string PK | Y | RMA-2026-###### |
| ReturnAuthorization | asset_id | FK string | Y | valid asset |
| ReturnAuthorization | requested_at | timestamp | Y | <= authorized_at |
| ReturnAuthorization | authorized_at, received_at | timestamp | N | receipt must follow dispatch in valid baseline |
| ReturnAuthorization | return_status | enum | Y | REQUESTED, AUTHORIZED, IN_TRANSIT, RECEIVED, CLOSED, REJECTED |
| ReturnAuthorization | source_location_id, destination_location_id | FK string | Y | valid locations |
| ReturnAuthorization | reason | string | Y | operational reason |
| Inspection | inspection_id | string PK | Y | INSP-####### |
| Inspection | rma_id, asset_id, inspector_owner_id | FK string | Y | valid parents |
| Inspection | inspected_at | timestamp | Y | >= received_at for valid baseline |
| Inspection | result | enum | Y | PASS, MINOR_DAMAGE, MAJOR_DAMAGE, MISSING_PARTS |
| Inspection | damage_cost | decimal INR | Y | >= 0 |
| Inspection | notes | string | N | inspection observations |
| Repair | repair_id | string PK | Y | REP-2026-###### |
| Repair | asset_id, repair_center_location_id | FK string | Y | valid parents |
| Repair | inspection_id | nullable FK | normally Y | null only for labelled anomaly |
| Repair | opened_at, closed_at | timestamp | Y/N | closed >= opened |
| Repair | repair_status | enum | Y | OPEN, IN_PROGRESS, COMPLETED, CANCELLED |
| Repair | repair_cost | decimal INR | Y | >= 0 |
| DepositLedger | ledger_entry_id | string PK | Y | LED-######## |
| DepositLedger | asset_id | FK string | Y | valid asset |
| DepositLedger | rma_id | nullable FK | N | valid RMA when present |
| DepositLedger | entry_type | enum | Y | DEPOSIT_CHARGE, DEPOSIT_REFUND, DAMAGE_CHARGE, ADJUSTMENT |
| DepositLedger | amount | decimal INR | Y | >= 0; refunds are positive credits |
| DepositLedger | currency | string | Y | INR |
| DepositLedger | posted_at | timestamp | Y | ledger posting time |
| DepositLedger | reference | string | Y | source transaction / reconciliation key |

## Relationships and cardinality

- AssetType 1:N ReusableAsset; Owner 1:N ReusableAsset; Location 1:N ReusableAsset as home location.
- Location 1:N Shipment as origin and destination; Owner 1:N Shipment as carrier.
- Shipment N:M ReusableAsset through ShipmentAsset.
- ReusableAsset 1:N CustodyEvent, ReturnAuthorization, Inspection, Repair and DepositLedger.
- Shipment 1:N CustodyEvent (optional shipment reference on non-shipment events).
- ReturnAuthorization 1:N Inspection; Inspection 1:N Repair (inspection link optional only for labelled negative case).
- Owner 1:N CustodyEvent as actor (actor optional only for the missing-actor anomaly).
- Location 1:N CustodyEvent as from/to location.

History is append-only: current status is a derived snapshot; custody events and ledger postings are not overwritten. Effective time is represented by event_at / posted_at; record creation time is implicit in this synthetic extract.
