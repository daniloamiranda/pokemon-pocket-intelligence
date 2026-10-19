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

- Copia canonica: `/home/hermes/.hermes/skills/<skill>/`
- Perfis-alvo (default): `tony_stark`, `hermione_granger`, `leia_organa`, `c3po`
  (sobrescreva com `PERFIS="a,b" bash scripts/install_skills.sh`)
- O script compara o **sha256 do SKILL.md** entre repo, copia canonica e perfis;
  qualquer divergencia = `exit 1` (instalacao parcial). Veredicto esperado no
  aceite: **"hash unico verificado: ok (readiness: available)"**.
- Para conferir que a skill esta carregavel de fato: `skill_view(nome_da_skill)`.

## 2. Catalogo (data/pocket.sqlite)

```bash
python3 scripts/collect_pocket.py         # coleta canonica a partir do Limitless
python3 scripts/db_migrate.py             # migra schema
```

## 2.5 Metagame (F7 — Limitless Developer API)

```bash
python3 scripts/meta/collect_meta.py            # coleta com checkpoint (data/meta/raw/)
python3 scripts/meta/meta_pipeline.py --days 30 # snapshot + tiers + relatorio
python3 scripts/meta/meta_pipeline.py --days 7  # janelas 7/14/30 coexistem
```

- Sem API key (escopo atual funciona dentro do rate limit 50/5min por header).
- Metodologia, regra de tiers S/A/B/C/D e politicas: docs/META.md +
  skill `pokemon-pocket-meta-analyzer`.
- Relatorios em data/meta/reports/ (fora do git); raw nunca apagado.

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
