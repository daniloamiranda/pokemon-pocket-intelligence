#!/usr/bin/env python3
"""Auditoria de duplicacao nas tabelas-filhas do catalogo (tarefa F4c)."""
import json, sqlite3, sys

DB = sys.argv[1] if len(sys.argv) > 1 else "data/pocket.sqlite"
conn = sqlite3.connect(DB)

print("== migracoes ==")
for r in conn.execute("SELECT version, name FROM schema_migrations ORDER BY version"):
    print(r)

print("\n== contagens brutas vs distintas ==")
tables = {
    "card_attacks": "card_id,name",
    "card_abilities": "card_id,name",
    "card_evolutions": "card_id,pre_evo_card_id",
    "card_prints": "id",
    "card_localizations": "card_id,lang",
    "card_legality": "card_id,format,from_date",
}
for t, cols in tables.items():
    total = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    dist = conn.execute(f"SELECT count(*) FROM (SELECT DISTINCT {cols} FROM {t})").fetchone()[0]
    f = total / dist if dist else 0
    print(f"{t:20s} total={total:6d} distinta({cols})={dist:6d} fator={f:.2f}")

print("\n== distintas por linha completa ==")
print("attacks full:", conn.execute(
    "SELECT count(*) FROM (SELECT DISTINCT card_id,name,energy_cost,damage,effect_text,sort_order FROM card_attacks)"
).fetchone()[0])
print("abilities full:", conn.execute(
    "SELECT count(*) FROM (SELECT DISTINCT card_id,name,kind,effect_text FROM card_abilities)"
).fetchone()[0])

print("\n== Mewtwo ex A1/129 ==")
rows = conn.execute(
    "SELECT ca.card_id, ca.name, ca.energy_cost, ca.damage FROM card_attacks ca "
    "WHERE ca.card_id IN (SELECT card_id FROM card_prints WHERE set_code='A1' AND number='129')"
).fetchall()
print("linhas de ataque:", len(rows), "-> nomes:", sorted({r[1] for r in rows}))
print(json.dumps(sorted({(r[1], r[3]) for r in rows}), ensure_ascii=False))

print("\n== cartas com >3 ataques distintos ==")
for r in conn.execute(
    "SELECT card_id, count(DISTINCT name) n FROM card_attacks GROUP BY card_id HAVING n>3 ORDER BY n DESC LIMIT 10"
):
    print(r)
print("total >3:", conn.execute(
    "SELECT count(*) FROM (SELECT card_id FROM card_attacks GROUP BY card_id HAVING count(DISTINCT name)>3)"
).fetchone()[0])

print("\n== duplicatas divergentes por (card_id,name)? ==")
q = ("SELECT count(*) FROM (SELECT card_id,name FROM card_attacks GROUP BY card_id,name "
     "HAVING count(DISTINCT energy_cost||'|'||COALESCE(damage,-1)||'|'||COALESCE(effect_text,''))>1)")
print("attacks divergentes:", conn.execute(q).fetchone()[0])
q2 = ("SELECT count(*) FROM (SELECT card_id,name FROM card_abilities GROUP BY card_id,name "
      "HAVING count(DISTINCT kind||'|'||COALESCE(effect_text,''))>1)")
print("abilities divergentes:", conn.execute(q2).fetchone()[0])

print("\n== schema das filhas ==")
for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE name IN ('card_attacks','card_abilities')"):
    print(r[0], "->", r[1])
for r in conn.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('card_attacks','card_abilities')"):
    print(r)

print("\n== integrity_check ==")
print(conn.execute("PRAGMA integrity_check").fetchone()[0])
