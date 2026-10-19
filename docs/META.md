# META.md — Metodologia do meta-analyzer (F7)

Projeto: pokemon-pocket-intelligence · Owner técnico: tony_stark (CTO)
Cards: t_04f33c18 (F7) · t_7872dcac (F7b) · Risco: R2 · Criado: 2026-10-19 (dados coletados 2026-10-19)

---

## 1. Fonte de verdade do metagame

| Camada | Fonte | Papel |
|---|---|---|
| Primária | **Limitless Developer API** — `https://play.limitlesstcg.com/api` (docs: docs.limitlesstcg.com/developer) | Torneios, standings (placing + decklist + taxonomia de deck), pairings (jogos individuais) |
| Validação cruzada | pocket.untapped.gg · pokemontcgpocket.app · pocketmeta.app | Conferência de tendências; NUNCA fonte de números; NUNCA misturada sem normalização |

O Limitless é a fonte-raiz declarada pelos próprios agregadores (FASE1 §5):
coletar da raiz elimina o intermediário. A API **não exige chave** para os
endpoints de torneio (prova real no cartão F7, 19/10/2026: HTTP 200 sem key).

## 2. Coleta (scripts/meta/collect_meta.py)

1. `GET /tournaments?game=POCKET&limit=50&page=N` — paginação até cobrir a
   janela de 35 dias (default) — checkpoint por página em `data/meta/raw/pages/`.
2. Para cada torneio do período: `details`, `standings`, `pairings` — um
   arquivo JSON por item em `data/meta/raw/tournaments/{id}/` (checkpoint;
   reexecução pula o existente; 404 memorizado como `{"_http404": true}`).
3. Rate limit: header `RateLimit: "50-in-5min"` lido a cada resposta; cliente
   com intervalo mínimo de 6.2s entre chamadas, espera pelo reset quando
   `r<=1`, backoff exponencial em 429/5xx, UA identificado.
4. Nada em `/tmp` (escopo §21); raw é dado de terceiros e fica fora do git
   (política `.gitignore` de `data/`).

Custo medido: ~200 torneios/35 dias ≈ 610 chamadas ≈ 63 min de coleta completa.

## 3. Escopo do snapshot (regra de inclusão)

Um torneio entra no snapshot somente se TODAS as condições:

| # | Condição | Motivo |
|---|---|---|
| 1 | `game=POCKET` | fonte do projeto |
| 2 | formato STANDARD: `format=null` no `/details` (organizador não declarou) é ACEITO; NOEX/CUSTOM declarados ficam fora | NOEX/CUSTOM não são o formato padrão do meta; decisão pela ausência de declaração contrária (medido: 139/200 torneios com format null) |
| 3 | `isPublic=true` | dado público verificável |
| 4 | `decklists=true` | sem decklist não há share por lista |
| 5 | ≥ 1 fase SWISS | estrutura suíça comparável |
| 6 | players ≥ 8 (META_MIN_PLAYERS) | amostra mínima por evento |
| 7 | início ≥ 6h no passado (FINISHED_GRACE_H) | torneio em andamento tem placing parcial |

**Janela vs escopo (F7b):** janela NÃO é gate de escopo. O modo padrão aplica
janela rolante (7/14/30 dias fechando na data UTC corrente — tendência
temporal); o modo `--full` NÃO tem corte de janela e ingere todo o raw
elegível (snapshot `snap-full-<data>`). A coleta cobre 35 dias e a janela
rolante de 30 descartava os excedentes como contagem agregada
`fora_da_janela` — em 19/10/2026 eram 41 torneios elegíveis (2026-09-09 a
2026-09-19) fora do banco (defeito F7b, card t_7872dcac; causa-raiz medida,
não suposta: filtro de janela, não falha de coleta nem dedupe).

**Auditoria de exclusão (F7b):** nenhum torneio é descartado em silêncio.
Toda exclusão é nomeada por motivo, com contagem E lista nominal de
`tournament_id`s — gravada no relatório (`exclusions.excl` /
`exclusions.excl_nominal`) e impressa no log do pipeline.

