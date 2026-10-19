"""F7b - teste de reconciliacao raw x banco do metagame.

Defeito que este teste impede de voltar (card t_7872dcac): a coleta cobre 35 dias
(collect_meta.py, POCKET_META_DAYS=35) mas a analise usava janela rolante de 30
dias — 41 torneios elegiveis (2026-09-09..2026-09-19) ficaram de fora do banco
silenciosamente, rotulados apenas como contagem agregada "fora_da_janela".

Regras auditadas aqui:
1. Torneio elegivel (gates de escopo de docs/META.md) fora da janela rolante NAO
   e lixo: o modo --full (full=True) ingere todo o raw elegivel.
2. Toda exclusao e nomeada: excl_nominal[motivo] = lista de tids (nada agregado
   sem rastro).
3. Reconciliacao REAL: elegiveis no raw == tournaments no banco (leitura ro).
   Falha se houver elegivel coletado e nao ingerido (ex.: nova coleta sem
   re-ingestao) — o teste falha e a re-ingestao (--full) corrige.

Nenhum teste escreve no banco de producao: o sintetico usa tmpdir; o real abre
data/pocket.sqlite em modo somente-leitura (uri mode=ro).
"""
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "meta"))
sys.path.insert(0, str(ROOT))

import meta_pipeline as M  # noqa: E402

RAW_REAL = ROOT / "data" / "meta" / "raw"
DB_REAL = ROOT / "data" / "pocket.sqlite"


# ------------------------------------------------------------------ helpers sinteticos
def standings_entry(pid, aid, aname, wins, losses, decklist=None):
    row = {"player": pid, "name": pid, "placing": None,
           "record": {"wins": wins, "losses": losses, "ties": 0}}
    if aid:
        row["deck"] = {"id": aid, "name": aname}
    if decklist:
        row["decklist"] = decklist
    return row


def decklist_20():
    """Lista de 20 cartas (10 prints x2) — mesma forma da API real."""
    entries = [{"count": 2, "set": "B1", "number": "%d" % (100 + i)} for i in range(4)]
    entries += [{"count": 2, "set": "A1", "number": "%d" % (200 + i)} for i in range(6)]
    return {"pokemon": entries[:4], "trainer": entries[4:]}


def iso_days_ago(days: float) -> str:
    return time.strftime("%Y-%m-%dT%H:00:00.000Z", time.gmtime(time.time() - days * 86400))


def make_raw(tmpdir, listing: dict, details: dict, standings: dict, pairings: dict | None = None):
    """Cria raw sintetico no formato da Limitless (pages/ + tournaments/{id}/)."""
    raw = Path(tmpdir) / "raw"
    pages = raw / "pages"
    pages.mkdir(parents=True)
    (pages / "page_1.json").write_text(json.dumps(list(listing.values())))
    pairings = pairings or {}
    for tid in listing:
        d = raw / "tournaments" / tid
        d.mkdir(parents=True)
        (d / "details.json").write_text(json.dumps(details[tid]))
        (d / "standings.json").write_text(json.dumps(standings[tid]))
        (d / "pairings.json").write_text(json.dumps(pairings.get(tid, [])))
    return raw


