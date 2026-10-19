# Pokemon TCG Pocket Intelligence System

Plataforma permanente de inteligencia estrategica para **Pokemon TCG Pocket** (o jogo mobile da The Pokemon Company/DeNA), operada por agentes de IA sobre o Hermes Agent.

> Escopo estrito: **somente Pokemon TCG Pocket**. Nao cobre Pokemon TCG fisico, TCG Live nem TCG Online. Uma carta so entra no catalogo se existir oficialmente no Pocket.

## Como usar

A forma natural de pedir um deck e pelo nome da carta: **"Use o tcgp-deck-builder para criar um deck baseado na carta X"** — que na linha de comando vira o comando curto `bin/tcgp`, ponto unico de entrada de todo o fluxo (montar, validar, avaliar, consultar):

```bash
bin/tcgp "Mega Altaria ex"          # FLUXO COMPLETO: monta, valida, avalia e explica
```

| Comando | O que faz | Exemplo real |
|---|---|---|
| `tcgp <carta>` | **Fluxo completo**: monta o deck, valida legalidade, avalia contra o meta e imprime o "como funciona" | `bin/tcgp "Mega Altaria ex"` |
| `tcgp deck <carta>` | So monta o deck (gravando no catalogo; adicione `--copiar` para rodar numa copia, sem gravar) | `bin/tcgp deck "Mega Altaria ex" --copiar` |
| `tcgp eval <carta ou deck_id>` | So avalia: nota 0-100 **heuristica de qualidade (NAO e winrate)** + matchups | `bin/tcgp eval deck-mega-altaria-ex-001` |
| `tcgp meta [--top N]` | Panorama do meta: arquetipos, tier, share e win_rate de torneio com amostra | `bin/tcgp meta --top 3` |
| `tcgp cartas <busca>` | Consulta o catalogo (nome, elemento ou trecho de efeito) | `bin/tcgp cartas "Pikachu"` |
| `tcgp refresh --check` | Checa atualizacao das fontes oficiais (usa REDE; manual, nunca em runtime/cron) | `bin/tcgp refresh --check` |

O que cada saida significa:

- **`tcgp <carta>`**: lista de 20 cartas (uma linha por carta com o papel dela), o bloco
  "como funciona" gerado do que o deck realmente contem, a nota do avaliador
  (qualidade heuristica 0-100 — nao e winrate) e os top-5 matchups.
- **`tcgp meta`**: tier [S/A/B/C/D] pela regra F7, `share` = fatia das listas do snapshot,
  `win_rate` = do arquetipo em torneio (nao e previsao para o SEU deck), com amostra.
- **`tcgp cartas`**: impressoes no catalogo com id (ex.: `limitless:A1/94`) para usar
  em consultas exatas.
- **Saidas para agentes**: todo subcomando aceita `--json` (contrato estavel).
- **Codigos de saida**: `0` ok · `2` carta/deck inexistente · `3` montagem inconsistente
  ou refresh sem conexao · `4` ilegal ou falha de captura · `10` refresh detectou mudanca
  · `64` uso invalido · `127` dependencia ausente.

Passo a passo completo e exemplos colados da execucao real: `docs/USAGE.md`.
Sem dependencia nova (stdlib pura); o wrapper usa o `.venv` do projeto quando existe e
cai para o `python3` do sistema com aviso claro. Rode de qualquer diretorio — a raiz do
repo e resolvida a partir do proprio script.

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
