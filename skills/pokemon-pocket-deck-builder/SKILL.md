---
name: pokemon-pocket-deck-builder
description: "Use ao construir um deck legal de 20 cartas a partir de uma carta principal: nucleo empirico das listas de torneio reais coletadas pela F7, sinergias com funcao mecanica declarada (compra/busca/evolucao/protecao/cura/controle/mobilidade/resposta ao meta), plano de energia e como-jogar derivados da ficha real — sempre validado pelo validador F3 antes de persistir."
license: MIT
---

# Skill: deck-builder (sinergias mecanicas + lista legal do Pocket)

Owner: tony_stark (CTO) · Card: t_89d318e2 · Risco: R2

## Objetivo
A partir de UMA carta principal, montar uma lista de 20 cartas LEGAL
(validador F3) com justificativa MECANICA por carta incluida — nunca
"compartilha tipo". O nucleo vem das listas REAIS de torneio do corpus F7.

## Fontes (e o que cada uma resolve)
| Fonte | Papel |
|---|---|
| `cards`/`card_attacks`/`card_abilities`/`card_evolutions` (SQLite canonico) | ficha REAL: nome, elemento, stage, HP, ataque (nome/custo/dano/efeito), habilidade, prerq. de evolucao |
| `decks`/`deck_cards` (corpus F7 — 4.865 listas de torneio, fonte `play.limitlesstcg.com`) | nucleo empirico: quais cartas acompanham a principal em listas que GANHARAM espaco no meta |
| `data/cache/pages` (cache F4 de pocket.limitlesstcg.com) | texto real de Trainer/Tool (re-parse offline; se a ficha nao esta em cache, o texto fica vazio — nunca inventado) |
| `meta_snapshots`/`meta_snapshot_archetypes`/`tiers` (snapshot 30d da F7) |oola analise competitiva: arquétipos com a carta, tier, share, win_rate, amostra |
| validador `scripts/validate_deck.py` (F3) | legalidade — DECK-001..REST-001, EVOL-001/002 |

## Regras do builder (F8 v1)
1. **Carta principal SEMPRE na lista** (proibição do card) — 2 cópias.
2. **Zero carta inventada**: todo pick é resolvido no `cards` por card_id.
3. **Função mecânica por regra nomeada** sobre a ficha real (nada por tipo
   compartilhado): draw/search/evolution/protection/heal/control/mobility/
   meta-response/energy-accel/core-companion/main-card.
4. **Evolução**: pré-requisitos via `card_evolutions`, reservados na MESMA
   iteração (EVOL-001 satisfeito na montagem, re-checado pelo F3).
   F8b: a linha da carta PRINCIPAL é reservada ANTES do núcleo empírico e
   a identidade do pré é escolhida por NOME + elemento da linha principal
   (`pick_pre_identity`) — nunca mistura tipos na mesma linha de evolução
   (ex: Gastly psíquico A1/120 numa linha sombria abre tipo na Energy Zone).
5. **Energia NÃO entra na lista**: nas 4.865 listas reais do corpus não há
   UMA carta de energia (Pocket commita energia por partida). O PLANO de
   energia é texto de saída derivado do custo real do ataque principal.
6. **Persistência**: toda lista gera `deck-{slug}-{n}` em `decks` (FK real,
   total=20) + `deck_cards` (print_id NULL; quantity 1..2) +
   `deck_specifications` (JSON completo; migration 0004, FK CASCADE).
   F8b: decks gerados (`deck-%`) ficam FORA do núcleo empírico de builds
   futuros (a saída do motor não é evidência de si mesma) e a lista é
   montada com agregação por NOME (máx 2 por nome — DECK-002).
7. **Veredicto por amostra**: `valido` (nucleo >= 12 listas reais na janela) |
   `fallback` (menos que isso) | `sem_evidencia`/`inconsistente`/`ilegal`
   quando a montagem nao fecha 20/20 ou reprova o F3 — nunca persiste ilegal.

## Uso
**Caminho oficial (UX-2, card t_2d795bb4): comando curto `bin/tcgp`** — ponto
unico de entrada que orquestra builder + validador + evaluator + meta:
```bash
# FLUXO COMPLETO: monta, valida, avalia e explica "como funciona"
bin/tcgp "Mega Gengar ex"

# so montar (gravando no canonico) ou numa copia do banco (sem gravar)
bin/tcgp deck "Mega Gengar ex"
bin/tcgp deck "Mega Gengar ex" --copiar

# so avaliar (nota heuristica + matchups; NAO e winrate; leitura pura)
bin/tcgp eval deck-mega-gengar-ex-001
bin/tcgp eval "Mega Gengar ex" --json
```
Guia do usuario: `docs/USAGE.md` (saidas reais coladas). Os comandos diretos
abaixo continuam validos para quem opera os motores isoladamente:

```bash
# deck a partir do nome (FTS5) — relatorio humano (uma linha por carta)
python3 scripts/deck/build_deck.py "Mega Gengar ex"

# saida JSON para agentes/consumidores (formato estavel + card_lines)
python3 scripts/deck/build_deck.py "Mega Gengar ex" --json

# deck a partir do card_id exato
python3 scripts/deck/build_deck.py --card-id limitless:B2b/39

# outras janelas empiricas
python3 scripts/deck/build_deck.py "Hoopa ex" --days 7

# quais cartas principais sao suportadas (>= 3 listas reais na janela)
python3 scripts/deck/build_deck.py --list-mains
```

## Saida (formato UX-1, card t_bd7c1cc1)
PADRAO (sem flag): relatorio humano — uma linha por carta distinta com
NOME+quantidade a esquerda e papel a direita ("2x Professor's Research —
Acelerar o jogo (comprar cartas)"), seguido do bloco "como funciona" (2-4
linhas geradas do que o deck REALMENTE contem: linha de evolucao presente,
ataque real da principal, motores, apoio e plano de energia; zero carta
fantasma — a guia que citasse carta ausente reprova a guarda da suite,
caso Gastly no deck do Mega Altaria ex).

--json: formato estavel do F8 (veredicto/confidence/empirical_decks/
window_days; legality + satisfied_rules; main_card; cards[] com
quantity/function/reason; energy_plan; how_to_play; competitive_analysis;
sources) + `card_lines[]` ADITIVO — cada entrada com card_id, name,
quantity, role, role_origin (curated | derived_text | neutral |
uncataloged), role_evidence e source (origem do papel citada por linha).

Fonte do papel (anti-invencao): Pokemon = effect_text real da ficha mapeado
por vocabulario fechado (scripts/deck/card_roles.py); treinadores/ferramentas/
estadios = tabela curada data/card_roles.yaml (text_evidence transcrito do
cache F4 e vigiado pela suite); sem casamento = rotulo neutro do vocabulario
ou "Papel nao catalogado" explicito — jamais texto inventado.

## Antes de confiar nos números
- Amostra empírica < 12 listas → veredicto `fallback`: a LISTA é legal, a
  CLAIM de meta é fraca (declarado, never hidden).
- popularidade (share) ≠ desempenho (tier) — como na F7.
- Papel de Trainer/Tool fora da tabela curada aparece como "Papel nao
  catalogado" (declarado, nunca inventado) — complete data/card_roles.yaml
  com text_evidence real do cache F4.
- Nothing about Gengar is fake: 12 listas reais de Mega Gengar ex existem no
  corpus e a amostra é citada em cada número do output.
