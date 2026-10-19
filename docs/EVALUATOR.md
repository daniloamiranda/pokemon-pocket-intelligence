# EVALUATOR.md — Metodologia do deck-evaluator (F9)

Projeto: pokemon-pocket-intelligence · Owner técnico: tony_stark (CTO)
Card: t_3afdfbcb · Risco: R2 · Criado: 2026-10-19

---

## 1. Princípio central

**A nota é HEURÍSTICA e REPRODUZÍVEL — não é winrate.** Ela mede qualidade
estimada do deck (10 dimensões com pesos versionados) a partir de fichas
REAIS do catálogo e amostras REAIS da F7. `score_type =
heuristic_quality_NOT_winrate` acompanha toda saída; nenhuma precisão
estatística é atribuída ao modelo (proibição do card).

## 2. Pipeline (determinístico, zero rede)

```
deck (--deck-id | --spec JSON | --name FTS5)
  → gate de legalidade (validador F3 — deck ilegal: veredicto, sem nota, sem persistência)
  → snapshot F7 (mais recente por window_end; ou --snapshot)
  → top-N arquetipos por share (default 12)
  → 10 dimensões (pesos em weights.json; cada score com reason citável)
  → matchups por arquetipo (análogo por nome/carta; EVIDÊNCIA selada)
  → trocas recomendadas (benefício e custo declarados)
  → persistência deck_evaluations + evaluation_dimensions + audit_logs
  → relatório data/eval/reports/
```

## 3. Pesos (aceitação 1 — nota reproduzível)

Arquivo único: `skills/pokemon-pocket-deck-evaluator/weights.json`
(`version: f9-v1`). Contrato: as 10 dimensões do escopo, soma dos pesos =
1.0 (validado em carga e na suíte); violação rejeita a execução por inteiro.
overall = Σ(score_dim × peso_dim), escala 0-100; persiste como 0-10
(`deck_evaluations.overall_score`, CHECK do schema 0001). Mudou o arquivo →
nova versão → a nota muda; a saída cita sempre `weights_version` e o caminho.

| dimensão | peso | insumos REAIS |
|---|---|---|
| legality | 0.10 | veredicto do validador F3 (regras citadas) |
| consistency | 0.14 | draw/search reais (quantidade), cadeia de evolução via `card_evolutions`, presença real das picks no núcleo de listas do corpus |
| speed | 0.10 | dano real (≥100/≥80/≥50), custo real de energias, Rare Candy/Wally, X Speed |
| offensive_power | 0.13 | dano real vs HP real das principais dos top-N por share (OHKO + razão; sem fraqueza — dano não simulado) |
| resilience | 0.11 | HP real, proteção/cura na lista, atacante de reserva (dano real), penalidade −15% quando a ficha real declara a regra Mega ex (3 pontos) |
| energy_efficiency | 0.09 | tamanho do custo real, híbrido de tipos (−0.15), X Speed/energy-accel |
| flexibility | 0.08 | funções mecânicas F8 distintas fora da principal, busca, Supporter |
| recovery | 0.07 | atacante de reserva, cura/proteção, densidade de compra |
| combo_dependency | 0.08 | INVERTIDO: alto = baixa dependência (cadeia curta/mitigada por candy/wally, busca ≥2) |
| meta_coverage | 0.10 | média ponderada por share dos scores de matchup contra top-N |

## 4. Matchups (aceitação 2 — selo real/teórico)

- **Análogo**: arquetipo do snapshot cujo nome contém (ou é contido pelo)
  nome da carta principal; prefere com tier e maior amostra de jogos. O id
  e o nome do análogo saem na evidência (transparência da aproximação).
- **REAL**: existe linha na tabela `matchups` da F7 para o par
  (análogo × adversário) na janela do snapshot. A taxa é orientada ao lado
  do deck (invertida quando o par está gravado do lado oposto). `sample_size`
  e `confidence` da F7 são citados SEMPRE — amostra LOW existe mas é fraca.
- **TEÓRICO**: sem amostra para o par. O score vem de fatores derivados de
  fichas REAIS (OHKO da principal vs HP das mains adversárias; sobrevivência
  da principal vs melhor dano adversário real), cada fator citado, com nota
  "não é resultado de torneio". NUNCA apresentado como estatística.
- Sem análogo nenhum → confidence geral `theoretical`.
- Cada entrada traz: mains resolvíveis no catálogo, pontos fortes/fracos
  (frases citando ficha/amostra), cartas decisivas do deck, condição de
  vitória e score 0-1 do confronto (peso na dimensão meta_coverage).

