# DECK.md — Metodologia do deck-builder (F8)

Projeto: pokemon-pocket-intelligence · Owner técnico: tony_stark (CTO)
Card: t_89d318e2 · Correção F8b: t_f29d4466 · Risco: R2 · Criado: 2026-10-19

---

## 1. Princípio central

**O núcleo do deck é EMPÍRICO, não enumerable por LLM**: as listas reais de
torneio coletadas pela F7 (4.865, fonte `play.limitlesstcg.com`) ditam quais
cartas acompanham a carta principal — e cada quantidade citada carrega a
presença real ("presente em N de M listas"). O motor classificatório só
ATRIBUI função mecânica e pré-requisito; ele não inventa carta e não inventa
texto de efeito.

## 2. Funções mecânicas (F8 v1)

| Função | Definição mecânica | Regra nomeada (exemplos) |
|---|---|---|
| `main-card` | é a carta pedida (sempre presente; proibição do card) | resolvida por card_id/FTS5 |
| `draw` | aumenta/recicla a mão | Professor's Research (4.802/4.865 reais), Copycat (4.644) |
| `search` | puxa do deck p/ mão | Poké Ball (4.249), Pokémon Communication |
| `evolution` | acelera/atualiza estágio | Rare Candy (1.499), Wally |
| `control` | captura/bloqueio/controle do oponente | Cyrus (3.541), Sabrina (1.936), Team Rocket's Boss |
| `protection` | HP/dano/status no próprio | Giant Cape (1.008), Lucky Ice Pop (1.376) |
| `heal` | recupera HP | Pokémon Center Lady (1.826), Erika |
| `mobility` | reposiciona/recuo | X Speed (1.035), efeitos "switch" reais |
| `meta-response` | responde a Tool/mão/dano | Field Blower (1.701), Deceptive Needle |
| `energy-accel` | melhora o fluxo de energia | Flame Patch, Elemental Switch |
| `core-companion` | presença real sem regra nomeada | ranking do corpus, honesto |

Regras nomeadas são **exprimidas em regex case-insensitive** sobre o nome
canônico + complemento do texto REAL da ficha (card_attacks/card_abilities;
trainers re-parseados do cache F4). "Compartilhar tipo/elemento" é
**proibido** como critério de inclusão (limitação do card).

## 3. Núcleo empírico (van Decks reais)

```sql
SELECT card_id, COUNT(DISTINCT deck_id) ndecks, SUM(quantity)
FROM deck_cards WHERE deck_id IN (listas_reais_que_usam_a_principal)
GROUP BY card_id;
```

- Janela: `--days` (padrão 30) sobre `decks.collected_at`; sem dados na
  janela = usa todo o corpus com selo `fallback` (declarado).
- **Exclusão F8b**: decks gerados pelo próprio builder (`id LIKE 'deck-%'`)
  ficam FORA do núcleo — a saída do motor nunca é evidência empírica de si
  mesma (antes, o deck-002 gerado inflava o tally do Gastly psíquico).
- Cut-off de presença: entra na lista quem está em >= 50% do núcleo real.
- Quantidade: 2 quando presença==100% ou cópias agregadas >= 3;
  senão 1 (máx 2 pela regra DECK-002).
- **Agregação por NOME (F8b)**: DECK-002 é "máx 2 cópias por NOME". Quando o
  ranking empírico traz uma SEGUNDA identidade de um nome já presente no
  deck, a identidade não entra — a cópia existente do nome recebe o top-up
  (até 2 no total do nome), citando a presença real que motivou.

## 4. Evolução (EVOL-001 por montagem, não por duct tape)

`cards.evolves_from_id` é NULL por design da carga F4; o vínculo REAL de
evolução vive em `card_evolutions`. Para cada pick não-Básico, o motor:

1. construir a linha completa `[basico, stage1, ..., cid]`;
2. **reservar** espaço na lista e adicionar cada pre faltante (1 cópia) na
   MESMA iteração — nada entra sem cadeia completa;
3. se não couber, o pick é pulado honestamente (o validador F3
   reapprove/reprovado OBRIGATORIAMENTE de qualquer forma — dupla garantia).

**F8b — linha da principal reservada ANTES do núcleo e identidade por NOME+tipo:**

- A linha de evolução da carta PRINCIPAL é reservada antes do ranking
  empírico (o deck-001 antigo ficou com um Mega Gengar ex SEM Haunter
  nenhum — o núcleo consumiu o espaço da própria linha).
