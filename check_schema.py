
import sqlite3
import tempfile
from pathlib import Path

schema_path = Path("schema.sql")

with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp:
    temp_path = Path(temp.name)
connection = None

try:
    connection = sqlite3.connect(temp_path)

    connection.executescript(
        schema_path.read_text(encoding="utf-8")
    )

    indexes = connection.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'index'
          AND name LIKE 'idx_%'
        ORDER BY name
    """).fetchall()

    print("========== FRESH SCHEMA VERIFICATION ==========")
    print("Custom indexes found:", len(indexes))

    for (name,) in indexes:
        print(name)

    print(
        "Database integrity:",
        connection.execute("PRAGMA integrity_check").fetchone()[0]
    )


finally:
    if connection is not None:
        connection.close()

    temp_path.unlink(missing_ok=True)
