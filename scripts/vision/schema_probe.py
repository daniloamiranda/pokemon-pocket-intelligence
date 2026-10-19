import sqlite3
from pathlib import Path

db = sqlite3.connect(str(Path(__file__).resolve().parents[2] / 'data' / 'pocket.sqlite'))
for (sql,) in db.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(sql)
    print('---')