O escopo vigente fica gravado no campo `scope` de cada snapshot — todo número
citado carrega o snapshot_id que declara o escopo.

## 4. Métricas

### 4.1 Share (POPULARIDADE)
```
share_pct(arch) = 100 * listas_do_arquetipo / listas_totais_da_janela
```
Conta TODA lista no escopo (mesmo com nome de carta não resolvido no join).

### 4.2 Win rate (DESEMPENHO)
```
win_rate_pct(arch) = 100 * (Σwins + 0.5·Σties) / (Σwins + Σlosses + Σties)
```
Soma dos `record` de todos os players do arquetipo nos standings da janela.
Empate vale meio ponto (padrão de tiebreak de metagame). **Popularidade nunca
é apresentada como desempenho** — os dois números ficam em colunas distintas.

### 4.3 Consistência
```
consistency_pct(arch) = 100 * torneios_com_melhor_record_wins>losses /
                        torneios_com_presenca(>=1 lista)
```
Mede capacidade de levar um evento além do break-even, não só volume.

### 4.4 Matchups
Base: `GET /tournaments/{id}/pairings` cruzado com a taxonomia do standings.
**Fora da taxa** (contados como exclusões): espelho (mesmo deck.id), bye/
ausente (player2 vazio), empate (winner=0), double loss (winner=-1), jogador
sem taxonomia, vencedor fora do par. O par é ordenado (a<b) e a taxa é do lado
a. `sample_size` = jogos do par na janela; `confidence`: high ≥ 200,
medium ≥ 50, low < 50. **Sem amostra não existe matchup** (regra do escopo).

## 5. Tiers — regra F7 v1 (a regra completa, sem resumo)

1. **Gates de amostra** (condição necessária): ≥ 20 listas E ≥ 100 jogos na
   janela. Quem não passa recebe `tier=''` e `tier_basis` iniciando com
   `sem_evidencia:` + amostra exata. É um resultado declarado, não falha.
2. **Faixas por win_rate da janela** (só quem passou nos gates):

| Tier | win_rate_pct |
|---|---|
| S | ≥ 55.0 |
| A | ≥ 52.0 |
| B | ≥ 49.0 |
| C | ≥ 45.0 |
| D | < 45.0 |

3. `F` nunca é emitido (reservado a falha de integridade de dados comprovada).
4. `basis` citável: todo tier carrega a frase com win_rate, n de jogos, n de
   listas e os gates.
5. A regra vive em `scripts/meta/meta_pipeline.py` (TIER_BANDS, MIN_DECKS,
   MIN_MATCHES) e nenhuma análise pode atribuir tier fora dela. Mudança de
   regra = nova versão v2 documentada aqui + nos testes.

**Cenário Mega Gengar ex:** a carta existe no catálogo (limitless:B2b/39,
5 impressões) mas, na amostra real da janela, se nenhuma lista aparecer nos
torneios do escopo, o arquetipo não é criado ou entra como `sem_evidencia`
com a amostra citada (no full de 19/10/2026: 14 listas / 20 cópias de
limitless:B2b/39 — segue abaixo do gate de 20 listas → `sem_evidencia`;
as 21 listas do agregado "Gengar" do watch_cards somam as 4 variantes da
carta, incluindo Gengar/Gengar ex antigos, e não são o arquetipo). Qualquer análise desse deck
é teórica e jamais rotulada como resultado de torneio.

## 6. Modelo de dados (migrations 0003)

- `meta_archetypes` — +`sample_decks`; tier agora aceita 'S' (e vazio =
  sem evidência). `tier_basis` obrigatório em nível de app quando tier ≠ NULL.
- `meta_snapshot_archetypes` — +`sample_decks`, `sample_matches`.
- `tiers` — +`sample_decks`, `sample_matches` (amostra citável por tier).
- `matchups` — +`sample_matches`.
- `tournament_matches` — NOVA: jogos individuais auditáveis
  (PK `{tid}:{phase}:{round}:{seq}`, com winner e arquétipos; exclusões
  guardadas com winner vazio).
