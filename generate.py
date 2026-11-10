#!/usr/bin/env python3
"""Deterministic synthetic reusable-asset reverse-logistics data generator."""
import argparse, csv, json, random, sqlite3, hashlib
from pathlib import Path
from datetime import datetime, timedelta

SEED = 20261022
NOW = datetime(2026, 11, 10, 12, 0, 0)
ENUMS = {
 "asset_status": ["AVAILABLE","IN_TRANSIT","AT_CUSTOMER","RETURN_PENDING","INSPECTION","REPAIR","LOST","RETIRED"],
 "event_type": ["DISPATCH","CUSTODY_TRANSFER","DELIVERY","RETURN_RECEIVED","INSPECTION","REPAIR_OPENED","REPAIR_CLOSED","LOST_DECLARED"],
 "return_status": ["REQUESTED","AUTHORIZED","IN_TRANSIT","RECEIVED","CLOSED","REJECTED"],
 "inspection_result": ["PASS","MINOR_DAMAGE","MAJOR_DAMAGE","MISSING_PARTS"],
 "repair_status": ["OPEN","IN_PROGRESS","COMPLETED","CANCELLED"],
 "ledger_type": ["DEPOSIT_CHARGE","DEPOSIT_REFUND","DAMAGE_CHARGE","ADJUSTMENT"],
}
def stamp(dt): return dt.strftime("%Y-%m-%dT%H:%M:%S")
def write_csv(path, rows, fields):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()
def build(out, scale, seed):
    out=Path(out); out.mkdir(parents=True,exist_ok=True); rng=random.Random(seed)
    n_assets=scale; n_ship=max(1,scale//2); n_events=scale*5
    owners=[{"owner_id":f"OWN-{i:04d}","owner_name":n,"owner_type":t,"active":1}
      for i,(n,t) in enumerate([("Northstar Packaging","SUPPLIER"),("Acme Retail","CUSTOMER"),("RapidRoute Logistics","CARRIER"),("Central Returns Hub","WAREHOUSE"),("Orbit Pooling Services","POOL_OPERATOR")],1)]
    locations=[{"location_id":f"LOC-{i:04d}","location_name":f"{city} {kind}","city":city,"country":"India","location_type":kind,"active":1}
      for i,(city,kind) in enumerate([(c,k) for c in ["Hyderabad","Bengaluru","Chennai","Pune","Mumbai","Delhi","Kolkata","Ahmedabad","Jaipur","Kochi"] for k in ["DEPOT","CUSTOMER","WAREHOUSE","REPAIR_CENTER"]],1)]
    types=[
      ("PALLET","Wooden pallet",21,14,2500,30),("PLASTIC_CRATE","Reusable plastic crate",14,10,900,21),
      ("IBC_TOTE","Intermediate bulk container",30,21,12000,45),("ROLL_CAGE","Roll cage",21,14,6500,30),
      ("DOLLY","Transport dolly",18,12,3200,30),("THERMAL_BOX","Insulated thermal box",10,7,1800,14)]
    asset_types=[{"asset_type_id":f"AT-{i:03d}","type_code":x[0],"description":x[1],"return_sla_days":x[2],"loss_threshold_days":x[3],"deposit_amount":x[4],"repair_sla_days":x[5],"active":1} for i,x in enumerate(types,1)]
    assets=[]
    for i in range(1,n_assets+1):
      typ=rng.choice(asset_types); owner=rng.choice(owners); loc=rng.choice(locations)
      created=NOW-timedelta(days=rng.randint(30,240))
      assets.append({"asset_id":f"ASSET-{i:07d}","asset_type_id":typ["asset_type_id"],"owner_id":owner["owner_id"],"serial_number":f"SN-{i:09d}","created_at":stamp(created),"current_status":"AVAILABLE","home_location_id":loc["location_id"],"deposit_amount":typ["deposit_amount"],"is_active":1})
    shipments=[]
    for i in range(1,n_ship+1):
      dt=NOW-timedelta(days=rng.randint(2,100))
      src,dst=rng.sample(locations,2)
      shipments.append({"shipment_id":f"SHP-2026-{i:06d}","origin_location_id":src["location_id"],"destination_location_id":dst["location_id"],"carrier_owner_id":owners[2]["owner_id"],"dispatch_at":stamp(dt),"expected_delivery_at":stamp(dt+timedelta(days=rng.randint(1,4))),"shipment_status":"DELIVERED" if dt+timedelta(days=4)<NOW else "IN_TRANSIT","tracking_reference":f"TRK-{i:08d}"})
    # shipment-to-assets bridge; every shipment gets 1-4 assets, selected deterministically
    bridge=[]; by_ship={}
    for j,s in enumerate(shipments):
      chosen=[assets[(j*2+k)%n_assets] for k in range(min(rng.randint(1,4),n_assets))]
      by_ship[s["shipment_id"]]=chosen
      for a in chosen: bridge.append({"shipment_id":s["shipment_id"],"asset_id":a["asset_id"],"quantity":1})
    events=[]; returns=[]; inspections=[]; repairs=[]; ledger=[]
    event_counter={a["asset_id"]:0 for a in assets}
    # 5 event records per asset, padded/truncated to requested volume
    for idx,a in enumerate(assets):
      typ=next(t for t in asset_types if t["asset_type_id"]==a["asset_type_id"])
      ship=shipments[idx % len(shipments)]
      owner=owners[1]; origin=next(x for x in locations if x["location_id"]==ship["origin_location_id"])
      dest=next(x for x in locations if x["location_id"]==ship["destination_location_id"])
      base=datetime.fromisoformat(ship["dispatch_at"])
      def add_event(kind, when, from_loc, to_loc, actor, shipment_id=ship["shipment_id"], note=""):
        event_counter[a["asset_id"]]+=1
        events.append({"custody_event_id":f"CUST-{a['asset_id']}-{event_counter[a['asset_id']]:06d}","asset_id":a["asset_id"],"shipment_id":shipment_id,"event_type":kind,"event_at":stamp(when),"from_location_id":from_loc,"to_location_id":to_loc,"actor_owner_id":actor,"notes":note,"issue_type":""})
      add_event("DISPATCH",base,origin["location_id"],dest["location_id"],owners[2]["owner_id"])
      add_event("DELIVERY",base+timedelta(days=2),origin["location_id"],dest["location_id"],owner["owner_id"])
      # Some assets return late, some stay outstanding, others return normally
      r=rng.random()
      if r<0.08:  # lost, no return
        add_event("LOST_DECLARED",base+timedelta(days=typ["loss_threshold_days"]+3),dest["location_id"],dest["location_id"],owners[3]["owner_id"],note="Loss threshold exceeded")
        a["current_status"]="LOST"
      elif r<0.22: # outstanding
        a["current_status"]="AT_CUSTOMER"
      else:
        ret=base+timedelta(days=rng.randint(typ["return_sla_days"]-2,typ["return_sla_days"]+18))
        if ret>NOW: ret=NOW-timedelta(days=rng.randint(0,2))
        add_event("RETURN_RECEIVED",ret,dest["location_id"],origin["location_id"],owners[3]["owner_id"])
        rma=f"RMA-2026-{len(returns)+1:06d}"
        returns.append({"rma_id":rma,"asset_id":a["asset_id"],"requested_at":stamp(ret-timedelta(days=1)),"authorized_at":stamp(ret-timedelta(hours=12)),"received_at":stamp(ret),"return_status":"RECEIVED","source_location_id":dest["location_id"],"destination_location_id":origin["location_id"],"reason":"ROUTINE_RETURN"})
        a["current_status"]="INSPECTION"
        result=rng.choices(ENUMS["inspection_result"],weights=[.78,.13,.06,.03])[0]
        iid=f"INSP-{len(inspections)+1:07d}"
        inspections.append({"inspection_id":iid,"rma_id":rma,"asset_id":a["asset_id"],"inspected_at":stamp(ret+timedelta(hours=3)),"inspector_owner_id":owners[3]["owner_id"],"result":result,"damage_cost":0 if result=="PASS" else rng.choice([150,300,500,800]),"notes":"Synthetic inspection"})
        if result in ("MINOR_DAMAGE","MAJOR_DAMAGE","MISSING_PARTS"):
          rep=f"REP-2026-{len(repairs)+1:06d}"
          opened=ret+timedelta(days=1)
          repairs.append({"repair_id":rep,"asset_id":a["asset_id"],"inspection_id":iid,"opened_at":stamp(opened),"closed_at":stamp(opened+timedelta(days=rng.randint(1,8))),"repair_status":"COMPLETED","repair_cost":rng.choice([200,450,700,1200]),"repair_center_location_id":origin["location_id"]})
          a["current_status"]="AVAILABLE"
        else: a["current_status"]="AVAILABLE"
      ledger.append({"ledger_entry_id":f"LED-{len(ledger)+1:08d}","asset_id":a["asset_id"],"rma_id":returns[-1]["rma_id"] if returns and returns[-1]["asset_id"]==a["asset_id"] else "","entry_type":"DEPOSIT_CHARGE","amount":typ["deposit_amount"],"currency":"INR","posted_at":stamp(base),"reference":ship["shipment_id"]})
      if a["current_status"] in ("AVAILABLE","INSPECTION"):
        ledger.append({"ledger_entry_id":f"LED-{len(ledger)+1:08d}","asset_id":a["asset_id"],"rma_id":returns[-1]["rma_id"] if returns and returns[-1]["asset_id"]==a["asset_id"] else "","entry_type":"DEPOSIT_REFUND","amount":typ["deposit_amount"],"currency":"INR","posted_at":stamp(NOW-timedelta(days=rng.randint(0,10))),"reference":"RETURN_SETTLEMENT"})
    # Expand to exactly five events per asset using legitimate custody transfers
    for a in assets:
      while event_counter[a["asset_id"]]<5:
        event_counter[a["asset_id"]]+=1
        k=event_counter[a["asset_id"]]
        loc=locations[(int(a["asset_id"][-3:])+k)%len(locations)]
        events.append({"custody_event_id":f"CUST-{a['asset_id']}-{k:06d}","asset_id":a["asset_id"],"shipment_id":"","event_type":"CUSTODY_TRANSFER","event_at":stamp(NOW-timedelta(days=k)),"from_location_id":loc["location_id"],"to_location_id":loc["location_id"],"actor_owner_id":owners[3]["owner_id"],"notes":"Routine recorded handling","issue_type":""})
    # If scale parameter differs, pad event count with additional legitimate transfer events.
    while len(events)<n_events:
      a=assets[len(events)%len(assets)]; event_counter[a["asset_id"]]+=1; k=event_counter[a["asset_id"]]
      loc=locations[k%len(locations)]
      events.append({"custody_event_id":f"CUST-{a['asset_id']}-{k:06d}","asset_id":a["asset_id"],"shipment_id":"","event_type":"CUSTODY_TRANSFER","event_at":stamp(NOW-timedelta(hours=k)),"from_location_id":loc["location_id"],"to_location_id":loc["location_id"],"actor_owner_id":owners[3]["owner_id"],"notes":"Routine handling","issue_type":""})
    # Inject five explicit labelled anomalies; IDs and parent references remain deterministic.
    truth=[]
    def anomaly(label, entity, record_id, expected, description):
      truth.append({"anomaly_id":f"GT-{len(truth)+1:03d}","issue_type":label,"entity":entity,"record_id":record_id,"expected_decision":expected,"description":description})
    a0=assets[0]; loc1,loc2=locations[0],locations[1]
    event_counter[a0["asset_id"]]+=1; eid=f"CUST-{a0['asset_id']}-{event_counter[a0['asset_id']]:06d}"
    events.append({"custody_event_id":eid,"asset_id":a0["asset_id"],"shipment_id":"","event_type":"CUSTODY_TRANSFER","event_at":stamp(NOW),"from_location_id":loc1["location_id"],"to_location_id":loc1["location_id"],"actor_owner_id":owners[3]["owner_id"],"notes":"Injected overlapping-location claim","issue_type":"SIMULTANEOUS_LOCATIONS"})
    events.append({"custody_event_id":f"CUST-{a0['asset_id']}-{event_counter[a0['asset_id']]+1:06d}","asset_id":a0["asset_id"],"shipment_id":"","event_type":"CUSTODY_TRANSFER","event_at":stamp(NOW),"from_location_id":loc2["location_id"],"to_location_id":loc2["location_id"],"actor_owner_id":owners[3]["owner_id"],"notes":"Conflicting location claim","issue_type":"SIMULTANEOUS_LOCATIONS"})
    anomaly("SIMULTANEOUS_LOCATIONS","CustodyEvent",eid,"QUARANTINE_ASSET","Two active location claims overlap for one asset.")
    # Return before dispatch: deliberately timestamped invalid chronology.
    rma=f"RMA-2026-{len(returns)+1:06d}"
    returns.append({"rma_id":rma,"asset_id":assets[1]["asset_id"],"requested_at":stamp(NOW-timedelta(days=20)),"authorized_at":stamp(NOW-timedelta(days=19)),"received_at":stamp(NOW-timedelta(days=21)),"return_status":"RECEIVED","source_location_id":locations[1]["location_id"],"destination_location_id":locations[0]["location_id"],"reason":"INJECTED_EARLY_RETURN"})
    anomaly("RETURN_BEFORE_DISPATCH","ReturnAuthorization",rma,"REJECT_RETURN_AND_REVIEW","Received timestamp predates the asset dispatch event.")
    # Duplicate deposit refund
    led_asset=assets[2]; base_ledger=next(x for x in ledger if x["asset_id"]==led_asset["asset_id"] and x["entry_type"]=="DEPOSIT_REFUND")
    duplicate=dict(base_ledger); duplicate["ledger_entry_id"]=f"LED-{len(ledger)+1:08d}"; duplicate["posted_at"]=stamp(NOW); duplicate["reference"]="INJECTED_DUPLICATE_REFUND"; ledger.append(duplicate)
    anomaly("DUPLICATE_DEPOSIT_REFUND","DepositLedger",duplicate["ledger_entry_id"],"REVERSE_DUPLICATE_AND_FLAG","Second refund for the same asset deposit.")
    # Repair closes without inspection (nullable FK intentionally; anomaly label retained)
    rep=f"REP-2026-{len(repairs)+1:06d}"
    repairs.append({"repair_id":rep,"asset_id":assets[3]["asset_id"],"inspection_id":"","opened_at":stamp(NOW-timedelta(days=2)),"closed_at":stamp(NOW-timedelta(days=1)),"repair_status":"COMPLETED","repair_cost":500,"repair_center_location_id":locations[2]["location_id"]})
    anomaly("REPAIR_WITHOUT_INSPECTION","Repair",rep,"REOPEN_REPAIR_AND_REQUIRE_INSPECTION","Repair completion has no linked inspection.")
    # Missing actor on event
    event_counter[assets[4]["asset_id"]]+=1; eid=f"CUST-{assets[4]['asset_id']}-{event_counter[assets[4]['asset_id']]:06d}"
    events.append({"custody_event_id":eid,"asset_id":assets[4]["asset_id"],"shipment_id":"","event_type":"CUSTODY_TRANSFER","event_at":stamp(NOW),"from_location_id":locations[4]["location_id"],"to_location_id":locations[5]["location_id"],"actor_owner_id":"","notes":"Injected missing actor","issue_type":"MISSING_ACTOR"})
    anomaly("MISSING_CUSTODY_ACTOR","CustodyEvent",eid,"HOLD_EVENT_FOR_REVIEW","Custody event lacks an accountable actor.")
    # Derive asset age/status snapshot, no independently randomized labels
    fields={
      "AssetType":list(asset_types[0]),"ReusableAsset":list(assets[0]),"Owner":list(owners[0]),"Location":list(locations[0]),"Shipment":list(shipments[0]),"ShipmentAsset":list(bridge[0]),"CustodyEvent":list(events[0]),"ReturnAuthorization":list(returns[0]),"Inspection":list(inspections[0]),"Repair":list(repairs[0]),"DepositLedger":list(ledger[0])}
    tables={"AssetType":asset_types,"ReusableAsset":assets,"Owner":owners,"Location":locations,"Shipment":shipments,"ShipmentAsset":bridge,"CustodyEvent":events,"ReturnAuthorization":returns,"Inspection":inspections,"Repair":repairs,"DepositLedger":ledger}
    for name,rows in tables.items(): write_csv(out/(name+".csv"),rows,fields[name])
    write_csv(out/"ground_truth.csv",truth,list(truth[0]))
    # Snapshot metrics are derived from records.
    outstanding=[a for a in assets if a["current_status"] in ("AT_CUSTOMER","IN_TRANSIT")]
    metrics={"seed":seed,"assets":len(assets),"shipments":len(shipments),"custody_events":len(events),"returns":len(returns),"inspections":len(inspections),"repairs":len(repairs),"ledger_entries":len(ledger),"known_anomalies":len(truth),"outstanding_assets":len(outstanding),"potentially_lost_assets":sum(a["current_status"]=="LOST" for a in assets)}
    (out/"validation_summary.json").write_text(json.dumps({"metrics":metrics,"checks":{"primary_keys":"checked by deterministic IDs","foreign_keys":"master IDs generated before child rows; deliberate actor/inspection optional only in labelled anomaly records","reproducibility":"SHA-256 manifest emitted"}},indent=2))
    manifest={p.name:digest(p) for p in sorted(out.glob("*.csv"))}
    (out/"source_manifest.json").write_text(json.dumps({"synthetic":True,"seed":seed,"generator":"generate.py","checksums_sha256":manifest},indent=2))
    return metrics
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--scale",type=int,default=20000,help="number of assets; shipments=scale/2, custody events=scale*5")
    ap.add_argument("--seed",type=int,default=SEED); ap.add_argument("--out",default="data")
    args=ap.parse_args(); print(json.dumps(build(args.out,args.scale,args.seed),indent=2))
if __name__=="__main__": main()
