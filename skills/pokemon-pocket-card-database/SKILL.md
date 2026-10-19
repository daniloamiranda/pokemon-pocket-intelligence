---
name: pokemon-pocket-card-database
description: "Use ao consultar ou atualizar o catalogo de cartas do Pokemon TCG Pocket no SQLite canonico (data/pocket.sqlite): contagens globais, cobertura por conjunto, ficha de carta por nome/ID com impressoes/ataques/habilidades/evolucao, e atualizacao incremental via coletor Limitless — dry-run por padrao, rede apenas sob pedido explicito respeitando rate limit."
version: "1.0.0"
author: "tony_stark"
license: MIT
metadata:
  hermes:
    tags: [pokemon-pocket, catalog, database, sqlite]
    related_skills: [pokemon-pocket-rules, pokemon-pocket-card-vision, pokemon-pocket-meta-analyzer, pokemon-pocket-deck-builder, pokemon-pocket-deck-evaluator]
---

# Skill: card-database (catalogo + atualizacao de cartas)

Owner: tony_stark (CTO) · Card: t_24f07bbc (F13) · Risco: R2

## Responsabilidade

Ser a UNICA porta de entrada para o catalogo de cartas do projeto
(`data/pocket.sqlite`): consultar contagens, cobertura por conjunto e fichas de
carta; e comandar a ATUALIZACAO do catalogo pela ferramenta canonica
(`scripts/collect_pocket.py` + `scripts/db_migrate.py`), nunca reimplementando
coleta dentro da skill.

## Quando usar

- Pedidos tipo "quantas cartas tem no catalogo?", "qual a cobertura do conjunto
  B4b?", "qual a ficha do Mega Gengar ex?" -> MODO A (consulta).
- Pedidos tipo "atualiza o catalogo", "tem carta nova?" -> MODO B (atualizacao),
  SEMPRE com dry-run primeiro. Rede real apenas sob pedido explicito do
  operador (quota/cortesia com a fonte).

## MODO A — CONSULTA (sem rede; leitura `mode=ro`, nunca altera producao)

```bash
# contagens globais do catalogo
python3 scripts/db_query.py stats

# cobertura por conjunto (declarado pela fonte vs carregado)
python3 scripts/db_query.py coverage

# ficha de carta por nome (exato ou parcial) ou card_id canonico
python3 scripts/db_query.py card "Mega Gengar ex"
```

Saidas REAIS registradas no aceite F13 (2026-10-19, banco 24 conjuntos /
2.319 identidades / 4.317 impressoes):

`stats` ->
```json
{
  "database": "data/pocket.sqlite",
  "expansions": 24,
  "cards": 2319,
  "card_prints": 4317,
  "evolutions": 932,
  "validation_status": {"pending": 2319},
  "cards_by_category": {"pokemon": 2156, "trainer_supporter": 82, "trainer_item": 42, "pokemon_tool": 26, "trainer_stadium": 13}
}
```

`coverage` -> JSON com `per_set` (cada conjunto: `declared` da fonte,
`loaded` do banco, `coverage_pct`), `overall_pct`, `sets_with_gap`,
`sets_with_excess` (sobra da fonte, nao falha da coleta) e `promo_sets`
(sem contagem declarada pela fonte; fora do percentual por design).

`card` -> JSON com `status`, `card` (identidade MECANICA: `id`, `canonical_name`,
`category`, `element`, `stage`, `hp`, `is_ex`, `mechanical_hash`,
`validation_status`), `prints` (impressoes: `id`, `set_code`, `number`,
`rarity`, `is_promo`, `has_image_url`), `attacks` (`name`, `energy_cost`,
`damage`, `effect_text`), `abilities`, `evolves_from` e `evolves_to`.
Termo ambiguo -> `status: "ambiguo"` com `candidates` (nunca chuta).

## MODO B — ATUALIZACAO (dry-run por padrao; rede so sob pedido explicito)

```bash
# PASSO OBRIGATORIO 1: plano offline (zero rede, zero escrita)
python3 scripts/collect_pocket.py --dry-run

# PASSO OBRIGATORIO 2: estado das migracoes (schema em dia?)
python3 scripts/db_migrate.py --status

# (opcional) simulacao de migracao
python3 scripts/db_migrate.py --dry-run

# SO COM PEDIDO EXPLICITO DO OPERADOR: coleta real (1 req/1.2s, backoff em 429/5xx;
# POCKET_RATE_DELAY ajusta o intervalo — manter >= 1.2 por cortesia com a fonte)
python3 scripts/collect_pocket.py --sets A4a   # incremental: apenas o conjunto novo
python3 scripts/collect_pocket.py              # coleta completa (regenera o relatorio)
```