- Migration 0003 é ADITIVA (reconstrói 3 tabelas para alargar CHECKs, sem
  destruir colunas; tabelas estavam vazias na data — provado no cartão).

## 7. API key: decisão pendente do dono (previsão do escopo)

O projeto é público; a chave Limitless existe para projetos públicos e libera
(a) rate limit maior e (b) o endpoint `/games/{id}/decks` (regras de
categorização). **Nenhum pedido é feito sem decisão do dono** (proibição do
card). Quando decidido: solicitar em play.limitlesstcg.com → account settings
→ API, enviar via `?key=` ou header `X-Access-Key` (nunca commitar; ler do
ambiente). O cliente já suporta a ausência de chave — sem ela, o escopo atual
funciona dentro de 50/5min.

## 8. Operação

```bash
# coleta incremental (checkpoint; reexecução pula existente)
python3 scripts/meta/collect_meta.py

# snapshot 30 dias (default) + relatório
python3 scripts/meta/meta_pipeline.py --days 30

# janelas 7 e 14
python3 scripts/meta/meta_pipeline.py --days 7
python3 scripts/meta/meta_pipeline.py --days 14

# reconciliacao/ingestao completa (sem corte de janela; coexiste com as janelas)
python3 scripts/meta/meta_pipeline.py --full

# teste de reconciliacao raw x banco (guarda F7b; ro no banco de producao)
python3 -m unittest tests.unit.test_f7b_reconciliation
```

- Relatórios: `data/meta/reports/snap-{7,14,30}d-{data}.json` e
  `snap-full-{data}.json` (fora do git); todo relatório carrega
  `exclusions` (contagens + listas nominais por motivo).
- Backups do banco: política docs/DATABASE.md (backups/ antes de sync —
  ex.: `data/backups/pocket-f7b-pre-ingest.sqlite`, 19/10/2026).
- Retenção do raw: `data/meta/raw/` é apend-only; nunca apagar (regra do
  snapshot histórico).

## 9. Cobertura REAL e reconciliação (F7b, lido do banco em 19/10/2026)

Leitura direta de `data/pocket.sqlite` após a correção e re-ingestão:

| Snapshot | Torneios | Listas | Linhas de pairing | Janela |
|---|---|---|---|---|
| snap-full-2026-10-19 | **123** | 8.622 | 24.984 | 2026-09-09 .. 2026-10-19 (sem corte — todo o elegível) |
| snap-30d-2026-10-19 | 82 | 4.865 | 13.927 | 2026-09-20 .. 2026-10-19 |
| snap-14d-2026-10-19 | 35 | 2.090 | 5.924 | 2026-10-06 .. 2026-10-19 |
| snap-7d-2026-10-19 | 14 | 681 | 1.923 | 2026-10-13 .. 2026-10-19 |

Reconciliação raw × banco (fechada): 200 torneios coletados = **123 elegíveis
ingestíveis (todos no banco)** + 77 exclusões de escopo nomeadas:
`formato_nao_standard=68`, `sem_swiss=5` (torneios SINGLE/DOUBLE_BRACKET, sem
fase suíça), `players_minimo=3`, `sem_decklists=1` (torneio com decklists
desligadas na origem — 0 listas). Nenhum torneio elegível fora do banco;
nenhum registro no banco fora dos gates (listas nominais nos relatórios).

**Por que 123 e não 128** (medição de 18/10 no card): o critério provisório
aplicava só 2 dos 7 gates (formato + players). Aplicando o escopo completo de
docs/META.md, 5 dos 128 falham em gates adicionais — 4 sem fase SWISS
(`6acf5e87115c12b73a5a39f3` DOUBLE_BRACKET, `6ac2e205245696afb3516622` e
`6aaac3d9f1243e65f9802bad` SINGLE_BRACKET 20/95 players,
`6aa17016a4272c53be64bb41` SINGLE_BRACKET) e 1 com `decklists=false` na origem
(`6abe4b19783097f8dcb74fed`, 0 listas — também é o único dos 46 sem decklist
no standings). 128 − 5 = 123, todos ingestíveis, todos no banco.