- `pick_pre_identity()`: quando `card_evolutions` aponta um pré com
  elemento DIVERGENTE da linha principal (ex: Gastly psíquico A1/120 para
  um Mega Gengar ex sombrio), o motor escolhe a identidade do MESMO NOME
  com o elemento da linha principal (Gastly B2b/37 darkness — 15/16 listas
  reais do corpus) e registra o motivo + `identity_basis` no deck output.
  No jogo real, a ficha evolui por NOME ("Evolves from Gastly"); misturar
  tipos abriria um tipo novo na Energy Zone. O validador F3 (EVOL-001)
  foi alinhado no mesmo sentido: aceita pré-requisito por id OU por nome.

## 5. Energia (regra do formato Pocket, provada)

Nas 4.865 listas reais não há UMA carta `energy_*`: energia no Pocket é
commitada por partida, fora da listagem. Portanto:

- a LISTA tem só Pokémon + Trainer/Tool/Stadium;
- o PLANO de energia é TEXTO ISSO derivado do custo real do ataque
  principal (elementos declarados; custo híbrido avisado);
- aceleradores de energia existentes no catálogo podem entrar como cards
  normais (`energy-accel`), nunca substituindo o commit real.

## 6. Persistência

Migration 0004 (ADITIVA):

```sql
CREATE TABLE IF NOT EXISTS deck_specifications (
    deck_id      TEXT PRIMARY KEY REFERENCES decks(id) ON DELETE CASCADE,
    spec_json    TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
```

- Ids: `deck-{slug}-{n:03d}` (ex.: `deck-mega-gengar-ex-001`).
- `decks.total_cards = 20` (CHECK do schema), `deck_cards.quantity 1..2` (CHECK),
  `deck_cards.print_id NULL` (formato do corpus F7).
- Nunca persiste `ilegal`/`inconsistente`/`sem_evidencia` (rc != 0).

## 7. Veredicto e confiança

| Condição | veredicto | confidence |
|---|---|---|
| núcleo >= 12 listas reais, lista legal | `valido` | medium |
| núcleo < 12 mas lista legal (fallback de consenso) | `fallback` | low |
| 0 lista real com a carta | `sem_evidencia` | — |
| montagem não fecha 20/20 | `inconsistente` | — |
| validador F3 reprova | `ilegal` | — |

**Popularidade ≠ desempenho**: a análise competitiva cita share/win_rate/tier
do snapshot 30d da F7, e SEMPRE declara quando a análise é teórica.

## 8. Trilha de evidência (aceite F8)

- 3+ cartas principais legais provadas: Mega Gengar ex, Hoopa ex, Greninja
  (FTS5 resolve `Greninja` → `Greninja ex` B1/73) — veredictos `valido` rc=0
  (saídas reais salvas: /opt/data/pokemon-cross/f8_out_*2.json).
- Persistência: `deck-mega-gengar-ex-001` com 10 linhas em `deck_cards`
  (soma 20) + 1 spec.
- Zero carta inventada: teste `test_06_carta_inexistente` + veredicto JSON.
- Suite completa: 76 testes, 0 falhas (incl. 10 novos test_f8_deck_builder).

## 9. Correção F8b (card t_f29d4466 — DECK-002 por NOME)

Defeito: o validador F3 checava a quantidade de CADA entrada isolada — não
agregava por nome nem por identidade entre entradas — e o builder misturava
identidades de mesmo nome (Gastly psíquico numa linha sombria). Resultado:
deck ILEGAL na mesa com selo "legal" do motor (2x Gastly B2b/37 + 1x Gastly
A1/120 no deck-mega-gengar-ex-002 original; Froakie x3 no greninja-001).

Correções aplicadas:

1. `validate_deck.py`: DECK-002 com dupla dimensão — por identidade
   (entrada isolada > 2) e agregado por NOME canônico (soma de todas as
   entradas/identidades do mesmo nome). EVOL-001 aceita pré-requisito por
   id OU por nome (a ficha evolui por nome). Comentário alinhado ao
   registry ("Max 2 copias por nome").
2. `build_deck.py`: núcleo empírico exclui `deck-%`; linha da principal
   reservada antes do ranking; `pick_pre_identity()` resolve o pré por
   nome + elemento da linha principal; agregação por NOME no ranking
   (segunda identidade nunca entra — top-up na existente até 2).
3. Fixtures F3 refeitas (o `legal_deck` antigo tinha 4x Cynthia em 2
   entradas e PASSAVA — falso-legal no próprio fixture).
4. Regressão F8b: `tests/unit/test_f8b_deck002_by_name.py` — os 5 casos
   obrigatórios do card + unidade de `pick_pre_identity` + guarda do
   núcleo contra decks gerados.
5. Revalidação do persistido: varredura das `deck_specifications` com o
   validador corrigido; 2 decks ilegais removidos com trilha auditada em
   `audit_logs` (`decks` FK CASCADE); corpus real auditado por nome.
6. Deck do Mega Gengar ex regerado (20 cartas, 10 entradas, linha sombria
   coerente Gastly B2b/37 + Haunter B2b/38, 7/7 regras citadas).
