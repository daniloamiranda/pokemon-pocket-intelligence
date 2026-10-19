#!/usr/bin/env python3
"""F15+ BUG-001 · guarda anti-regressao da geracao de deck_id (card t_fd4343fb, R2).

Classe do defeito: persist() derivava o proximo deck_id de COUNT(*)+1 sobre o
slug. Contagem nao e sequencia: a revalidacao F8b removeu 001/004 da serie
deck-mega-gengar-ex-% (restaram 002/003) e o COUNT=2 recalculava o id 003 JA
existente -> sqlite3.IntegrityError: UNIQUE constraint failed: decks.id
(repro deterministica 2/2 da QA em t_3539dc38 + reproducao independente do
CEO em 19/10, producao intocada).

Criterio do Proprietario (card t_fd4343fb): o proximo id NAO pode depender de
contagem. Fix aplicado: MAX(CAST(substr(id,-3) AS INTEGER))+1 por slug e
guarda de colisao residual (incrementa sufixo em vez de crashar).

Regressao obrigatoria coberta AQUI em banco EFEMERO (schema DDL identico ao
de producao — data/pocket.sqlite NUNCA e escrito; a suite nao exige catalogo):
  (a)  build -> apagar registro ABAIXO do max (buraco real) -> build de novo
       => rc=0 e id novo DISTINTO (o codigo antigo crashava com IntegrityError);
  (a2) serie totalmente apagada -> rebuild rc=0 sem colisao (tail liberado e
       reutilizado por semantica MAX — nenhuma colisao possivel; a classe
       IntegrityError fica extinta);
  (b)  dois builds seguidos => ids distintos, sem colisao;
  (c)  estado EXATO de producao com buraco (002/003 presentes) => build do
       Mega Gengar ex rc=0 -> 004, irmaos intocados, deck_cards sem duplicacao.
A legalidade 20/20 do cenario 17 (E2E contra COPIA do banco real, linha
Gastly B2b/37 -> Haunter B2b/38 -> Mega Gengar ex B2b/39) fica na prova de
aceite do card — fora da suite (a suite nunca escreve nem copia producao).
"""
from __future__ import annotations

import re
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "deck"))

import build_deck as B  # noqa: E402

# DDL EXTRAIDO DO PRODUCAO (probe read-only 19/10/2026, migration 0004) —
# identico, inclusive CHECKs e FKs, para o fixture nao mentir.
DDL = [
    """CREATE TABLE decks (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    format       TEXT NOT NULL,
    total_cards  INTEGER NOT NULL CHECK (total_cards = 20),
    archetype_id TEXT REFERENCES meta_archetypes(id),
    source_id    TEXT NOT NULL REFERENCES sources(id),
    collected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
)""",
    """CREATE TABLE deck_cards (
    deck_id  TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id  TEXT NOT NULL REFERENCES cards(id),
    print_id TEXT REFERENCES card_prints(id),
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 2),
    PRIMARY KEY (deck_id, card_id, print_id)
)""",
    """CREATE TABLE deck_specifications (
    deck_id      TEXT PRIMARY KEY REFERENCES decks(id) ON DELETE CASCADE,
    spec_json    TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
)""",
]

SOURCE_ID = "play.limitlesstcg.com"  # CORPUS_SOURCE_ID real do builder
SLUG = "mega-gengar-ex"
PICKS = [{"card_id": "limitless:B2b/37", "quantity": 2},   # Gastly
         {"card_id": "limitless:B2b/38", "quantity": 2},   # Haunter
         {"card_id": "limitless:B2b/39", "quantity": 2},   # Mega Gengar ex
         {"card_id": "limitless:A4b/373", "quantity": 1}]  # draw


def _seed_deck(con, deck_id, cards=10):
    """Semeia um deck-irmao com deck_cards, imitando o estado de producao."""
    con.execute("INSERT INTO decks (id, name, format, total_cards, source_id) "
                "VALUES (?,?,?,?,?)", (deck_id, f"{deck_id} — build F8",
                                       "standard", 20, SOURCE_ID))
    for i in range(cards):
        con.execute("INSERT INTO deck_cards (deck_id, card_id, print_id, quantity) "
                    "VALUES (?,?,'NULL-print',?)",
                    (deck_id, f"limitless:seed/{i:03d}", 2 if i % 2 else 1))
    con.execute("INSERT INTO deck_specifications (deck_id, spec_json) VALUES (?,?)",
                (deck_id, f'{{"seeded": "{deck_id}"}}'))
    con.commit()


