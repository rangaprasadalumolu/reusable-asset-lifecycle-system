
import sqlite3

connection = sqlite3.connect("assets.db")

tables = connection.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""").fetchall()

print("========== DATABASE INDEX AUDIT ==========")

for (table_name,) in tables:
    print(f"\nTABLE: {table_name}")

    indexes = connection.execute(
        f'PRAGMA index_list("{table_name}")'
    ).fetchall()

    if not indexes:
        print("No indexes found")
    else:
        for index in indexes:
            print(index)

            index_name = index[1]
            columns = connection.execute(
                f'PRAGMA index_info("{index_name}")'
            ).fetchall()

            print("  Columns:", columns)

connection.close()
