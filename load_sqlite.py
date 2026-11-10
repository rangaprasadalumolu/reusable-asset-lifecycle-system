import csv, sqlite3, sys
from pathlib import Path
db=sqlite3.connect(sys.argv[2] if len(sys.argv)>2 else "assets.db")
db.executescript(Path("schema.sql").read_text())
base=Path(sys.argv[1] if len(sys.argv)>1 else "data/starter")
order=["Owner","Location","AssetType","ReusableAsset","Shipment","ShipmentAsset","CustodyEvent","ReturnAuthorization","Inspection","Repair","DepositLedger"]
for table in order:
    with open(base/(table+".csv"),newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    if not rows: continue
    cols=list(rows[0])
    sql=f'INSERT INTO "{table}" ({",".join(chr(34)+c+chr(34) for c in cols)}) VALUES ({",".join("?" for _ in cols)})'
    vals=[[r[c] if r[c]!="" else None for c in cols] for r in rows]
    try: db.executemany(sql,vals)
    except sqlite3.IntegrityError as e:
        # Explicitly labelled missing-actor anomaly and repair-without-inspection are valid exception records;
        # FK enforcement permits NULL, so all parent links remain checked.
        raise RuntimeError(f"Load failed for {table}: {e}")
db.commit()
print("Loaded",sum(db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in order),"rows")