Saida REAL do `--dry-run` (aceite F13, banco 24/2319/4317): coleta completa
= `requisicoes_estimadas: 4144`, `duracao_estimada_min: 82.9` (rate 1.2s);
incremental `--sets A4a` = `131` reqs / `2.6` min. JSON com `mode: "dry-run"`,
`garantia: "nenhuma requisicao HTTP; nenhuma escrita (banco e relatorio
intocados)"`, `estado_atual` (contagens do banco), `sets_conhecidos`,
`o_que_faria` (fases da coleta), `rate_limit_s`, `idempotencia`
(INSERT OR IGNORE) e `aviso_aditivo` (coleta e ADITIVA: nao corrige print
fossilizado — ver Armadilhas). Promos/ausentes sem contagem declarada vem com
`"estimativa indisponivel"` — nunca inventa numero. Prova de zero escrita no
aceite: mtimes de `data/pocket.sqlite` e `data/collection_report.json`
IDENTICOS antes/depois de todas as invocacoes; `PRAGMA integrity_check = ok`.

Regra da casa: coleta PARCIAL (`--sets`) NAO altera
`data/collection_report.json` (regenerado apenas em coleta completa).

## Contratos (JSON Schema em `contracts/`, gerados por `scripts/gen_contracts.py`)

A skill EMITE (produtora canonica):

| Contrato | Conteudo (campos nomeados) | Consumidores |
|---|---|---|
| `card.json` | `cards`: `id` (`limitless:{set}/{num}`), `canonical_name`, `category`, `element`, `stage`, `hp`, `mechanical_hash`, `validation_status` | deck-builder, deck-evaluator, rules |
| `card_variant.json` | `card_prints`: `id`, `card_id`, `set_code`, `number`, `rarity`, `image_url` (URL, nunca bytes de arte) | card-vision |
| `expansion.json` | `expansions`: `code`, `name`, `series`, `release_date`, `card_count` | (proveniencia do catalogo) |
| `source.json` | `sources`: `id`, `name`, `base_url`, `kind`, `tier` (canonical) | meta-analyzer |
| `sync_job.json` | `sync_jobs`: `direction` (pull), `entity` (cards/card_prints), `status`, `items_changed` | meta-analyzer |

A skill CONSOME (nada de dado fora do contrato):

| De | Contrato | Uso |
|---|---|---|
| card-vision | `card` + `card_variant` | ficha confere com a observacao visual |
| deck-builder | `card` | resolucao de cartas por `card_id` do catalogo |
| meta-analyzer | `card` + `expansion` | rotulacao de arquetipos |
| rules | `card` | base de identidade para legalidade |

## Fontes

- Canonica (tier `canonical`): pocket.limitlesstcg.com — scrape respeitoso,
  rate limit 1.2s, User-Agent identificado, imagens NUNCA baixadas (so URL)
  (docs/SOURCES.md, docs/ATTRIBUTION.md).
- Cache persistente em `data/cache/pages` (nunca /tmp — secao 21 do escopo).

## Limites honestos

- `--only-list` do coletor e flag LEGADO SEM EFEITO (aceito por
  compatibilidade; nunca implementado). O modo seguro e `--dry-run`.
- Promos (P-A/P-B) sem contagem declarada pela fonte ficam fora do percentual
  de cobertura (note, nao gap).
- Coleta e ADITIVA: re-coletar NAO corrige registro fossilizado (ver abaixo).
- `db_query.py` abre o banco em `mode=ro` e NUNCA escreve; escrita so pela
  ferramenta canonica de coleta/migracao, com backup previo.
- Skill apenas no repo NAO e skill instalada (regra ARCSEC — instalacao via
  `scripts/install_skills.sh` e obrigatoria no aceite).

## Armadilhas que o projeto JA PAGOU CARO (nao repitam)

1. **Caminho unico do banco**: `data/pocket.sqlite` no repo. Nunca copia
   paralela, nunca banco em /tmp (dado operacional em caminho efemero e
   proibido — secao 21 do escopo).
2. **Print errado e PIOR que print ausente**: impressao apontada para identidade
   mecanica errada envenena downstream (F7c: 61 prints fantasma). Na duvida,
   declare ausencia; nunca adivinhe.
3. **Promos sem href nao se adivinham**: linha de versao promo (P-A#N) sem link
   na fonte NAO herda o numero homonimo do proprio set — parser pula (F7c).
4. **INSERT OR IGNORE fossiliza o primeiro dono**: a coleta idempotente e
   aditiva; se um print foi gravado com `card_id` errado, re-coletar NAO corrige
   — correcao exige re-parse auditado com trilha em `audit_logs` (F7c).
5. **Skill no repo != skill instalada**: toda mudanca aqui exige
   `bash scripts/install_skills.sh` + `--verify` rc=0 (hash unico) antes do
   aceite; guarda na suite (`tests/unit/test_f12_skills_guard.py`).

## Governanca

Risco R2. Consulta e somente-leitura por design (`mode=ro`). Atualizacao do
catalogo escreve apenas no banco do projeto via ferramenta canonica, com backup
previo (padrao: `data/pocket.sqlite.bak-<fase>-<n>`) e trilha em `audit_logs`
quando houver correcao manual. Coleta de rede real so com pedido explicito do
operador.
