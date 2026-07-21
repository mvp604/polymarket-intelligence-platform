import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "database" / "polymarket.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
SELECT
    restricted,
    COUNT(*) AS total
FROM gamma_markets
GROUP BY restricted
ORDER BY total DESC
""").fetchall()

print("\nRestricted values in gamma_markets\n")

for row in rows:
    print(repr(row["restricted"]), row["total"])

print("\nSample rows\n")

rows = conn.execute("""
SELECT
    gamma_market_id,
    question,
    restricted
FROM gamma_markets
LIMIT 20
""").fetchall()

for row in rows:
    print(
        row["gamma_market_id"],
        "|",
        row["restricted"],
        "|",
        row["question"]
    )

conn.close()