# USAGE · Guia de uso do `tcgp` (comando curto, UX-2)

`bin/tcgp` e o ponto unico de entrada: uma chamada chama todo o fluxo de
geracao de decks, avaliacao contra o meta e consulta ao catalogo. Tudo aqui
foi EXECUTADO de verdade — as saidas abaixo estao coladas da execucao real
(snapshot `snap-full-2026-10-19`, corpus de 8.622 listas de torneio).
Card de origem: t_2d795bb4 · guardas em `tests/unit/test_ux2_tcgp.py`.

## Requisitos

- Nenhuma dependencia nova: o `tcgp` e Python puro (stdlib) e usa o `.venv`
  do projeto quando existe; sem venv, cai para o `python3` do sistema com um
  aviso claro.
- Rode de QUALQUER diretorio: o caminho do repo e resolvido a partir do
  proprio script (nunca voce digita caminho absoluto).
- O catalogo precisa existir (`data/pocket.sqlite`). Em checkout cru, popule
  antes: `python3 scripts/collect_pocket.py` (ver `INSTALLATION.md`).

## Passo a passo

### 1. Panorama do meta — `tcgp meta`

Antes de montar deck, veja com o que voce vai competir:

```console
$ bin/tcgp meta --top 3
Meta — snapshot snap-full-2026-10-19 (janela 2026-09-09..2026-10-19, 123 torneios, 8622 listas)
share = fatia das listas do snapshot; win_rate = do ARQUETIPO em torneio (nao e previsao para o SEU deck); tier = regra F7 v1.

  [B] Mega Altaria ex Espeon       share  9.26%  win_rate  51.8%  (798 listas, 4817 jogos)
  [C] Mega Lucario ex Lucario      share  7.11%  win_rate  45.9%  (613 listas, 3357 jogos)
  [B] Butterfree Mega Sceptile ex  share  5.01%  win_rate  50.1%  (432 listas, 2453 jogos)
```

Leitura: `tier` [S/A/B/C/D] vem da regra F7 (gates >= 20 listas e >= 100 jogos),
`share` e a fatia do snapshot e `win_rate` e do ARQUETIPO em torneio — nao e
previsao para o deck que voce vai montar.

### 2. Consultar o catalogo — `tcgp cartas`

Nome, elemento (ex.: `water`, `psychic`) ou trecho de efeito:

```console
$ bin/tcgp cartas "Pikachu"
11 carta(s) para 'Pikachu' (ate 40):
  limitless:A1/94        Pikachu                      [pokemon/lightning] 60 HP
  limitless:A1a/25       Pikachu                      [pokemon/lightning] 60 HP
  limitless:A2a/25       Pikachu                      [pokemon/lightning] 60 HP
  limitless:A3/57        Pikachu                      [pokemon/lightning] 60 HP
  limitless:B2/49        Pikachu                      [pokemon/lightning] 60 HP
  limitless:B2b/22       Pikachu                      [pokemon/lightning] 70 HP
  limitless:B3b/21       Pikachu                      [pokemon/lightning] 60 HP
  limitless:B4/49        Pikachu                      [pokemon/lightning] 60 HP
  limitless:P-A/111      Pikachu                      [pokemon/lightning] 60 HP
  limitless:A1/96        Pikachu ex                   [pokemon/lightning] 120 HP
  limitless:A2b/22       Pikachu ex                   [pokemon/lightning] 120 HP
```

O id (`limitless:A1/94`) serve para consultas exatas (`tcgp deck --card-id`).

### 3. Montar o deck — `tcgp deck`

So o builder: monta a lista de 20, valida legalidade (F3) e grava no catalogo
com `deck_id` proprio. Com `--copiar`, roda numa COPIA do banco e nao grava
nada (ver secao "Canonico x copia"):

```console
$ bin/tcgp deck "Mega Altaria ex" --copiar
=== deck-mega-altaria-ex-004 · Mega Altaria ex — build F8 ===
2x Mega Altaria ex (psychic, 190 HP, mega_ex) — Atacante principal; evolui de Swablu
2x Swablu                                     — Atacante de dano direto
2x Professor's Research                       — Acelerar o jogo (comprar cartas)
2x Copycat                                    — Compra de cartas
2x Poké Ball                                  — Busca no deck
2x Training Area                              — Estádio de apoio
2x Sabrina                                    — Pressão de troca e captura
2x Small Balloon                              — Diminuir custo de retorno
2x Darkrai                                    — Controle por sono
2x Igglybuff                                  — Controle por sono
-- como funciona --
Abra com Swablu no ativo e evolua para Mega Altaria ex (turno 2+); o ataque Mega Harmony ganha +30 por Pokémon no seu banco — encha o banco antes de atacar — núcleo calibrado em 1338 lista(s) real(is) do corpus.
Motor de cartas: Professor's Research — Acelerar o jogo (comprar cartas); Copycat — Compra de cartas; Poké Ball — Busca no deck.
Apoio: Swablu — Atacante de dano direto; Training Area — Estádio de apoio; Sabrina — Pressão de troca e captura; Small Balloon — Diminuir custo de retorno; Darkrai — Controle por sono; Igglybuff — Controle por sono.
Energia: Mega Harmony pede Psíquico, Psíquico — commit por partida; energia não entra na lista de 20.
```

