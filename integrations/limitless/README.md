# integrations/limitless — Developer API do Limitless (dados de torneio)

Fonte-raiz do metagame (F7): `https://play.limitlesstcg.com/api`
Docs: https://docs.limitlesstcg.com/developer (lida em 2026-10-19; prova no cartao t_04f33c18).

## Contrato (o que a API garante)

| Endpoint | Retorna | Uso no projeto |
|---|---|---|
| `GET /tournaments?game=POCKET&limit=&page=` | lista de torneios (id, game, format, name, date, players) | enumerar janela de coleta |
| `GET /tournaments/{id}/details` | torneio completo: organizer, decklists(bool), isPublic, isOnline, phases[] | escopo do snapshot |
| `GET /tournaments/{id}/standings` | placing, record{wins,losses,ties}, deck{id,name} (taxonomia Limitless), decklist{pokemon[],trainer[]} com set+number | share, winrate, listas reais |
| `GET /tournaments/{id}/pairings` | jogos individuais (round, phase, player1/2, winner: id/0 empate/-1 double loss) | matchups |
| `GET /games` | jogos e formatos (`POCKET`: STANDARD, NOEX) | descoberta |
| `GET /games/{id}/decks` | regras de categorizacao | EXIGE API KEY — nao usado (decisao do dono pendente) |

## Regras de acesso (implementadas em `api_client.py`)

- **Sem chave** para o escopo acima. NAO pedir key sem decisao do dono (projeto
  publico; formulario em /account/settings/api; `?key=` ou header `X-Access-Key`
  quando autorizado — ler do ambiente, NUNCA commitar).
- **Rate limit por header**: `RateLimit: "50-in-5min"; r=N; t=S`. Cliente:
  intervalo minimo 6.2s, espera do reset quando r<=1, backoff exponencial em
  429/5xx, UA identificado.
- **Zero scraping de HTML** enquanto a API resolver (regra F7).
- Resposta JSON sempre persistida pelo chamador (checkpoint em data/meta/raw/).

## Consumidores

- `scripts/meta/collect_meta.py` — coletor com checkpoint (F7).
- `scripts/meta/meta_pipeline.py` — estatistica/snapshot/tiers (F7).
