import sqlite3
db = sqlite3.connect('/workspace/ARCOS/projetos/pokemon-pocket-intelligence/data/pocket.sqlite')
for (sql,) in db.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(sql)
    print('---')
