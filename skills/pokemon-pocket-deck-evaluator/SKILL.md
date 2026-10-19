---
name: pokemon-pocket-deck-evaluator
description: "Use ao avaliar, comparar ou otimizar um deck do Pokemon TCG Pocket: nota heuristica 0-100 reprodutivel (pesos versionados em weights.json, 10 dimensoes), matchups contra os principais arquetipos do meta real com selo de evidencia real/teorico, comparacao com a analise do deck-builder F8 e recomendacoes de troca com beneficio e custo — persistindo em deck_evaluations. A nota NUNCA e winrate."
license: MIT
---

# Skill: deck-evaluator (nota heurística + matchups com evidência selada)

Owner: tony_stark (CTO) · Card: t_3afdfbcb · Risco: R2

## Objetivo
Avaliar QUALQUER deck (do builder F8 ou fornecido via spec JSON) com uma
nota REPRODUZÍVEL 0-100 e matchups contra os principais arquetipos do meta
real (F7), comparando o deck criado com o meta. Toda evidência carrega selo.

## Fontes (e o que cada uma resolve)
| Fonte | Papel |
|---|---|
| `cards`/`card_attacks`/`card_abilities`/`card_evolutions` | fichas REAIS: HP, dano real do ataque, custo real de energia, fraqueza, cadeia de evolução |
| `decks`/`deck_cards` (corpus F7) | núcleo empírico: presença real de cada pick no núcleo de listas que usam a carta principal |
| `meta_snapshots`/`meta_snapshot_archetypes`/`tiers` (F7) | meta real: top-N arquetipos por share, tier, win_rate, amostra |
| `matchups`/`tournament_matches` (F7) | matchup REAL por par de arquetipos (sample e confidence) |
| `scripts/validate_deck.py` (F3) | gate de legalidade — deck ilegal tem veredicto, não nota |
| `scripts/deck/build_deck.py` (F8) | funções mecânicas e núcleo empírico reutilizados (mesmo contrato) |

## Regras de honestidade (proibições do card)
1. **A nota NÃO é winrate**: `score_type=heuristic_quality_NOT_winrate` em
   toda saída. Nenhuma precisão estatística é atribuída ao modelo.
2. **Matchup selado**: `evidence.kind = real` (tem amostra da F7, com
   `sample_size` e `confidence` citados) ou `teorico` (fatores derivados de
   fichas REAIS: OHKO vs HP, sobrevivência vs dano adversário — cada fator
   citado, com nota SE torneio). Teórico JAMAIS é apresentado como resultado
   de torneio.
3. **Legalidade é gate**: o validador F3 roda sempre; ilegal → veredicto
   `ilegal`, sem nota, sem persistência, com recusa em audit_logs.
4. **Zero número inventado**: todos os fatores vêm de fichas/amostras reais;
   matchup sem amostra = teórico com fatores, não taxa "chutada" de 50/50.
5. **Popularidade ≠ desempenho**: share e win_rate ficam em campos distintos.

## Dimensões v1 (pesos em `weights.json` v f9-v1; mudou o arquivo, muda a nota)
| dimensão | peso | resumo (detalhes no arquivo) |
|---|---|---|
| legality | 0.10 | gate F3 |
| consistency | 0.14 | motor de mão + ônus de evolução + presença empírica |
| speed | 0.10 | dano ≥100 + custo de energia + aceleração |
| offensive_power | 0.13 | dano real vs HP real das principais dos top-N por share |
| resilience | 0.11 | HP real + proteção/cura + atacante de reserva − penalidade mega |
| energy_efficiency | 0.09 | custo real do ataque (tamanho/hibridismo) + mobilidade |
| flexibility | 0.08 | funções mecânicas distintas + busca + Supporter |
| recovery | 0.07 | atacante de reserva + cura + compra |
| combo_dependency | 0.08 | INVERTIDO: alto = baixa dependência de peças casadas |
| meta_coverage | 0.10 | matchup vs top-N ponderado por share (real/teórico selados) |

overall = Σ(score × peso), escala 0-100 (persistido como 0-10 em
`deck_evaluations.overall_score`, CHECK do schema).

## Matchups (como ler)
Cada entrada: arquetipo (id/tier/share/win_rate/amostra), mains resolvíveis
no catálogo, pontos fortes/fracos (cada frase cita ficha/amostra real),
cartas decisivas do deck para aquele confronto, condição de vitória,
`evidence` com selo e, quando real, o id do arquetipo análogo usado
(orientado ao lado do deck: win_rate invertido corretamente se o par está
gravado no lado oposto).

## Análogo do arquetipo
`find_analog` escolhe o arquetipo do snapshot cujo nome contém (ou é contido
pelo) nome da carta principal, preferindo com tier e maior amostra de jogos.
Sem análogo → todos os matchups são teóricos e confidence = `theoretical`.

## Trocas recomendadas
`swap_recommendations <= 3`: cartas do MESMO núcleo empírico (dia 20% de
presença real) com função mecânica aproveitável, para substituir o pick de
menor presença mesma classe de carta; cada recomendação traz beneficio E
custo declarado (com a presença real citada). Nunca sugere tirar a principal.

## Uso
```bash
# deck do builder F8
python3 scripts/eval/evaluate_deck.py --deck-id deck-mega-gengar-ex-003

# deck via spec JSON (bancada/terceiro)
python3 scripts/eval/evaluate_deck.py --spec /caminho/spec.json

# por nome FTS5 (usa o deck F8 principal)
python3 scripts/eval/evaluate_deck.py --name "Mega Gengar ex"

# snapshot/janela específicos
python3 scripts/eval/evaluate_deck.py --deck-id deck-hoopa-ex-001 --snapshot snap-7d-2026-10-19 --top 8

# sem persistir (inspeção)
... --no-persist
```

## Saída
JSON: veredicto; deck (lista com função mecânica e presença real); legality
(gate F3, satisfied_rules citados); score (overall + 10 dimensões com peso,
score, weighted e reason; versão dos pesos e caminho do arquivo); meta
(snapshot/janela/contagens); matchups (com selos); swap_recommendations;
comparison (análogo mais próximo + posicionamento honesto declarando que
heurística ≠ winrate); evidence (confidence: theoretical/low/medium/high);
disclaimers (3, obrigatórios); persistence (id em deck_evaluations).

## Persistência
- `deck_evaluations` — id determinístico `eval-{deck_id}-{snapshot_id}`
  (idempotente: re-avaliar não cria duplicata; overall persiste como 0-10).
- `evaluation_dimensions` — seeds das 10 dimensões (nome/peso/descrição).
- `audit_logs` — insert/update com reason citando weights.json.
- Relatórios: `data/eval/reports/eval-*.json` (fora do git, como os da F7).

## Antes de confiar nos números
- Sem análogo no meta OU sem amostra para o par → matchup TEÓRICO (selado).
- Amostra LOW num matchup real existe mas aproveita pouco (1-2 jogos).
- Comparação deck × meta é sempre pelo ANÁLOGO (id, nome, tier, win_rate
  citados) NUNCA pela nota heurística — ambos declarados como não comparáveis.
- Nota golden f9-v1 deck-mega-gengar-ex-003 = 70.1 (pós-F3b; o deck de referência
  era o deck-mega-gengar-ex-001 = 74.8 pós-F8b, removido com trilha audit_logs
  por violar EVOL-001 quando o validador passou a cobrir stage mega_ex —
  Mega Gengar ex sem Haunter no deck) — muda se o corpus crescer,
  outro snapshot for usado ou os pesos mudarem; cite a versão.
