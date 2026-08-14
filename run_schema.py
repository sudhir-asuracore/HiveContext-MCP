import os
import psycopg2

db_url = os.environ.get("DATABASE_URL").replace("/defaultdb", "/hive_oss_defaultdb")

conn = psycopg2.connect(db_url)
conn.autocommit = True

with open("schema.sql", "r") as f:
    schema = f.read()

with conn.cursor() as cur:
    cur.execute(schema)

print("Schema created successfully.")