Energia nao entra na lista (regra do Pocket: commit por partida) — o plano de
energia e texto derivado do custo real do ataque.

### 4. Avaliar — `tcgp eval`

Aceita carta (usa o deck F8 canonico dela: `deck-<slug>-001`) ou `deck_id`
(a montagem exata que voce quer). **A nota 0-100 e qualidade heuristica —
NAO e winrate e nao previu resultado de torneio** (o proprio JSON carrega
`score_type: heuristic_quality_NOT_winrate`):

```console
$ bin/tcgp eval deck-mega-altaria-ex-001
[tcgp eval: leitura pura — nada gravado no banco canonico; a nota 0-100 e heuristica e NAO e winrate.]
{
  "veredicto": "avaliado",
  "deck": {
    "id": "deck-mega-altaria-ex-001",
    "name": "Mega Altaria ex — build F8",
    "total_cards": 20,
    "main_card": "Mega Altaria ex",
    ...
  },
  "legality": { "legal": true, "violations": [], ... },
  "score": {
    "overall": 60.3,
    "scale": "0-100",
    "score_type": "heuristic_quality_NOT_winrate",
    ...
  },
  "meta": { "snapshot_id": "snap-full-2026-10-19", "window": "2026-09-09..2026-10-19",
            "tournament_count": 123, "decklist_count": 8622, "match_count": 24984, ... },
  "matchups": [ ... 12 arquetipos, cada um com evidencia "real" (amostra de torneio)
                  ou "teorico" (ficha real SEM amostra — nunca apresentado como torneio) ... ],
  "disclaimers": [
    "A nota 0-100 é QUALIDADE HEURÍSTICA (score_type=heuristic_quality_NOT_winrate); NÃO é winrate ...",
    ...
  ]
}
```

O que existe de "eficiencia em torneio" aqui e o campo `comparison`:
o análogo real do meta que compartilha a carta principal, com o win_rate DELE
e o aviso de que nota heuristica e winrate sao numeros NAO comparaveis.
Matchups marcados `kind: teorico` derivam de fichas reais sem amostra de par.

### 5. Fluxo completo — `tcgp <carta>`

Uma chamada faz tudo: monta, valida, avalia e explica:

```console
$ bin/tcgp "Mega Altaria ex"
=== deck-mega-altaria-ex-004 · Mega Altaria ex — fluxo completo tcgp ===
2x Mega Altaria ex (psychic, 190 HP, mega_ex) — Atacante principal; evolui de Swablu
2x Swablu                                     — Atacante de dano direto
2x Professor's Research                       — Acelerar o jogo (comprar cartas)
2x Copycat                                    — Compra de cartas
2x Poké Ball                                  — Busca no deck
2x Training Area                              — Estádio de apoio
2x Sabrina                                    — Pressão de troca e captura
2x Small Balloon                              — Diminuir custo de retorno
2x Darkrai                                    — Controle por sono
2x Igglybuff                                  — Controle por sono
-- como funciona --
Abra com Swablu no ativo e evolua para Mega Altaria ex (turno 2+); o ataque Mega Harmony ganha +30 por Pokémon no seu banco — encha o banco antes de atacar — núcleo calibrado em 1338 lista(s) real(is) do corpus.
Motor de cartas: Professor's Research — Acelerar o jogo (comprar cartas); Copycat — Compra de cartas; Poké Ball — Busca no deck.
Apoio: Swablu — Atacante de dano direto; Training Area — Estádio de apoio; Sabrina — Pressão de troca e captura; Small Balloon — Diminuir custo de retorno; Darkrai — Controle por sono; Igglybuff — Controle por sono.
Energia: Mega Harmony pede Psíquico, Psíquico — commit por partida; energia não entra na lista de 20.

Nota do avaliador (QUALIDADE HEURISTICA 0-100 — NAO e winrate):
  59.9/100 (confianca low)

Matchups (top 5 do relatorio completo; ver --json para evidencia):
  - Mega Altaria ex Espeon [tier B]: score 0.0 (evidencia: real)
  - Mega Lucario ex Lucario [tier C]: score 1.0 (evidencia: real)
  - Butterfree Mega Sceptile ex [tier B]: score 0.0 (evidencia: teorico)
  - Dragonair Mega Rayquaza ex [tier A]: score 0.0 (evidencia: real)
  - Suicune ex Baxcalibur [tier B]: score 0.5 (evidencia: real)
```