O texto antigo desta seção falava em "~200 torneios/30 dias": eram 200
COLETADOS (janela de coleta de 35 dias), 123 ELEGÍVEIS e 82 ingestos antes da
correção F7b (64% da amostra). Números de tiers/matchups SEM o sufixo
`snap-full` são de janela rolante e citam o próprio snapshot_id.

### 9.1 Impacto nos tiers (amostra 30d → full, lido do banco)

10 arquitetos saíram de `sem_evidencia` para tier com a amostra completa
(gates ≥20 listas e ≥100 jogos — ver `tier_basis` de cada um):
`beautifly-b1-dustox-b4` (A, 52.03%), `hoopa-ex-b4-greninja-a1` (B, 50.58%),
`team-rockets-weezing-ex-b4a-zoroark-ex-b3` (B, 49.16%),
`mega-blaziken-ex-b1-castform-sunny-form-b3` (C, 47.45%) e 6 em D:
`mega-altaria-ex-chingling-b1`, `mega-altaria-ex-b1`, `mega-venusaur-ex-b1a`,
`mega-altaria-ex-b1-igglybuff-a4a`, `team-rockets-raticate-ex-b4a-alolan-ninetales-ex-b2`,
`mega-charizard-x-ex-b2b-mega-charizard-y-ex-b1a`.

Continuam `sem_evidencia` no full: 555 arquetipos — os maiores quase-gates:
`mega-sceptile-ex-b3-teal-mask-ogerpon-ex-b2` (19 listas/98 jogos),
`espeon-ex-a4-giratina-ex-a2b` (18/86), `mega-charizard-y-ex-b1a-charizard-ex-a1`
(18/94), `mega-lucario-ex-b3-hitmonchan-ex-b1` (18/84). Relatório completo:
`data/meta/reports/snap-full-2026-10-19.json`.

## 10. Limitações conhecidas (honestidade estatística)

1. `deck.id` da Limitless cobre os decks principais; decks raros podem ficar
   sem taxonomia (ficam fora do share — contados nas exclusões).
2. Torneio sem submission de lista não contribui listas (só resultados, se
   entrarem — mas o escopo exige decklists, então ficam fora).
3. Records suíços incluem drop: jogador que dropou tem record parcial —
   permanece na amostra (é o dado real do torneio).
4. BO1 suíço + BO3 top cut: matchups misturam formatos de jogo do mesmo
   torneio (padrão do metagame; a fase está gravada em tournament_matches).
5. Datas dos torneios em UTC; janelas fecham em data UTC (declarado). O modo
   `--full` muda de escopo a cada nova coleta (não é janela fixa) — cite o
   snapshot_id e a data da leitura.
6. Amostras pequenas por par = confidence low — o número existe, a confiança
   não (nunca esconder a coluna confidence).

## 11. Trilha de evidência (aceite F7 + F7b)

- Coleta real: 19/10/2026 — 200 torneios POCKET (2026-09-09..2026-10-18),
  torneio de 355 players com 355/355 standings + 355 listas de 20 cartas +
  355 deck.id (JSON salvos em /opt/data/f7, prova no cartão).
- F7b (19/10/2026): causa-raiz medida (janela 30d × coleta 35d →
  `fora_da_janela`); re-ingestão idempotente `--full` a partir do raw (zero
  rede; 2ª execução não mudou 1 contagem — 123/8.622/24.984/115.741 lidos de
  volta); backup pré-ingestão `data/backups/pocket-f7b-pre-ingest.sqlite`
  (82 torneios); guarda `tests/unit/test_f7b_reconciliation.py` (sintético +
  real ro) reproduziu o defeito em RED antes da correção e ficou VERDE após.
- Suíte: `tests/unit/test_f7_meta.py` (8 testes) + `test_f7b_reconciliation.py`
  (3 testes) — 66/66 OK no venv f5 (3.12.13), OK skipped=3 no sistema (3.13.5).
- Suite do projeto: 66/66 OK (f5_venv, 19/10/2026).
