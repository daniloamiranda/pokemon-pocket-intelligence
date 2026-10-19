"""F13 · Skill pokemon-pocket-card-database: consulta e atualizacao (t_24f07bbc).

Contratos vigiados:
1. A face de CONSULTA (scripts/db_query.py) reflete o banco canonico
   (data/pocket.sqlite) aberto em mode=ro — contagens iguais a leitura SQL
   direta independente; ficha resolve identidade mecanica + impressoes.
2. A face de ATUALIZACAO em dry-run (collect_pocket.py --dry-run) produz o
   PLANO offline: zero rede (prova temporal: duracao << 1 requisicao de rate
   limit), zero escrita (mtimes do banco e do relatorio intocados).
3. A skill existe no repo COMO DECLARADA: frontmatter no padrao das irma
   (license MIT nas 6 — decisao do Proprietario aplicada na F14), related_skills
   resolvendo para skills reais, e o gen_contracts.py declara
   pokemon-pocket-card-database como produtora/consumidora nos contratos.
4. A instalacao e vigiada pela guarda F12 (test_f12_skills_guard.py), que
   itera o repo dinamicamente — a 6a skill entra sem lista fixa.

A suite NUNCA instala, NUNCA coleta na rede e NUNCA escreve no banco.
Sem o catalogo em data/pocket.sqlite, os casos dependentes de banco PULAM com
motivo explicito (dependencia de ambiente, nao defeito).
"""

import json
import subprocess
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "pocket.sqlite"
SKILL_DIR = ROOT / "skills" / "pokemon-pocket-card-database"
SKILL_MD = SKILL_DIR / "SKILL.md"


def _run(*args, timeout=180):
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, timeout=timeout)


def _db_counts(direct):
    import sqlite3
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        for table in ("expansions", "cards", "card_prints"):
            direct[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


class _CatalogoTestCase(unittest.TestCase):
    """Base: pulo com motivo quando o catalogo nao esta neste checkout."""

    def setUp(self):
        if not DB.is_file():
            raise unittest.SkipTest(
                f"catalogo ausente neste checkout ({DB}) — dependencia de ambiente, "
                "nao defeito (colete com scripts/collect_pocket.py fora da suite)")


class TestF13Consulta(_CatalogoTestCase):

    @classmethod
    def setUpClass(cls):
        if not DB.is_file():
            raise unittest.SkipTest("catalogo ausente (ver class docstring)")

    def test_1_stats_confere_com_leitura_direta(self):
        """stats do db_query == contagens SQL diretas independentes; piso do aceite."""
        proc = _run("python3", "scripts/db_query.py", "stats")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stats = json.loads(proc.stdout)
        direto = {}
        _db_counts(direto)
        self.assertEqual(stats["expansions"], direto["expansions"])
        self.assertEqual(stats["cards"], direto["cards"])
        self.assertEqual(stats["card_prints"], direto["card_prints"])
        # piso do aceite F13 (monotonico: coleta aditiva so cresce)
        self.assertGreaterEqual(stats["expansions"], 24, "24 conjuntos no aceite")
        self.assertGreaterEqual(stats["cards"], 2319, "2.319 identidades no aceite")
        self.assertGreaterEqual(stats["card_prints"], 4317, "4.317 impressoes no aceite")

    def test_2_coverage_100_sem_gap(self):
        """Cobertura integral com o banco atual: 100%, zero gap, promos a parte."""
        proc = _run("python3", "scripts/db_query.py", "coverage")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cov = json.loads(proc.stdout)
        self.assertEqual(cov["overall_pct"], 100.0)
        self.assertEqual(cov["sets_with_gap"], [], "nenhum gap com o banco do aceite")
        self.assertIn("P-A", cov["promo_sets"], "promos ficam fora do percentual")
        self.assertIn("P-B", cov["promo_sets"])
        b4b = next(e for e in cov["per_set"] if e["set"] == "B4b")
        self.assertEqual(b4b["declared"], 429)
        self.assertEqual(b4b["loaded"], 429)
        self.assertEqual(b4b["coverage_pct"], 100.0)

    def test_3_ficha_mega_gengar_identidade_e_prints(self):
        """Ficha real: identidade mecanica + prints B2b 39/114, B4b 141/419."""
        proc = _run("python3", "scripts/db_query.py", "card", "Mega Gengar ex")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ficha = json.loads(proc.stdout)
        self.assertEqual(ficha["status"], "ok")
        self.assertEqual(ficha["card"]["id"], "limitless:B2b/39")
        self.assertEqual(ficha["card"]["hp"], 210)
        self.assertEqual(ficha["card"]["element"], "darkness")
        self.assertEqual(ficha["card"]["stage"], "mega_ex")
        self.assertTrue(ficha["card"]["is_ex"])
        self.assertEqual(ficha["card"]["mechanical_hash"],
                         "6e7202059617d5804a1cbf5ee495ebd123c96893f07c646c5fac9bc61ea8157b")
        print_ids = {p["id"] for p in ficha["prints"]}
        self.assertTrue({"B2b#39", "B2b#114", "B4b#141"}.issubset(print_ids))
        self.assertEqual(ficha["attacks"][0]["name"], "Labyrinth of Shadows")

    def test_4_termo_ambiguo_nunca_chuta(self):
        """Termo parcial ambiguo -> status ambiguo com candidatos (regra: sem chute)."""
        proc = _run("python3", "scripts/db_query.py", "card", "Mega")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["status"], "ambiguo")
        self.assertGreaterEqual(len(out["candidates"]), 2)

    def test_5_card_inexistente_rc1_com_mensagem(self):
        proc = _run("python3", "scripts/db_query.py", "card", "NaoExisteNada123XYZ")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("nenhuma carta encontrada", proc.stderr)