class TestF15PlusDeckIdGuard(unittest.TestCase):
    """A classe 'slug com buraco nao gera colisao' fica vigiada aqui."""

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        for stmt in DDL:
            self.con.execute(stmt)
        # sources() e meta_archetypes() nao existem no fixture (FKs ficam
        # sem enforcement, como na conexao real do builder — sqlite3 sem PRAGMA).

    def tearDown(self):
        self.con.close()

    def _persist(self):
        spec = {"main_card": {"canonical_name": "Mega Gengar ex"},
                "name": "Mega Gengar ex — build F8", "format": "standard"}
        return B.persist(self.con, spec, PICKS)

    # -- (c) estado EXATO de producao: buraco 001/004 ausentes, 002/003 presentes
    def test_01_buraco_real_producao_gera_004_sem_colisao(self):
        _seed_deck(self.con, "deck-mega-gengar-ex-002")
        _seed_deck(self.con, "deck-mega-gengar-ex-003")
        deck_id = self._persist()  # codigo antigo: IntegrityError AQUI
        self.assertEqual(f"deck-{SLUG}-004", deck_id)
        ids = [r[0] for r in self.con.execute(
            "SELECT id FROM decks WHERE id LIKE ? ORDER BY id", (f"deck-{SLUG}-%",))]
        self.assertEqual([f"deck-{SLUG}-002", f"deck-{SLUG}-003",
                          f"deck-{SLUG}-004"], ids)

    # -- (a) build -> apagar registro abaixo do max -> build de novo: id DISTINTO
    def test_02_rebuild_apos_apagar_abaixo_do_max_id_distinto(self):
        first = self._persist()               # 001
        second = self._persist()              # 002
        self.assertNotEqual(first, second)
        # apaga o PRIMEIRO (buraco abaixo do max — a ordem das operacoes
        # nao esconde o defeito; COUNT=1 recomputaria o 002 existente)
        self.con.execute("DELETE FROM deck_cards WHERE deck_id=?", (first,))
        self.con.execute("DELETE FROM deck_specifications WHERE deck_id=?", (first,))
        self.con.execute("DELETE FROM decks WHERE id=?", (first,))
        self.con.commit()
        third = self._persist()               # codigo antigo: IntegrityError
        self.assertNotIn(third, {first, second})
        self.assertEqual(f"deck-{SLUG}-003", third)

    # -- (a2) serie TOTALMENTE apagada: rebuild rc=0, sem colisao possivel
    def test_03_serie_vazia_rebuild_rc0_sem_colisao(self):
        first = self._persist()
        for table in ("deck_cards", "deck_specifications", "decks"):
            self.con.execute(f"DELETE FROM {table}")
        self.con.commit()
        rebuilt = self._persist()             # nem codigo velho nem novo crasham
        self.assertEqual(first, rebuilt)      # tail liberado reutilizado (MAX)

    # -- (b) dois builds seguidos: ids distintos, sem colisao
    def test_04_dois_builds_seguidos_ids_distintos(self):
        seen = [self._persist() for _ in range(3)]
        self.assertEqual(3, len(set(seen)))
        self.assertEqual([f"deck-{SLUG}-{n:03d}" for n in (1, 2, 3)], seen)

    # -- Nick item 3: deck_cards nao duplica e irmaos ficam intocados
    def test_05_deck_cards_sem_duplicacao_e_irmaos_intactos(self):
        _seed_deck(self.con, "deck-mega-gengar-ex-002")
        _seed_deck(self.con, "deck-mega-gengar-ex-003")
        before = dict(self.con.execute(
            "SELECT deck_id, COUNT(*) FROM deck_cards WHERE deck_id LIKE ? "
            "GROUP BY deck_id", (f"deck-{SLUG}-%",)).fetchall())
        deck_id = self._persist()
        rows = self.con.execute(
            "SELECT card_id, COUNT(*) FROM deck_cards WHERE deck_id=? "
            "GROUP BY card_id", (deck_id,)).fetchall()
        self.assertEqual(len(PICKS), len(rows))          # 1 linha por carta
        self.assertEqual(len(PICKS), self.con.execute(
            "SELECT COUNT(*) FROM deck_cards WHERE deck_id=?",
            (deck_id,)).fetchone()[0])                   # zero duplicacao
        after = dict(self.con.execute(
            "SELECT deck_id, COUNT(*) FROM deck_cards WHERE deck_id LIKE ? "
            "GROUP BY deck_id", (f"deck-{SLUG}-%",)).fetchall())
        after.pop(deck_id)
        self.assertEqual(before, after)                  # irmaos intocados

    # -- guarda de fonte: o antipattern COUNT-como-sequencia nao volta
    def test_06_fonte_sem_antipattern_count(self):
        src = (ROOT / "scripts" / "deck" / "build_deck.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"COUNT\(\*\)\s+FROM\s+decks", src),
                          "antipattern BUG-001 de volta em build_deck.py")
        self.assertIn("MAX(CAST(substr(id, -3) AS INTEGER))", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
