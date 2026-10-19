"""F7 - testes unitarios do pipeline de meta (dados SINTETICOS, banco tmp).

Nenhum teste toca o banco de producao em modo escrita: o snapshot e construido
em tmpdir com as migracoes do repositorio (mesmo runner da producao). Raw
sintetico imita o formato da Limitless Developer API (provas reais no cartao).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "meta"))
sys.path.insert(0, str(ROOT))

import meta_pipeline as M  # noqa: E402


def make_print_index(tmpdir):
    """Catalogo minimo NO banco tmp (FKs reais): 10 prints x2 = lista de 20."""
    con = M.sqlite3.connect(str(Path(tmpdir) / "meta_test.sqlite"))
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("INSERT OR IGNORE INTO sources (id,name,kind,tier) "
                "VALUES ('play.limitlesstcg.com','Limitless','api','canonical')")
    con.execute("INSERT OR IGNORE INTO expansions (id,code,name,release_date,card_count,source_id) "
                "VALUES ('e1','B1','Set B1','2026-01-30',200,'play.limitlesstcg.com')")
    con.execute("INSERT OR IGNORE INTO expansions (id,code,name,release_date,card_count,source_id) "
                "VALUES ('e2','A1','Set A1','2025-10-30',200,'play.limitlesstcg.com')")
    rows = []
    for i in range(4):
        rows.append((f"c_pok{i}", "Pokemon %d" % i, "pokemon", "B1", "%d" % (100 + i)))
    for i in range(6):
        rows.append((f"c_tr{i}", "Trainer %d" % i, "trainer_supporter", "A1", "%d" % (200 + i)))
    for cid, name, cat, setc, num in rows:
        con.execute("INSERT INTO cards (id,canonical_name,category,mechanical_hash,source_id) "
                    "VALUES (?,?,?,?,?)", (cid, name, cat, "mh-%s" % cid, "play.limitlesstcg.com"))
        con.execute("INSERT INTO card_prints (id,card_id,set_code,number,source_id) "
                    "VALUES (?,?,?,?,?)", ("pr-%s" % cid, cid, setc, num, "play.limitlesstcg.com"))
    con.commit()
    idx = M.build_print_index(con)
    con.close()
    return idx


def standings_entry(pid, aid, aname, wins, losses, decklist=None, placing=None):
    row = {"player": pid, "name": pid, "placing": placing, "record": {"wins": wins, "losses": losses, "ties": 0}}
    if aid:
        row["deck"] = {"id": aid, "name": aname}
    if decklist:
        row["decklist"] = decklist
    return row


def decklist_20():
    """Lista de 20: 10 prints distintos x2 (formato real da API)."""
    entries = []
    for i in range(4):
        entries.append({"count": 2, "set": "B1", "number": "%d" % (100 + i)})
    for i in range(6):
        entries.append({"count": 2, "set": "A1", "number": "%d" % (200 + i)})
    return {"pokemon": entries[:4], "trainer": entries[4:]}


class TestResolveDecklist(unittest.TestCase):
    def test_join_por_set_number_e_falha_contada(self):
        idx = {("B1", "100"): ("c_pok0", "pr-c_pok0"), ("A1", "200"): ("c_tr0", "pr-c_tr0")}
        dl = {"pokemon": [{"count": 2, "set": "B1", "number": "100"}],
              "trainer": [{"count": 2, "set": "A1", "number": "200"},
                          {"count": 1, "set": "ZZ", "number": "999"}]}
        resolved, unresolved = M.resolve_decklist(dl, idx)
        self.assertEqual(sorted(resolved), [("c_pok0", "pr-c_pok0", 2), ("c_tr0", "pr-c_tr0", 2)])
        self.assertEqual(unresolved, 1)

    def test_numero_sem_zero_esquerda_resolve(self):
        idx = {("B1", "100"): ("c_pok0", "pr-c_pok0")}
        dl = {"pokemon": [{"count": 2, "set": "B1", "number": "100"}], "trainer": []}
        resolved, unresolved = M.resolve_decklist(dl, idx)
        self.assertEqual(resolved, [("c_pok0", "pr-c_pok0", 2)])
        self.assertEqual(unresolved, 0)


class TestPairings(unittest.TestCase):
    def setUp(self):
        self.arch_of = {"p1": "a", "p2": "b", "p3": "a"}

    def test_exclusoes_documentadas(self):
        pairings = [
            {"phase": 1, "round": 1, "player1": "p1", "player2": None, "winner": -1},   # bye
            {"phase": 1, "round": 2, "player1": "p1", "player2": "p3", "winner": "p1"},  # espelho
            {"phase": 1, "round": 3, "player1": "p1", "player2": "p2", "winner": 0},     # empate
            {"phase": 1, "round": 4, "player1": "p1", "player2": "p2", "winner": -1},    # double loss
            {"phase": 1, "round": 5, "player1": "p1", "player2": "p2", "winner": "p1"},  # valido
        ]
        games, excl = M.pairings_to_games(pairings, self.arch_of)
        self.assertEqual(games, [("a", "b", "a")])
        self.assertEqual(excl, {"bye_ou_walkover": 1, "espelho": 1, "empate": 1, "double_loss": 1})


class TestWinRateTiers(unittest.TestCase):
    def test_win_rate_com_meio_empate(self):
        self.assertEqual(M.win_rate(6, 2, 2), 70.0)   # (6+1)/10
        self.assertEqual(M.win_rate(0, 0, 0), None)

    def test_faixas_de_tier(self):
        stats = {"decks_by_arch": {}, "rec_w": {}, "rec_l": {}, "rec_t": {},
                 "arch_events": {}, "event_best": {}}
        # 60 listas, 1000 jogos, 55% -> S
        stats["decks_by_arch"]["a"] = 60
        stats["rec_w"]["a"], stats["rec_l"]["a"], stats["rec_t"]["a"] = 550, 450, 0
        stats["arch_events"]["a"] = {"t1", "t2"}
        stats["event_best"] = {"t1": {"a": (6, 1)}, "t2": {"a": (4, 3)}}
        t = M.compute_tiers(stats)["a"]
        self.assertEqual(t["tier"], "S")
        self.assertEqual(t["consistency_pct"], 100.0)
        # 46.5% -> C
        stats["rec_w"]["a"], stats["rec_l"]["a"] = 465, 535
        self.assertEqual(M.compute_tiers(stats)["a"]["tier"], "C")

    def test_sem_evidencia_cita_amostra(self):
        stats = {"decks_by_arch": {"gengar": 3}, "rec_w": {"gengar": 8}, "rec_l": {"gengar": 4},
                 "rec_t": {}, "arch_events": {"gengar": {"t1"}}, "event_best": {"t1": {"gengar": (3, 1)}}}
        t = M.compute_tiers(stats)["gengar"]
        self.assertEqual(t["tier"], "")
        self.assertIn("sem_evidencia", t["basis"])
        self.assertIn("3 listas", t["basis"])
        self.assertIn("12 jogos", t["basis"])


class TestPersistFull(unittest.TestCase):
    """Pipeline completo em banco tmp com migracoes do repositorio."""

    def _fresh_db(self, tmpdir):
        db = Path(tmpdir) / "meta_test.sqlite"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "db_migrate.py"), "--db", str(db)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return db

    def _synthetic_events(self):
        """2 torneios: arquetipo 'a' dominante (gate ok) e 'gengar-test' raro (sem evidencia)."""
        evs = []
        for tid, wins_a in (("t1", True), ("t2", False)):
            st = []
            # 30 players do arquetipo a (lista 20 valida), records alternados
            for i in range(30):
                st.append(standings_entry(f"a{i}", "arch-a", "Altaria Espeon", 5, 1,
                                          decklist=decklist_20()))
            # 30 players de 'b'
            for i in range(30):
                st.append(standings_entry(f"b{i}", "arch-b", "Raticate Ninetales", 3, 3,
                                          decklist=decklist_20()))
            # raro: 2 listas de gengar (abaixo do gate MIN_DECKS=20)
            for i in range(2):
                st.append(standings_entry(f"g{i}", "arch-gengar-test", "Gengar Test",
                                          4, 2, decklist=decklist_20()))
            # lista quebrada (19 cartas apos unresolved) nao vira deck
            st.append(standings_entry("x1", "arch-a", "Altaria Espeon", 0, 3, decklist={
                "pokemon": [{"count": 2, "set": "B1", "number": "102"}], "trainer": []}))
            pairings = [
                {"phase": 1, "round": 1, "player1": "a0", "player2": "b0", "winner": "a0" if wins_a else "b0"},
                {"phase": 1, "round": 2, "player1": "a1", "player2": "b1", "winner": "a1"},
                {"phase": 1, "round": 3, "player1": "g0", "player2": "b2", "winner": "g0"},
                {"phase": 1, "round": 4, "player1": "a2", "player2": None, "winner": -1},
            ]
            evs.append({"tid": tid, "date": "2026-10-10", "name": f"T {tid}", "players": 92,
                        "details": {"format": "STANDARD", "isPublic": True, "decklists": True,
                                    "phases": [{"type": "SWISS"}]},
                        "standings": st, "pairings": pairings})
        return evs

    def test_pipeline_completo_e_idempotente(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._fresh_db(td)
            idx = make_print_index(td)
            window = {"start": "2026-10-01", "end": "2026-10-19"}
            events = self._synthetic_events()
            con = M.open_db(db)
            M.ensure_source(con)
            stats = M.compute_stats(window, events, idx)
            tiers = M.compute_tiers(stats)
            snap_id = M.persist(con, window, events, stats, tiers, 30, idx)
            con.close()

            con = M.sqlite3.connect(str(db))
            # snapshot com totais certos
            snap = con.execute("SELECT tournament_count, decklist_count, match_count FROM meta_snapshots WHERE id=?",
                               (snap_id,)).fetchone()
            self.assertEqual(snap[0], 2)
            # 30+30+2 validas por torneio = 124 (a quebrada entra no share de listas? NAO:
            # decklist presente conta em decklist_count) => 62 por torneio * 2 = 124 + 2 quebradas = 126
            self.assertEqual(snap[1], 126)
            self.assertEqual(snap[2], 8)  # 4 pairings por torneio x 2 torneios
            # tiers: a com gate ok; gengar sem evidencia; decks so de lista 20
            rows = {r[0]: r[1] for r in con.execute("SELECT id, tier FROM meta_archetypes")}
            self.assertIn(rows["arch-a"], ("S", "A", "B", "C", "D"))
            self.assertEqual(rows["arch-gengar-test"], "")
            basis = con.execute("SELECT tier_basis FROM meta_archetypes WHERE id='arch-gengar-test'").fetchone()[0]
            self.assertIn("sem_evidencia", basis)
            self.assertIn("4 listas", basis)
            decks_a = con.execute("SELECT count(*) FROM decks WHERE archetype_id='arch-a'").fetchone()[0]
            self.assertEqual(decks_a, 60)  # 30 x 2 torneios (a quebrada fora)
            # todas as deck_card quantity entre 1-2 e deck com 20 cartas
            bad = con.execute("""SELECT count(*) FROM decks d WHERE
                                 (SELECT COALESCE(SUM(quantity),0) FROM deck_cards WHERE deck_id=d.id) != 20""").fetchone()[0]
            self.assertEqual(bad, 0)
            # matchups: par a x b — 2 jogos validos por torneio (a0-b0, a1-b1) = 4 na janela
            mu = con.execute("SELECT win_rate_a_pct, sample_size, confidence FROM matchups WHERE archetype_a='arch-a' AND archetype_b='arch-b'").fetchone()
            self.assertIsNotNone(mu)
            self.assertEqual(mu[1], 4)
            self.assertEqual(mu[0], 75.0)  # a venceu 3 (a0,a1 no t1; a1 no t2), b venceu 1 (b0 no t2)
            self.assertEqual(mu[2], "low")
            # gengar matchup: 1 confronto g0-b2 por torneio x 2 torneios = 2 jogos (gengar 2-0)
            mu_g = con.execute("SELECT sample_size, confidence FROM matchups WHERE archetype_a='arch-gengar-test' OR archetype_b='arch-gengar-test'").fetchone()
            self.assertEqual(mu_g[0], 2)
            self.assertEqual(mu_g[1], "low")
            con.close()

            # reexecucao (mesma janela): IDEMPOTENTE (contagens inalteradas)
            con = M.open_db(db)
            stats2 = M.compute_stats(window, events, idx)
            tiers2 = M.compute_tiers(stats2)
            M.persist(con, window, events, stats2, tiers2, 30, idx)
            n_snap = con.execute("SELECT count(*) FROM meta_snapshots").fetchone()[0]
            n_decks = con.execute("SELECT count(*) FROM decks").fetchone()[0]
            n_matches = con.execute("SELECT count(*) FROM tournament_matches").fetchone()[0]
            con.close()
            self.assertEqual(n_snap, 1)
            self.assertEqual(n_decks, 124)  # 62 validas/torneio (30a+30b+2gengar) x 2, idempotente
            self.assertEqual(n_matches, 8)  # todos os pairings auditados (inclui bye)

            # janela DIFERENTE coexiste (apend-only)
            con = M.open_db(db)
            w7 = {"start": "2026-10-13", "end": "2026-10-19"}
            M.persist(con, w7, events[:1], stats2, tiers2, 7, idx)
            n_snaps = con.execute("SELECT count(*) FROM meta_snapshots").fetchone()[0]
            con.close()
            self.assertEqual(n_snaps, 2)

    def test_migration_0003_aceita_S_e_rejeita_lixo(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._fresh_db(td)
            con = M.sqlite3.connect(str(db))
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("INSERT INTO sources (id,name,kind,tier) VALUES ('s','S','api','canonical')")
            con.execute("INSERT INTO meta_archetypes (id,name,tier,tier_basis,source_id) VALUES ('a','A','S','b','s')")
            con.execute("INSERT INTO meta_snapshots (id,window_start,window_end,scope,source_id) VALUES ('sn','2026-10-01','2026-10-19','x','s')")
            con.execute("INSERT INTO tiers (id,snapshot_id,archetype_id,tier,basis) VALUES ('t','sn','a','S','b')")
            with self.assertRaises(M.sqlite3.IntegrityError):
                con.execute("INSERT INTO tiers (id,snapshot_id,archetype_id,tier,basis) VALUES ('t2','sn','a','Z','b')")
            con.close()


if __name__ == "__main__":
    unittest.main()
