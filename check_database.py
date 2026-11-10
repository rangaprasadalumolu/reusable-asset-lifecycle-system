
import sqlite3

connection = sqlite3.connect("assets.db")

print("========== DATABASE TABLES ==========")

tables = connection.execute("""
    SELECT name, sql
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
""").fetchall()

for table_name, table_sql in tables:
    print("\nTABLE:", table_name)
    print(table_sql)

print("\n========== OWNERS ==========")

owners = connection.execute("""
    SELECT owner_id, owner_name, owner_type
    FROM Owner
    LIMIT 10
""").fetchall()

for owner in owners:
    print(owner)

print("\n========== LOCATIONS ==========")

locations = connection.execute("""
    SELECT location_id, location_name
    FROM Location
    LIMIT 10
""").fetchall()

for location in locations:
    print(location)

connection.close()

print("\nDatabase verification completed.")