Sem `--copiar`, o fluxo completo grava a montagem no catalogo canonico (com
`deck_id` novo — padrao F8) e avalia SEM gravar nota. Com `--copiar`, nada e
gravado em lugar nenhum (prova md5 na secao abaixo). Para agentes, o mesmo
fluxo em JSON com o relatorio do evaluator aninhado:

```console
$ bin/tcgp "Mega Altaria ex" --copiar --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d)); print(sorted(d['evaluation']))"
['card_lines', 'cards', 'competitive_analysis', 'confidence_level', 'deck_id', 'empirical_decks', 'energy_plan', 'evaluation', 'how_to_play', 'legality', 'main_card', 'satisfied_rules', 'sources', 'veredicto', 'window_days']
['comparison', 'deck', 'disclaimers', 'evidence', 'generated_at', 'legality', 'matchups', 'meta', 'score', 'sources', 'swap_recommendations', 'veredicto']
```

### 6. Atualizar as fontes oficiais — `tcgp refresh --check` (MANUAL)

Unico subcomando que usa REDE (captura das FAQs oficiais via Firecrawl,
modo manutencao — NUNCA em runtime, nunca cron). Saida real de 19/10/2026:

```console
$ bin/tcgp refresh --check
[tcgp refresh] ATENCAO: rede real via Firecrawl/Composio (modo manutencao). Isto NAO roda em runtime nem cron.
# rules_refresh — relatorio 2026-10-19T18:37:43Z

## Fonte: faq-gameplay
- URL: https://support.pokemon.com/hc/en-us/articles/30330309361172-Pokemon-TCG-Pocket-Gameplay-FAQ
- RESULTADO: sem mudanca.
- Captura atual: sha256=6b2615d1cf57a16317ec43beb514a90e56ecb19f4c1d6fc12ce6b976e01af371 (17456 bytes, metodo firecrawl)

## Fonte: faq-battle
- URL: https://support.pokemon.com/hc/en-us/articles/38906248102292-Pokemon-TCG-Pocket-Battle-Rules-FAQ
- RESULTADO: sem mudanca.
- Captura atual: sha256=41eeab87e6164a7a7636469088a414a8cc987bff9ae17d59de14bc43b2bad1d4 (4518 bytes, metodo firecrawl)
```

Se o SDK Composio nao estiver no interpretador padrao, aponte o venv dele:
`TCGP_REFRESH_PYTHON=/caminho/com/composio/bin/python bin/tcgp refresh --check`.

## Canonico x copia (o que grava o que)

| Comando | Escreve no catalogo canonico? |
|---|---|
| `tcgp deck <carta>` | SIM — grava `deck-<slug>-<n>` (padrao F8; decks gerados ficam fora do nucleo empirico de builds futuros) |
| `tcgp deck <carta> --copiar` | NAO — roda numa copia (backup API do SQLite); o deck e criado so nela |
| `tcgp eval <alvo>` | NAO — leitura pura (o motor F9 recusa escrita automatica em producao: BUG-002/F15) |
| `tcgp <carta>` | So o builder grava o deck; a avaliacao nunca grava |
| `tcgp <carta> --copiar` | NAO — builder e evaluator rodam na copia, copia apagada no fim |
| `tcgp meta` / `tcgp cartas` | NAO — leitura pura (`mode=ro`) |
| `tcgp refresh --check` | So os snapshots de regras (`data/rules_snapshots/`), quando a fonte muda; nunca o catalogo |

Prova de nao-gravacao (suite UX-2, `test_04`/`test_05`): md5 de
`data/pocket.sqlite` antes e depois de `tcgp deck "Mega Altaria ex" --copiar`
e do fluxo completo `--copiar` — identicos
(`ad0effc642f9141432109ea98a0bf447` na sessao de captura).

## Codigos de saida

| rc | Significado |
|---|---|
| 0 | ok |
| 2 | carta/deck inexistente (builder/evaluator) |
| 3 | montagem inconsistente (builder) ou sem conexao (refresh) |
| 4 | deck ilegal (builder) ou falha de captura (refresh) |
| 10 | refresh: fonte oficial mudou (snapshot atualizado, RULES.md intocado) |
| 64 | uso invalido do tcgp (sem carta, `--top` nao-numerico, refresh sem `--check`) |
| 127 | dependencia/raiz ausente (banco inexistente, script fora do repo) |

## Para agentes (modo `--json`)

Todo subcomando aceita `--json`. O fluxo completo devolve o contrato F8 do
builder (15 chaves, incluindo `card_lines[]` do UX-1) + a chave aditiva
`evaluation` com o relatorio F9 completo. Erros maquina-legiveis:
carta inexistente imprime `{"veredicto": "carta_inexistente", ...}` e sai
com rc=2. Execucao real:

```console
$ bin/tcgp "Carta Que Nao Existe XYZ"
{
  "veredicto": "carta_inexistente",
  "query": "Carta Que Nao Existe XYZ",
  "reason": "nem card_id nem nome canônico resolvem no catálogo"
}
$ echo $?
2
```