class TestReconciliacaoSintetica(unittest.TestCase):
    """Raw sintetico: 2 elegiveis (1 fora de qualquer janela curta), 2 excluidos."""

    def _montar(self, td):
        listing = {
            "tA": {"id": "tA", "date": iso_days_ago(40), "players": 50, "name": "Antigo Elegivel"},
            "tB": {"id": "tB", "date": iso_days_ago(3), "players": 40, "name": "Recente Elegivel"},
            "tC": {"id": "tC", "date": iso_days_ago(2), "players": 30, "name": "NOEX Cup"},
            "tD": {"id": "tD", "date": iso_days_ago(1), "players": 5, "name": "Pequeno"},
        }
        details, standings = {}, {}
        for tid, fmt, players in (("tA", "STANDARD", 50), ("tB", "STANDARD", 40),
                                  ("tC", "NOEX", 30), ("tD", "STANDARD", 5)):
            details[tid] = {"format": fmt, "isPublic": True, "decklists": True,
                            "phases": [{"type": "SWISS"}]}
            standings[tid] = [standings_entry(f"{tid}-p{i}", f"arch-{i % 2}", f"Arch {i % 2}",
                                              3, 2, decklist=decklist_20()) for i in range(10)]
        raw = make_raw(td, listing, details, standings)
        return raw, {"tA", "tB"}, {"tC": "formato_nao_standard", "tD": "players_minimo"}

    def _db(self, td):
        db = Path(td) / "meta_test.sqlite"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "db_migrate.py"), "--db", str(db)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return db

    def test_full_ingerir_fora_da_janela_e_exclusoes_nomeadas(self):
        with tempfile.TemporaryDirectory() as td:
            raw, elegiveis, excl_esperadas = self._montar(td)
            # janela rolante curta DESCARTA o antigo — mas de forma NOMEADA
            w, evs, load_excl = M.load_window(raw, days=7,
                                              end_date=time.strftime("%Y-%m-%d", time.gmtime()))
            self.assertEqual({e["tid"] for e in evs}, {"tB"})
            self.assertIn("tA", load_excl["excl_nominal"]["fora_da_janela"])
            # modo full: TODO elegivel entra, exclusoes nominais por motivo
            w, evs, load_excl = M.load_window(raw, days=1, full=True)
            self.assertEqual({e["tid"] for e in evs}, elegiveis)
            for tid, motivo in excl_esperadas.items():
                self.assertIn(tid, load_excl["excl_nominal"][motivo])
            self.assertEqual(load_excl["excl"].get("fora_da_janela", 0), 0)  # full nao tem fora_da_janela

            db = self._db(td)
            con = M.open_db(db)
            M.ensure_source(con)
            idx = M.build_print_index(con)
            stats = M.compute_stats(w, evs, idx, load_excl)
            tiers = M.compute_tiers(stats)
            snap_id = M.persist(con, w, evs, stats, tiers, 1, idx, full=True)
            con.close()
            self.assertTrue(snap_id.startswith("snap-full-"))

            # reconciliacao: elegiveis no raw == tournaments no banco
            con = sqlite3.connect(str(db))
            db_tids = {r[0] for r in con.execute("SELECT id FROM tournaments")}
            con.close()
            self.assertEqual(db_tids, elegiveis)

    def test_relatorio_carrega_exclusoes_nominais(self):
        with tempfile.TemporaryDirectory() as td:
            raw, _eleg, _excl = self._montar(td)
            w, evs, load_excl = M.load_window(raw, days=1, full=True)
            idx = {}
            stats = M.compute_stats(w, evs, idx, load_excl)
            tiers = M.compute_tiers(stats)
            rep = M.report("snap-full-test", w, evs, stats, tiers)
            self.assertEqual(rep["exclusions"]["excl"]["formato_nao_standard"], 1)
            self.assertEqual(rep["exclusions"]["excl_nominal"]["formato_nao_standard"], ["tC"])
            self.assertEqual(rep["exclusions"]["excl_nominal"]["players_minimo"], ["tD"])


@unittest.skipUnless(RAW_REAL.exists() and DB_REAL.exists(),
                     "raw/banco de producao ausentes neste ambiente")
class TestReconciliacaoReal(unittest.TestCase):
    """Guarda permanente: elegivel coletado tem que estar no banco (leitura ro)."""

    def test_todos_os_elegiveis_do_raw_estao_no_banco(self):
        w, evs, load_excl = M.load_window(RAW_REAL, days=1, full=True)
        raw_elegiveis = {e["tid"] for e in evs}
        con = sqlite3.connect(f"file:{DB_REAL}?mode=ro", uri=True)
        db_tids = {r[0] for r in con.execute("SELECT id FROM tournaments")}
        con.close()
        faltando = sorted(raw_elegiveis - db_tids)
        indevidos = sorted(db_tids - raw_elegiveis)
        self.assertEqual(
            faltando, [],
            f"RECONCILIACAO F7b FALHOU: {len(faltando)} elegiveis no raw fora do banco "
            f"(primeiros: {faltando[:10]}). Reexecutar: python3 scripts/meta/meta_pipeline.py --full")
        self.assertEqual(
            indevidos, [],
            f"RECONCILIACAO F7b FALHOU: {len(indevidos)} torneios no banco fora dos gates "
            f"do escopo (primeiros: {indevidos[:10]})")
        # exclusoes do escopo sao nomeadas e somam o resto do raw
        excl_nominal = load_excl["excl_nominal"]
        todos_excl = {t for tids in excl_nominal.values() for t in tids}
        paginas = set()
        for p in sorted((RAW_REAL / "pages").glob("page_*.json")):
            paginas |= {t.get("id") for t in json.loads(p.read_text())}
        self.assertEqual(paginas - raw_elegiveis, todos_excl,
                         "toda exclusao deve ser nomeada por motivo (regra F7b)")


if __name__ == "__main__":
    unittest.main()
