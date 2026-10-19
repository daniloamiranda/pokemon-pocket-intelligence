"""Loader: grava cartas coletadas do Limitless no SQLite canonico (dev via /opt/data).

COPIADO para o repo via cp depois de lintar aqui. Editar esta copia e re-copiar.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

SOURCE_ID = "pocket.limitlesstcg.com"
SOURCE_NAME = "Limitless TCG Pocket Database"
SOURCE_URL = "https://pocket.limitlesstcg.com"

SET_NAMES_FALLBACK = {
    "A1": "Genetic Apex", "A1a": "Mythical Island",
    "A2": "Space-Time Smackdown", "A2a": "Triumphant Light",
    "A2b": "Shining Revelry", "A3": "Celestial Guardians",
    "A3a": "Extradimensional Crisis", "A3b": "Eevee Grove",
    "A4": "Wisdom of Sea and Sky", "A4a": "Tidal Storm",
    "A4b": "Smeltzone", "B1": "Secluded Springs",
    "B1a": "Crimson Blaze", "B2": "Fantastical Parade",
    "B2a": "Pickpocket Scheme", "B2b": "Mega Shine",
    "B3": "Rumble of the Fallen", "B3a": "Black Moon Rising",
    "B3b": "Angels and Demons", "B4": "Ruler of Skies",
    "B4a": "Revelation Rays", "B4b": "Deluxe Pack: Mega",
    "P-A": "Promo Pack A", "P-B": "Promo Pack B",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_source(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS card_evolution_slugs ("
        "card_id TEXT PRIMARY KEY, slug TEXT NOT NULL)")
    conn.execute(
        "INSERT OR IGNORE INTO sources(id, name, base_url, kind, tier, policy, requires_key, notes)"
        " VALUES (?,?,?,?,?,?,0,?)",
        (SOURCE_ID, SOURCE_NAME, SOURCE_URL, "scrape", "canonical",
         "HTML server-side; rate limit 1.2s; UA identificado; sem redistribuicao de imagens",
         "Fonte primaria de cartas (Fase 1, nivel A). Politica: link/referencia apenas."))
    conn.commit()


def compute_mechanical_hash(card: dict) -> str:
    payload = {
        "n": card.get("name"),
        "cat": card.get("category"),
        "el": card.get("element"),
        "st": card.get("stage"),
        "hp": card.get("hp"),
        "wk": card.get("weakness_element"),
        "rt": card.get("retreat_cost"),
        "sr": card.get("special_rule"),
        "ex": card.get("is_ex"),
        "at": card.get("attacks"),
        "ab": card.get("abilities"),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def upsert_expansion(conn: sqlite3.Connection, meta: dict, code: str) -> bool:
    """Insere expansao se inexistente. Idempotente."""
    cur = conn.execute("SELECT 1 FROM expansions WHERE code=?", (code,))
    if cur.fetchone() is not None:
        return False
    conn.execute(
        "INSERT INTO expansions(id, code, name, release_date, card_count, source_id, verified_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (code, code,
         meta.get("name") or SET_NAMES_FALLBACK.get(code, code),
         meta.get("release_date") or "1970-01-01",
         meta.get("card_count") or 0,
         SOURCE_ID, now_iso()))
    conn.commit()
    return True


def load_card(conn: sqlite3.Connection, card: dict) -> tuple[str, str]:
    """Upsert de 1 ficha mecanica + impressoes. Retorna (card_id, acao)."""
    mhash = compute_mechanical_hash(card)
    card_id = f"limitless:{card['set']}/{card['number']}"
    # F4c: lookup de ficha PRIMEIRO por id estavel do print (set/number) e DEPOIS
    # por hash. Antes: somente hash — mesma carta com dano corrigido virava
    # "nova" (novo hash) e o INSERT OR IGNORE falhava silencioso (id ja existe),
    # deixando row None quando o hash tambem tinha mudado de outro card...
    row = conn.execute("SELECT id FROM cards WHERE id=?", (card_id,)).fetchone()
    is_new = row is None
    if row is None:
        row = conn.execute("SELECT id FROM cards WHERE mechanical_hash=? AND source_id=?",
                           (mhash, SOURCE_ID)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO cards(id, canonical_name, category, element, stage,"
            " hp, weakness_element, retreat_cost, special_rule, mechanical_hash, is_ex,"
            " source_id, verified_at, validation_status)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'pending')"
            " ON CONFLICT(id) DO UPDATE SET"
            " canonical_name=excluded.canonical_name, category=excluded.category,"
            " element=excluded.element, stage=excluded.stage, hp=excluded.hp,"
            " weakness_element=excluded.weakness_element,"
            " retreat_cost=excluded.retreat_cost, special_rule=excluded.special_rule,"
            " mechanical_hash=excluded.mechanical_hash, is_ex=excluded.is_ex",
            (card_id, card["name"], card["category"], card.get("element"),
             card.get("stage"), card.get("hp"), card.get("weakness_element"),
             card.get("retreat_cost"), card.get("special_rule"), mhash, card.get("is_ex", 0),
             SOURCE_ID, now_iso()))
        row = (card_id,)
    card_pk = row[0]

    # slug da pre-evolucao guardado em tabela auxiliar (FK de cards.evolves_from_id
    # referencia cards(id); slug sera resolvido no fim da carga por link_evolutions)
    if card.get("evolves_from"):
        conn.execute("INSERT OR IGNORE INTO card_evolution_slugs(card_id, slug)"
                     " VALUES (?,?)", (card_pk, card["evolves_from"]))
    # F4c: escritas de filhos IDEMPOTENTES — UNIQUE(card_id, name) + upsert.
    # (antes: INSERT OR IGNORE sem UNIQUE = cada reprocesso re-inseria a linha)
    for i, atk in enumerate(card.get("attacks") or []):
        conn.execute(
            "INSERT INTO card_attacks(card_id, name, energy_cost, damage,"
            " effect_text, sort_order) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(card_id, name) DO UPDATE SET"
            " energy_cost=excluded.energy_cost, damage=excluded.damage,"
            " effect_text=excluded.effect_text, sort_order=excluded.sort_order",
            (card_pk, atk["name"], json.dumps(atk["energy_cost"]), atk.get("damage"),
             atk.get("effect_text"), i))
    for ab in card.get("abilities") or []:
        conn.execute(
            "INSERT INTO card_abilities(card_id, name, kind, effect_text)"
            " VALUES (?,?,?,?) ON CONFLICT(card_id, name) DO UPDATE SET"
            " kind=excluded.kind, effect_text=excluded.effect_text",
            (card_pk, ab["name"], ab.get("kind", "ability"), ab["effect_text"]))
    conn.execute("INSERT OR IGNORE INTO card_localizations(card_id, lang, name)"
                 " VALUES (?,'en',?)", (card_pk, card["name"]))

    # impressoes: ficha atual + tabela de versoes (rarity da ficha atual atualizada abaixo)
    prints = list(card.get("versions") or [])
    if not prints or not any(p_["number"] == card["number"] and p_["set"] == card["set"]
                             for p_ in prints):
        prints.append({"set": card["set"], "number": card["number"],
                       "rarity": card.get("print_rarity"),
                       "image_url": card.get("image_url")})
    for pr in prints:
        pset, pnum = pr["set"], pr["number"]
        print_id = f"{pset}#{pnum}"
        # imagem: a da FICHA atual pinta a impressao correspondente ao (set, num)
        # da ficha; prints de outras versoes vem sem imagem (o coletor resolve
        # pela listagem/URL deterministica)
        own_print = (pset == card["set"] and pnum == card["number"])
        conn.execute(
            "INSERT OR IGNORE INTO card_prints(id, card_id, set_code, number, rarity,"
            " artist, image_url, source_id) VALUES (?,?,?,?,?,?,?,?)",
            (print_id, card_pk, pset, pnum, pr.get("rarity"), card.get("artist"),
             card.get("image_url") if own_print else None, SOURCE_ID))
        # reflete a arte da ficha na impressao correspondente (reexecuta ficha após
        # outra ficha já ter criado o print sem imagem)
        if own_print and card.get("image_url"):
            conn.execute("UPDATE card_prints SET image_url=? WHERE id=?"
                         " AND image_url IS NULL", (card["image_url"], print_id))
    conn.commit()
    return card_pk, ("insert" if is_new else "existing")


def link_evolutions(conn: sqlite3.Connection) -> int:
    """Resolve evolves_from (slug de nome na URL) para card_id e grava card_evolutions."""
    conn.execute("CREATE TABLE IF NOT EXISTS card_evolution_slugs ("
                 "card_id TEXT PRIMARY KEY, slug TEXT NOT NULL)")
    slugs = conn.execute("SELECT card_id, slug FROM card_evolution_slugs").fetchall()
    resolved = 0
    for card_id, slug in slugs:
        target = conn.execute(
            "SELECT id FROM cards WHERE LOWER(REPLACE(canonical_name,' ','_')) LIKE ?"
            " AND category='pokemon' ORDER BY id LIMIT 1",
            (slug + "%",)).fetchone()
        if not target:
            continue
        stage = conn.execute("SELECT stage FROM cards WHERE id=?", (card_id,)).fetchone()
        conn.execute(
            "INSERT OR IGNORE INTO card_evolutions(card_id, pre_evo_card_id, stage)"
            " VALUES (?,?,?)", (card_id, target[0], stage[0] if stage else 'stage1'))
        resolved += 1
    conn.commit()
    return resolved