class TestF13DryRun(_CatalogoTestCase):

    @classmethod
    def setUpClass(cls):
        if not DB.is_file():
            raise unittest.SkipTest("catalogo ausente (ver class docstring)")

    def test_6_dry_run_zero_rede_zero_escrita(self):
        """Plano offline: garantia declarada + prova temporal + dado intocado.

        Vigia o DADO (pocket.sqlite + collection_report.json). Os sidecars
        -wal/-shm sao COORDENACAO de acesso do WAL (mtime muda ate em
        leitura, por read-marks) — nao sao dado, nao provam escrita.
        """
        alvos = [DB, ROOT / "data" / "collection_report.json"]
        antes = {p: p.stat().st_mtime_ns for p in alvos if p.is_file()}
        t0 = time.monotonic()
        proc = _run("python3", "scripts/collect_pocket.py", "--dry-run")
        dur = time.monotonic() - t0
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plano = json.loads(proc.stdout)
        self.assertEqual(plano["mode"], "dry-run")
        self.assertIn("nenhuma requisicao HTTP", plano["garantia"])
        self.assertIn("nenhuma escrita", plano["garantia"])
        self.assertEqual(plano["estado_atual"]["cards"], 2319)
        # prova temporal: se houvesse rede real (4.1k reqs x 1.2s), levaria ~83 min;
        # o dry-run inteiro roda em menos de UMA requisicao do rate limit.
        self.assertLess(dur, 1.2, f"dry-run levou {dur:.2f}s — rede real seria ~83 min")
        depois = {p: p.stat().st_mtime_ns for p in alvos if p.is_file()}
        self.assertEqual(antes, depois, "dry-run alterou mtime de dado de producao")

    def test_7_dry_run_incremental_sem_inventar_estimativa(self):
        proc = _run("python3", "scripts/collect_pocket.py", "--sets", "A4a", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plano = json.loads(proc.stdout)
        self.assertEqual(plano["sets_conhecidos"], ["A4a"])
        self.assertGreater(plano["requisicoes_estimadas"], 0)
        # promos sem contagem declarada: estimativa indisponivel, nunca inventada
        proc2 = _run("python3", "scripts/collect_pocket.py", "--sets", "P-A", "--dry-run")
        plano2 = json.loads(proc2.stdout)
        ps = plano2["per_set_estimativa"][0]
        self.assertIsNone(ps["fichas_estimadas"])
        self.assertIn("estimativa indisponivel", ps["note"])

    def test_8_dry_run_sem_banco_rc0(self):
        """Plano funciona mesmo sem banco (db_exists=false) — nada explode."""
        proc = _run("python3", "scripts/collect_pocket.py",
                    "--db", "/tmp/f13-nao-existe.sqlite", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plano = json.loads(proc.stdout)
        self.assertFalse(plano["db_exists"])
        self.assertIsNone(plano["estado_atual"]["cards"])


class TestF13DeclaracaoDaSkill(unittest.TestCase):
    """A skill existe como DECLARADA (frontmatter + contratos). Sem banco, roda igual."""

    def test_10_skill_md_no_repo_frontmatter_padrao_das_irmas(self):
        self.assertTrue(SKILL_MD.is_file(), f"SKILL.md ausente: {SKILL_MD}")
        texto = SKILL_MD.read_text(encoding="utf-8")
        self.assertTrue(texto.startswith("---"), "frontmatter ausente")
        fim = texto.index("---", 3)
        front = texto[3:fim]
        self.assertIn("name: pokemon-pocket-card-database", front)
        self.assertIn("Use ao consultar ou atualizar o catalogo", front,
                      "description deve ser auto-suficiente no gatilho")
        # license IGUAL entre irmas — hoje: MIT em todas (F14, t_ea82a78b)
        lic_nova = [l.split(":", 1)[1].strip() for l in front.splitlines()
                    if l.strip().startswith("license:")][0]
        rules = (ROOT / "skills" / "pokemon-pocket-rules" / "SKILL.md").read_text(
            encoding="utf-8")
        lic_irma = [l.split(":", 1)[1].strip() for l in rules.splitlines()
                    if l.strip().startswith("license:")][0]
        self.assertEqual(lic_nova, lic_irma,
                         "licenca deve ser IGUAL a das irmas (MIT — F14 t_ea82a78b)")
        # corpo obrigatorio do escopo
        for secao in ("## Responsabilidade", "## Quando usar", "## MODO A", "## MODO B",
                      "## Contratos", "## Fontes", "## Limites honestos", "## Armadilhas"):
            self.assertIn(secao, texto, f"secao obrigatoria ausente: {secao}")
        for armadilha in ("data/pocket.sqlite", "Print errado e PIOR que print ausente",
                          "Promos sem href nao se adivinham",
                          "INSERT OR IGNORE fossiliza", "Skill no repo != skill instalada",
                          "--only-list", "--dry-run"):
            self.assertIn(armadilha, texto, f"armadilha/limite nao declarado: {armadilha}")

    def test_11_related_skills_resolvem_para_skills_reais(self):
        front = SKILL_MD.read_text(encoding="utf-8")
        linha = next(l for l in front.splitlines() if "related_skills" in l)
        import re
        nomes = re.findall(r"pokemon-pocket-[\w-]+", linha)
        self.assertGreaterEqual(len(nomes), 5, f"related_skills incompleto: {nomes}")
        faltando = [n for n in nomes
                    if not (ROOT / "skills" / n / "SKILL.md").is_file()]
        self.assertEqual(faltando, [], f"related_skills aponta para skill inexistente: {faltando}")
        # e a rules declara a card-database de volta (ciclo declarado no escopo)
        rules = (ROOT / "skills" / "pokemon-pocket-rules" / "SKILL.md").read_text(
            encoding="utf-8")
        self.assertIn("pokemon-pocket-card-database", rules)

    def test_12_gen_contracts_declara_card_database(self):
        fonte = (ROOT / "scripts" / "gen_contracts.py").read_text(encoding="utf-8")
        n = fonte.count('"pokemon-pocket-card-database"')
        self.assertGreaterEqual(n, 4,
                                f"gen_contracts.py cita card-database {n}x (esperado >= 4)")

    def test_13_db_query_e_ferramenta_canonica_no_repo(self):
        self.assertTrue((ROOT / "scripts" / "db_query.py").is_file())
        fonte = (ROOT / "scripts" / "db_query.py").read_text(encoding="utf-8")
        self.assertIn("mode=ro", fonte, "consulta deve abrir o banco em mode=ro")
        self.assertIn("--dry-run", (ROOT / "scripts" / "collect_pocket.py").read_text(
            encoding="utf-8"), "coletor deve ter dry-run real")


if __name__ == "__main__":
    unittest.main()
