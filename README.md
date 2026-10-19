# Pokemon TCG Pocket Intelligence System

Plataforma permanente de inteligencia estrategica para **Pokemon TCG Pocket** (o jogo mobile da The Pokemon Company/DeNA), operada por agentes de IA sobre o Hermes Agent.

> Escopo estrito: **somente Pokemon TCG Pocket**. Nao cobre Pokemon TCG fisico, TCG Live nem TCG Online. Uma carta so entra no catalogo se existir oficialmente no Pocket.

## O que o sistema faz

1. Conhece as regras oficiais do Pocket e valida legalidade de decks.
2. Mantem um catalogo completo de cartas, com atualizacao incremental.
3. Reconhece cartas por imagem (screenshot/foto).
4. Constroi decks legais e competitivos a partir de uma carta principal.
5. Analisa o metagame com dados reais de torneio e atribui tiers com metodologia.
6. Avalia e compara decks (consistencia, velocidade, matchups).

## Arquitetura

- **SQLite** = fonte canonica (WAL, foreign_keys, FTS5, Application-ID 1).
- **Google Sheets** = interface de visualizacao/auditoria, via Composio.
- **Skills modulares** (rules, card-vision, meta-analyzer, deck-builder) + orquestracao, com contratos JSON versionados entre elas.

Status atual: **Fase 2 em execucao — F2 (arquitetura) ate F9 (deck-evaluator) entregues com suite verde; F10 (homologacao independente de QA) pendente.** Ver `docs/PLAN.md`, `docs/DECK.md` e `docs/EVALUATOR.md`.

## Fontes de dados

- Cartas: Limitless TCG Pocket Database (`pocket.limitlesstcg.com`).
- Torneios/metagame: Limitless Developer API (`play.limitlesstcg.com/api`).
- Validacao cruzada: agregadores que derivam do Limitless (nunca misturados sem normalizacao).
- Cartas e imagens: (c) The Pokemon Company / DeNA / Creatures. Ver `docs/ATTRIBUTION.md`.

Este projeto nao e produzido, endossado ou afiliado a The Pokemon Company, DeNA ou Creatures.

## Instalacao rapida

```bash
bash scripts/install_skills.sh                # skills -> copia canonica + perfis (hash unico)
python3 scripts/collect_pocket.py && python3 scripts/db_migrate.py   # catalogo
python3 scripts/vision/fetch_fixtures.py      # fixtures de visao (nao versionadas)
python3 scripts/meta/collect_meta.py          # coleta de torneios (metagame, F7)
python3 scripts/meta/meta_pipeline.py --days 30   # snapshot + tiers (docs/META.md)
python3 scripts/deck/build_deck.py "Mega Gengar ex"   # deck builder F8 (docs/DECK.md)
python3 scripts/eval/evaluate_deck.py --deck-id deck-mega-gengar-ex-001  # evaluator F9 (docs/EVALUATOR.md)
```

Detalhes em `INSTALLATION.md` e `docs/USER_GUIDE.md`. Regra de ouro: skill que so existe dentro do repo NAO e skill instalada — rode o script acima (defeito recorrente: F3, F6).

## Licenca

- **Codigo** (scripts, tests e skills deste repositorio): licenca **MIT** — ver o arquivo `LICENSE` na raiz.
- **Dados** derivados de fontes de terceiros (Limitless TCG Pocket Database e Limitless Developer API;
  cartas (c) The Pokemon Company / DeNA / Creatures) permanecem sob os termos dos respectivos donos e
  **NAO sao redistribuidos** neste repositorio.
- **Arte de cartas** nunca e versionada no repositorio (politica em `docs/ATTRIBUTION.md`).
