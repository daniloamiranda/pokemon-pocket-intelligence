"""F14 · Guarda de licenca: skill declara a MESMA licenca do LICENSE da raiz (t_ea82a78b).

Contrato (decisao do Proprietario, 19/10/2026): o codigo do repositorio e MIT
(arquivo LICENSE na raiz) e as SEIS skills declaram `license: MIT` no
frontmatter. Esta guarda reprova a suite quando:

  1. o LICENSE da raiz desaparece ou tem identificador nao reconhecido;
  2. qualquer SKILL.md do REPO declara licenca ausente/divergente
     (ex.: `proprietary` voltando por copia de perfil antiga);
  3. qualquer copia instalada (copia canonica do Hermes ou perfil-alvo)
     declara licenca divergente do LICENSE da raiz — cobieira propria do F14,
     complementar a guarda F12 (que compara a ARVORE inteira repo x destino).

Dinamica como a F13: itera skills/ do repo SEM lista fixa — skill nova entra
por iteracao. O reconhecedor de identificador do LICENSE e um mapa minimo
( MIT License -> MIT ); identificador desconhecido reprova, para forcar
atualizacao consciente da guarda em vez de drift silencioso.

Somente leitura; nunca edita LICENSE nem skills. Sem a raiz canonica do Hermes
no host (checkout cru em outra maquina), pula com motivo explicito.
"""

import os
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SKILLS_SRC = REPO / "skills"
LICENSE = REPO / "LICENSE"
HERMES_ROOT = Path("/home/hermes/.hermes")
PERFIS = ["tony_stark", "hermione_granger", "leia_organa", "c3po"]

# Mapa minimo de reconhecimento (primeira linha do texto -> identificador SPDX).
IDENTIFICADORES = {
    "MIT LICENSE": "MIT",
    "APACHE LICENSE": "Apache-2.0",
}


def _identificador_licenca_raiz() -> str:
    """Identificador declarado no LICENSE da raiz; ValueError se desconhecido."""
    texto = LICENSE.read_text(encoding="utf-8")
    primeira = texto.strip().splitlines()[0].strip().upper()
    for chave, ident in IDENTIFICADORES.items():
        if primeira.startswith(chave):
            return ident
    raise ValueError(
        f"identificador de licenca nao reconhecido em {LICENSE}: '{primeira}' — "
        "atualize o mapa IDENTIFICADORES da guarda (nada de drift silencioso)"
    )


def _license_declarada(skmd: Path) -> str:
    """Valor de `license:` do frontmatter; ValueError se ausente/malformado."""
    t = skmd.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    if not m:
        raise ValueError(f"{skmd}: frontmatter nao encontrado")
    ml = re.search(r"^license:(.*)$", m.group(1), re.M)
    if not ml:
        raise ValueError(f"{skmd}: campo `license:` ausente do frontmatter")
    return ml.group(1).strip().strip("\"'").strip()


def _skills_do_repo() -> list:
    return sorted(d for d in SKILLS_SRC.iterdir() if (d / "SKILL.md").is_file())


class TestF14GuardaLicenca(unittest.TestCase):
    PULOU = None

    @classmethod
    def setUpClass(cls):
        if not LICENSE.is_file():
            raise unittest.SkipTest("LICENSE ausente na raiz do repo")
        if not (HERMES_ROOT / "skills").is_dir():
            cls.PULOU = (
                f"raiz canonica do Hermes ausente neste host ({HERMES_ROOT}) — "
                "a guarda de copias instaladas NAO roda aqui; ver docs/TESTING.md"
            )
            raise unittest.SkipTest(cls.PULOU)

    def test_1_license_raiz_reconhecido(self):
        """LICENSE da raiz existe e tem identificador reconhecido (contrato F14: MIT)."""
        try:
            ident = _identificador_licenca_raiz()
        except ValueError as e:
            self.fail(str(e))
        self.assertEqual(ident, "MIT", "decisao do Proprietario (19/10): codigo e MIT")

    def test_2_skills_repo_declaram_licenca_da_raiz(self):
        """Cada SKILL.md do REPO declara `license:` IGUAL ao identificador do LICENSE."""
        raiz = _identificador_licenca_raiz()
        problemas = []
        for d in _skills_do_repo():
            try:
                declarada = _license_declarada(d / "SKILL.md")
            except ValueError as e:
                problemas.append(str(e))
                continue
            if declarada != raiz:
                problemas.append(
                    f"{d.name}: license '{declarada}' != LICENSE da raiz '{raiz}'"
                )
        self.assertEqual(
            problemas, [],
            "licenca declarada diverge do LICENSE da raiz (redistribua/conserte):\n  "
            + "\n  ".join(problemas),
        )

    def test_3_copias_instaladas_declaram_licenca_da_raiz(self):
        """Copia canonica + perfis-alvo declaram a mesma licenca do LICENSE da raiz.

        Cobra a classe de defeito 'copia de perfil antiga': uma skill instalada
        antes da decisao F14 (ou restaurada de backup) voltaria a declarar
        `proprietary` no destino mesmo com o repo correto.
        """
        raiz = _identificador_licenca_raiz()
        destinos = [("canonica", HERMES_ROOT / "skills")] + [
            (f"perfil:{p}", HERMES_ROOT / "profiles" / p / "skills") for p in PERFIS
        ]
        problemas = []
        for d in _skills_do_repo():
            for rotulo, base in destinos:
                skmd = base / d.name / "SKILL.md"
                if not skmd.is_file():
                    problemas.append(f"{d.name}@{rotulo}: SKILL.md AUSENTE (redistribua)")
                    continue
                try:
                    declarada = _license_declarada(skmd)
                except ValueError as e:
                    problemas.append(f"{d.name}@{rotulo}: {e}")
                    continue
                if declarada != raiz:
                    problemas.append(
                        f"{d.name}@{rotulo}: license '{declarada}' != raiz '{raiz}'"
                        " (redistribua: bash scripts/install_skills.sh)"
                    )
        self.assertEqual(
            problemas, [],
            "copia instalada com licenca divergente:\n  " + "\n  ".join(problemas),
        )


if __name__ == "__main__":
    unittest.main()