## 5. Comparação com o meta real (aceitação 3)

O relatório compara o deck avaliado com o meta pelos dados do banco:
análogo mais próximo (id/nome/tier/win_rate/amostra), cartas compartilhadas
com os top-12 por share, e `positioning` que DECLARA que nota heurística e
winrate de torneio não são comparáveis. O deck F8 Mega Gengar ex
(deck-mega-gengar-ex-003, lista regenerada pós-F8b com linha de evolução
completa) avaliado contra snap-full-2026-10-19 (123 torneios): 70,1/100
(f9-v1), análogo Hoopa ex Mega Gengar ex (sem_evidencia), 6 matchups com
amostra REAL (1-3 jogos, confidence low) e 6 TEÓRICOS selados.

## 6. Trocas recomendadas

Máximo 3; só entre cartas com presença real no núcleo (≥20% das listas com
a principal), mesma classe de carta na troca, função mecânica aproveitável;
benefício E custo declarados com a presença real citada (ex.: "ganha
proteção/cura; perde Sabrina, presente em 62% do núcleo"). Nunca sugere
remover a carta principal. Sem candidato honesto → lista vazia (nada forçado).

## 7. Persistência (aceitação 4)

- `deck_evaluations` — PK determinística `eval-{deck_id}-{snapshot_id}`;
  re-execução é idempotente (upsert com audit_logs de action update;
  overall_score igual). CHECKs do schema (0-10; confidence
  theoretical/low/medium/high) respeitados.
- `evaluation_dimensions` — seeds das 10 dimensões (nome, peso default,
  descrição; UPSERT).
- `audit_logs` — toda avaliação gravada com reason citando weights.json e
  a advertência de não-winrate; recusas de deck ilegal também são gravadas.
- Relatórios JSON em `data/eval/reports/` (fora do git, política data/).

## 8. Operação

```bash
python3 scripts/eval/evaluate_deck.py --deck-id deck-mega-gengar-ex-003
python3 scripts/eval/evaluate_deck.py --spec caminho/spec.json
python3 scripts/eval/evaluate_deck.py --name "Mega Gengar ex"
python3 scripts/eval/evaluate_deck.py --deck-id deck-hoopa-ex-001 --snapshot snap-7d-2026-10-19 --top 8
python3 scripts/eval/evaluate_deck.py --deck-id deck-mega-gengar-ex-003 --no-persist
python3 -m unittest tests.unit.test_f9_deck_evaluator -v
```

## 9. Limitações (honestidade estatística)

1. Dimensões são proxies heurísticos (v1) — calibração só melhora com
   também o gate de QA F10 (Hermione) e feedback real de jogos.
2. Análogo por nome pode aproximar demais (ex.: deck F8 "Mega Gengar ex +
   Hoopa ex" mapeia para Hoopa-Mega-Gengar) — a saída declara o análogo.
3. Matchups reais da janela full têm amostras BAIXAS para arquetipos raros
   (1-3 jogos): o selo existe para NÃO esconder isso.
4. Janela empírica (days) opera sobre `collected_at` do corpus (ingestão
   2026-10-19) — com o corpus de 1 dia, as janelas 30/7/dias caem todas no
   mesmo conjunto (comportamento igual ao F8, declarado).
5. A nota muda quando o snapshot/corpus/pesos mudam — reproducibilidade é
   por (deck, snapshot, versão de pesos), não eterna.

## 10. Trilha de evidência (aceite F9)

- Golden: deck-mega-gengar-ex-003 × snap-full-2026-10-19 = 70.1/100
  (f9-v1; pós-F3b — o deck de referência era o deck-mega-gengar-ex-001 = 74.8,
  que por sua vez era 74.9 antes da F8b excluir decks gerados `deck-%` do
  núcleo; o -001 foi removido com trilha audit_logs por violar EVOL-001 com
  o stage mega_ex coberto), reproduzido pela suíte, 2 intérpretes
  (3.12.13 e 3.13.5).
- Matchup real citado: par hoopa-ex-b4-mega-gengar-ex-b2b ×
  mega-altaria-ex-b1-espeon-b3a (window 2026-09-09..2026-10-19, 2 jogos)
  conferido linha a linha entre a saída e a tabela `matchups` (teste).
- Persistência idempotente provada em teste (2 execuções = 1 linha, mesmo
  overall) — e rastros de teste foram limpos do banco de produção
  (audit+evals zerados antes da persistência oficial via CLI, commit F9).
