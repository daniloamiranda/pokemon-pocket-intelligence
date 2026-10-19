# Instalacao

## 1. Skills do projeto — INSTALAR APOS COMMIT (obrigatorio)

**Regra ARCSEC (defeito recorrente — F3 e F6):** skill que existe apenas em
`skills/<nome>/SKILL.md` **dentro do repositorio NAO e skill instalada**. O
`skill_view` do Hermes so carrega skills de `~/.hermes/skills/` ou
`~/.hermes/profiles/<perfil>/skills/`. Toda skill nova do projeto precisa passar
pelo script de instalacao no aceite da fase:

```bash
bash scripts/install_skills.sh            # instala na copia canonica + perfis-alvo
bash scripts/install_skills.sh --verify   # conferencia posterior: hash unico
```

- Copia canonica: `/home/hermes/.hermes/skills/<skill>/` — RAIZ FIXA (F12): o
  instalador NUNCA herda `HERMES_HOME` do shell (shell de agente aponta para o
  proprio perfil; herdar foi o que criou a arvore fantasma
  `profiles/<perfil>/profiles/` na era F7-F9). Override explicito apenas via
  `HERMES_ROOT_SKILLS` (fail-fast rc=3 se a raiz nao existir).
- Perfis-alvo (default): `tony_stark`, `hermione_granger`, `leia_organa`, `c3po`
  (sobrescreva com `PERFIS="a,b" bash scripts/install_skills.sh`)
- O script compara o **sha256 de TODA a arvore de arquivos** da skill (SKILL.md,
  `references/`, `weights.json`, etc.) entre repo, copia canonica e perfis
  (F12: antes era so o SKILL.md); qualquer divergencia — arquivo divergente,
  ausente ou EXTRA no destino — = `exit 1` (instalacao parcial). Veredicto
  esperado no aceite: **"hash unico verificado: ok (readiness: available)"**.
- Guarda na suite: `tests/unit/test_f12_skills_guard.py` reprova a suite se
  repo e instalacao divergirem (docs/TESTING.md secao 5). **Skill editada no
  repo exige redistribuicao + verify antes do aceite.**
- Guarda de licenca (F14): `tests/unit/test_f14_license_guard.py` compara o
  `license:` declarado em cada SKILL.md — no repo e nas copias instaladas —
  com o identificador do `LICENSE` da raiz (MIT); divergencia (ex.:
  `proprietary` voltando por copia de perfil antiga) reprova a suite
  (docs/TESTING.md secao 7). Skill nova nasce com `license: MIT`.
- Para conferir que a skill esta carregavel de fato: `skill_view(nome_da_skill)`.

## 2. Catalogo (data/pocket.sqlite)

```bash
python3 scripts/collect_pocket.py         # coleta canonica a partir do Limitless
python3 scripts/db_migrate.py             # migra schema
```

Skill responsavel (F13): `pokemon-pocket-card-database` — porta de entrada para
CONSULTA e ATUALIZACAO do catalogo:

```bash
# CONSULTA (sem rede, read-only):
python3 scripts/db_query.py stats                 # contagens globais
python3 scripts/db_query.py coverage              # cobertura por conjunto
python3 scripts/db_query.py card "Mega Gengar ex" # ficha + prints + evolucao

# ATUALIZACAO (dry-run por padrao — rede real so sob pedido explicito):
python3 scripts/collect_pocket.py --dry-run       # PLANO offline (zero rede/escrita)
python3 scripts/db_migrate.py --status            # estado do schema
python3 scripts/collect_pocket.py --sets A4a      # coleta incremental (pedido explicito)
python3 scripts/collect_pocket.py                 # coleta completa (regenera relatorio)
```

Obs.: `--only-list` e flag legado SEM EFEITO (aceito por compatibilidade). O
modo seguro e `--dry-run`; coleta parcial NAO altera `data/collection_report.json`.

## 3. Fixtures de visao (F6 — imagens de carta)

As imagens de carta sao **artes de terceiros (TPC/DeNA) e NAO sao versionadas**
no repositorio (politica `docs/ATTRIBUTION.md`: nao redistribuir arte). Baixe-as
sob demanda direto do CDN do Limitless:

```bash
python3 scripts/vision/fetch_fixtures.py            # baixa o que falta em tests/vision/
python3 scripts/vision/fetch_fixtures.py --list     # lista URLs sem baixar
```

Sem as fixtures, os testes de visao **pulam com motivo claro** (não falham);
os testes do RESOLVEDOR (`tests/unit/test_f6_card_vision.py`) rodam com o
catálogo presente e PULAM com motivo claro quando as fixtures de imagem não
estão no disco (o teste funciona sem imagem, mas a fixture é o insumo do
ground truth de observação — ver docstring do arquivo de teste).

## 4. Variaveis de ambiente / credenciais

Copie o gabarito `config/` e preencha fora do repositorio (`.env` nunca versionado).

## 5. Suite de testes e ambiente (TESTING.md)

A suite completa roda com `/opt/data/f5_venv/bin/python3 -m unittest
discover -s tests/unit -v` (63 testes OK). No python3 do sistema a suite
tambem e verde: os casos dependentes do SDK Composio (venv-only,
composio==0.22.0) PULAM com motivo explicito. Comando exato, revisao por
interprete e como recriar o venv: **docs/TESTING.md**.
