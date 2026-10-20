"""F12 · Guarda anti-divergencia: skill no repo = skill instalada (t_99f12).

Contrato (DEV-02 da F10): cada skill em <repo>/skills/ deve existir com a MESMA
arvore de arquivos (sha256 por arquivo) na copia canonica do Hermes
($HERMES_ROOT/skills/ — raiz canonica do Hermes no host) e em cada perfil-alvo
($HERMES_ROOT/profiles/<perfil>/skills/). Qualquer divergencia — arquivo
divergente, ausente ou EXTRA no destino — reprova a suite.

Isso existe porque a classe de defeito se repetiu 3x (F3, F6, F7-F9): instalacao
feita com HERMES_HOME desviado para o perfil (arvore fantasma
profiles/<perfil>/profiles/) e skill re-versionada no repo sem redistribuicao
(card-vision 5c83438b != 33fc2c25). O teste roda o proprio
scripts/install_skills.sh --verify (raciocinio de comparacao NAO duplicado) e,
alem disso, verifica diretamente a tabela de destinos esperados.

A suite NUNCA instala (somente leitura); a redistribuicao e o
install_skills.sh, nao o teste. Sem a raiz canonica do Hermes no host (ex.:
checkout cru em outra maquina), pula com motivo explicito — dependencia de
ambiente, nao defeito.
"""

import hashlib
import os
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SKILLS_SRC = REPO / "skills"
INSTALLER = REPO / "scripts" / "install_skills.sh"
# Portavel: default = raiz Hermes do proprio usuario; override por
# TCGP_HERMES_ROOT (checkout em maquina alternativa pula com motivo claro).
HERMES_ROOT = Path(os.environ.get("TCGP_HERMES_ROOT", Path.home() / ".hermes"))
PERFIS = ["tony_stark", "hermione_granger", "leia_organa", "c3po"]

IGNORAR = {".DS_Store", "__pycache__"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _arquivos_skill(dir_skill: Path) -> dict:
    """{caminho_relativo: sha256} da arvore completa da skill."""
    saida = {}
    for root, dirs, files in os.walk(dir_skill):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for fn in files:
            if fn in IGNORAR:
                continue
            fp = Path(root) / fn
            saida[str(fp.relative_to(dir_skill))] = _sha256(fp)
    return saida


def _skills_do_repo() -> list:
    return sorted(d for d in SKILLS_SRC.iterdir() if (d / "SKILL.md").is_file())


class TestF12SkillsInstaladas(unittest.TestCase):
    PULOU = None

    @classmethod
    def setUpClass(cls):
        if not INSTALLER.is_file():
            raise unittest.SkipTest("scripts/install_skills.sh ausente no repo")
        if os.name != "posix":
            raise unittest.SkipTest("instalador bash requer POSIX")
        if not (HERMES_ROOT / "skills").is_dir():
            cls.PULOU = (
                f"raiz canonica do Hermes ausente neste host ({HERMES_ROOT}) — "
                "ver docs/TESTING.md secao 5; a suite NAO instala nada"
            )
            raise unittest.SkipTest(cls.PULOU)
        if not os.access(INSTALLER, os.X_OK):
            raise unittest.SkipTest("install_skills.sh sem permissao de execucao")

    def test_1_verify_installer_rc0(self):
        """O proprio install_skills.sh --verify (raiz fixa) aprova as skills do repo.

        F13: a guarda e DINAMICA — itera skills/ do repo sem lista fixa, entao
        a 6a skill (card-database) entra por iteracao, nao por edicao aqui.
        """
        proc = subprocess.run(
            ["bash", str(INSTALLER), "--verify"],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"install_skills.sh --verify rc={proc.returncode}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        self.assertIn("hash unico verificado: ok", proc.stdout)
        skills = _skills_do_repo()
        for s in skills:
            self.assertIn(f"ok    {s.name} ", proc.stdout)

    def test_2_arvore_completa_por_destino(self):
        """Cada arquivo de cada skill do repo tem hash identico em todos os destinos."""
        repo_tree = {s.name: _arquivos_skill(s) for s in _skills_do_repo()}
        self.assertGreater(len(repo_tree), 0, "nenhuma skill no repo")
        destinos = [("canonica", HERMES_ROOT / "skills")] + [
            (f"perfil:{p}", HERMES_ROOT / "profiles" / p / "skills") for p in PERFIS
        ]
        problemas = []
        for nome, arvore in sorted(repo_tree.items()):
            for rotulo, base in destinos:
                dir_destino = base / nome
                if not dir_destino.is_dir():
                    problemas.append(f"{nome}@{rotulo}: DIRETORIO AUSENTE")
                    continue
                destino_tree = _arquivos_skill(dir_destino)
                for rel, h in sorted(arvore.items()):
                    if rel not in destino_tree:
                        problemas.append(f"{nome}@{rotulo}: {rel} AUSENTE no destino")
                    elif destino_tree[rel] != h:
                        problemas.append(
                            f"{nome}@{rotulo}: {rel} divergente "
                            f"({destino_tree[rel][:12]} != {h[:12]})"
                        )
                for rel in sorted(destino_tree):
                    if rel not in arvore:
                        problemas.append(f"{nome}@{rotulo}: {rel} EXTRA no destino")
        self.assertEqual(
            problemas, [],
            "skill no repo != skill instalada (redistribua: bash scripts/install_skills.sh)"
            "\n  " + "\n  ".join(problemas),
        )

    def test_3_instalador_nao_herda_hermes_home(self):
        """Raiz canonica fixa: HERMES_HOME desviado no shell NAO muda o destino.

        Regressao direta da causa-raiz do DEV-02: com HERMES_HOME apontando para
        um perfil, o instalador antigo instalava numa arvore fantasma e o verify
        dizia 'ok' na raiz errada. Aqui so simulamos com --verify (nunca instala)
        contra uma raiz inexistente para provar que o caminho NAO depende do
        ambiente; rc=3 = fail-fast correto apontando a raiz fixa.
        """
        env = dict(os.environ)
        env["HERMES_HOME"] = str(Path(os.environ.get("HOME", "/tmp")) / "hermes-falso-f12")
        proc = subprocess.run(
            ["bash", str(INSTALLER), "--verify"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        self.assertEqual(proc.returncode, 0)  # raiz real e fixa: HERMES_HOME e ignorado
        self.assertIn("hash unico verificado: ok", proc.stdout)

    def test_4_fail_fast_raiz_ausente(self):
        """HERMES_ROOT_SKILLS inexistente -> rc=3 com mensagem clara (sem instalar)."""
        env = dict(os.environ)
        env["HERMES_ROOT_SKILLS"] = "/nonexistent/f12-nao-existe"
        proc = subprocess.run(
            ["bash", str(INSTALLER), "--verify"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        self.assertEqual(proc.returncode, 3)
        self.assertIn("raiz canonica do Hermes nao existe", proc.stderr)


if __name__ == "__main__":
    unittest.main()
