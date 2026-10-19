---
name: pokemon-pocket-meta-analyzer
description: "Use ao analisar o metagame real do Pokemon TCG Pocket: coleta de torneios via Limitless Developer API, snapshots 7/14/30 dias, share/winrate/consistencia/matchup e tiers S/A/B/C/D com amostra citada e regra 'sem evidencia'."
license: MIT
---

# Skill: meta-analyzer (metagame real do Pocket)

Owner: tony_stark (CTO) · Card: t_04f33c18 · Risco: R2

## Objetivo
Medir o metagame REAL do Pokemon TCG Pocket a partir de dados de torneio da
Limitless Developer API e responder: o que esta jogando, o que esta GANHANDO,
contra o que, e com quanta confianca — com amostra citada em cada numero.

## Fonte e coleta

- Fonte-raiz: `https://play.limitlesstcg.com/api` (Developer API documentada em
  docs.limitlesstcg.com/developer; lida e provada em 2026-10-19). Endpoints:
  `GET /tournaments`, `/tournaments/{id}/details`, `/standings`, `/pairings`.
- **Nao exige API key** para este escopo (so `/games/{id}/decks`, nao usado).
  NAO pedir/chavear sem decisao do dono — o projeto e publico e a chave existe
  para projetos publicos (prever pedido, ver docs/META.md §7).
- Rate limit declarado POR HEADER (`RateLimit: "50-in-5min; r=N; t=S"`):
  respeitado com intervalo minimo 6.2s + espera do reset quando r<=1 +
  backoff exponencial em 429/5xx. Zero scraping de HTML (a API resolve —
  scraping e proibido enquanto a API resolver).
- Coletor: `python3 scripts/meta/collect_meta.py` (checkpoint por arquivo em
  `data/meta/raw/`; reexecucao PULA o que ja existe; nada em /tmp).
- Paginas/JSON brutos sao dados de terceiros: ficam em `data/` (fora do git,
  politica do .gitignore — igual ao catalogo).

## Escopo do snapshot (declarado, nunca implicito)

Torneios publicos de formato STANDARD com decklists obrigatorias, >= 8 players
e ao menos uma fase SWISS, com inicio >= 6h no passado (torneio em andamento
pode ter placing/standings parcial). NOEX e CUSTOM ficam FORA (a API tem os
dois; `format=null` em `/tournaments` e resolvido pelo `/details`).
Cada snapshot carrega o escopo completo no campo `scope`.
Por padrao o snapshot usa JANELA ROLANTE (7/14/30 dias fechando na data UTC
corrente — tendencia temporal). O modo `--full` ingere TODO o raw elegivel sem
corte de janela (snapshot `snap-full-<data>`); reconciliacao coleta x analise:
a coleta cobre 35 dias e a janela rolante de 30 chegou a deixar 41 elegiveis
fora do banco (defeito F7b, card t_7872dcac).

## Metricas (regra: popularidade NUNCA e apresentada como desempenho)

| Metrica | Definicao exata |
|---|---|
| `share_pct` | listas do arquetipo / listas totais da janela (POPULARIDADE) |
| `win_rate_pct` | (wins + 0.5·ties) / (wins+losses+ties) somando records dos players do arquetipo (DESEMPENHO) |
| `consistency_pct` | % dos torneios em que o arquetipo apareceu (>=1 lista) em que seu melhor record no torneio teve wins > losses |
| `matchups` | jogos reais do `/pairings`; fora da taxa: espelho, bye/ausente, empate (0), double loss (-1); confidence: high >= 200 jogos, medium >= 50, low < 50 do par |

Taxonomia de arquetipo: `deck.id`/`deck.name` atribuidos pela PROPRIA Limitless
(standings). O projeto nao inventa agrupamento.

## Tiers — regra F7 v1 (documentada; nao re-inventar por call)

- Gates de amostra (nao ha tier sem isso): >= 20 listas (MIN_DECKS) e >= 100
  jogos (MIN_MATCHES) na janela do snapshot.
- Faixas pelo win_rate da janela: **S >= 55.0 · A >= 52.0 · B >= 49.0 ·
  C >= 45.0 · D < 45.0**.
- Sem gates -> `tier = ''` (vazio) e `tier_basis` comecando com
  `sem_evidencia:` + a amostra exata (`N listas / M jogos`). **"Sem evidencia"
  e um RESULTADO, nao uma falha** — e o caso do Mega Gengar ex enquanto nao
  aparecer em torneios (amostra citada na saida).
- `F` nunca e emitido (reservado a falha de integridade de dados comprovada).
- Popularidade (share) e reportada separadamente do desempenho (tier).

## Uso

```bash
# 1) coletar (idempotente; checkpoint em data/meta/raw/)
python3 scripts/meta/collect_meta.py

# 2) snapshot da janela (7/14/30) + relatorio JSON em data/meta/reports/
python3 scripts/meta/meta_pipeline.py --days 30

# leitura de periodo especifica (relatorio pode ir a qualquer caminho DENTRO do projeto)
python3 scripts/meta/meta_pipeline.py --days 7 --report data/meta/reports/snap-7d-manual.json

# reconciliacao/ingestao completa (sem corte de janela; snapshot snap-full-<data>)
python3 scripts/meta/meta_pipeline.py --full
```

Saidas principais: tabelas `meta_snapshots`, `meta_snapshot_archetypes`,
`meta_archetypes` (com `tier`, `tier_basis`, `sample_decks`, `core_cards`),
`tiers`, `matchups` (com `sample_matches` e `confidence`), `tournaments`,
`decks`/`deck_cards` (listas reais de 20 cartas, join `set+number` ao catalogo),
`archetype_cards` (nucleo citavel para o deck-builder) e
`tournament_matches` (auditoria de jogos individuais).

## Validacao cruzada (regra do escopo)

Agregadores (pocket.untapped.gg, pokemontcgpocket.app, pocketmeta.app) sao
APENAS validacao cruzada, nunca fonte. NUNCA misturar estatisticas de fontes
diferentes sem normalizacao — comparacao direta entre amostras distintas e
proibida (FASE1 §5). O comparativo fica no relatorio como contexto, com
data/amostra/janela de cada fonte declaradas.

## Regras inegociaveis (da F7 do card)

- NAO inventar estatistica: todo numero sai do raw coletado e e tracavel
  (snapshot_id -> janela -> torneios -> listas/jogos).
- NAO apresentar popularidade como desempenho (share != winrate).
- NAO raspar HTML enquanto a API resolver.
- NAO pedir API key sem decisao do dono.
- Raw/snapshots nunca apagados (apend-only por janela; raw intocado).

## Documentacao completa

`docs/META.md` (metodologia, ADRs das decisões, operacao, backups).
