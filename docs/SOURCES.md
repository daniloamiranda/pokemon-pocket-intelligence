# SOURCES.md — Fontes oficiais perante o registry de regras

Atualizado em **2026-10-19** (Area 15 — mecanicas de app/ranqueada; atualizacao anterior 2026-10-18, tarefa F3b).
Politica: NAO inventar regra (Regra 6). Mecanica de jogo = fonte primaria Pokemon.com/suporte TPC. Existencia e legabilidade por carta = Limitless Pocket DB (F4). TCG fisico/Live e PROIBIDO como fonte de regra do Pocket.

| Tag | Fonte | URL | O que comprova | Consultado em | Status |
|---|---|---|---|---|---|
| [DB] | Pokemon.com — "Learn How to Build a Deck in Pokemon TCG Pocket" (deck building) | https://www.pokemon.com/us/features/learn-how-to-build-a-deck-in-pokemon-tcg-pocket | DECK-001, DECK-002, EVOL-002, POCKET-001, POCKET-002, POCKET-007, POCKET-010, POCKET-011, POCKET-012, TURN-001/DRAW-001, ATK-002 | 2026-10-18 | OK (HTTP 200; texto literal extraido e conferido) |
| [FAQ-BATTLE] | support.pokemon.com — "Pokemon TCG Pocket Battle Rules FAQ" (artigo 38906248102292, "Updated May 12, 2026") | https://support.pokemon.com/hc/en-us/articles/38906248102292-Pokemon-TCG-Pocket-Battle-Rules-FAQ | POCKET-006, POCKET-013, ATK-003, ATK-004, EFF-001, EFF-002, RES-001, RES-002, ERRATA-001 | 2026-10-18 | OK (corpo completo obtido via API oficial do help center Zendesk; site bloqueia crawler com Cloudflare) |
| [FAQ-GAMEPLAY] | support.pokemon.com — "Pokemon TCG Pocket Gameplay FAQ" (artigo 30330309361172) | https://support.pokemon.com/hc/en-us/articles/30330309361172-Pokemon-TCG-Pocket-Gameplay-FAQ | Delegacao das regras de batalha ao tutorial in-app ("Tips" / botao "?"); regras != TCG fisico; ranked points em empate (nao e regra de batalha); MECANICAS DE APP/RANQUEADA APP-001..APP-010 (Area 15 do RULES.md) | 2026-10-18 (API do help center); 2026-10-19 (Firecrawl) | OK (recaptura FULL via Firecrawl/Composio em 19/10 — superconjunto da API de 18/10; evidencia interna NAO versionada em armazenamento local de fontes do host
(fora do repositorio)) |
| [LL] | pocket.limitlesstcg.com — fichas de carta | https://pocket.limitlesstcg.com/cards/{SET}/{NUM} | POCKET-004 (Gengar ex A1/123), POCKET-005 (Mega Gengar ex B4b/141), WEAK-001, RET-001, ABIL-001..003, EVOL-001, DECK-003/004, REST-001 | 2026-10-18 | OK (HTTP 200; texto literal das fichas conferido) |
| [LL-IMG] | Limitless CDN — imagens das cartas (apenas URL, nunca baixadas) | https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/{SET}/{SET}_{NNN:03d}_EN_SM.webp | URL de imagem por impressão em `card_prints.image_url` (F4b). Padrão CONFIRMADO contra o `src` real de `<div class="card-image">` nas fichas e das listagens (`display=compact&show=all`); também nas listagens promo P-A/P-B (mesmo padrão). Amostragem 10 por conjunto × 24 conjuntos: 240/240 HTTP 200 (2026-10-18). Cobertura no banco: 4317/4317 (100%). | 2026-10-18 | OK (URLs conferidas contra a fonte; sem exceção de promo) |
| [XC-1] | pokemontcgpocket.app (agregador, declaradamente Limitless-sourced) | https://pokemontcgpocket.app/ | Validacao cruzada do meta (tendencia, nunca numero): 19/10/2026 servia janela de 18/10 com 8.697 partidas; Altaria/Espeon share #1 — coerente com snap-30d | 2026-10-19 | OK (leitura ao vivo; janela/escopo proprios declarados na pagina) |
| [XC-2] | pocket.untapped.gg tier-list (agregador) | https://pocket.untapped.gg/en/tier-list | Validacao cruzada apenas; 19/10/2026 a pagina servia o MES de setembro/2026 (desatualizada) — uso restrito a tendencia | 2026-10-19 | OK com ressalva (conteudo atrasado) |
| [LL-API] | Limitless Developer API — play.limitlesstcg.com/api (docs: docs.limitlesstcg.com/developer) | https://play.limitlesstcg.com/api | Dados de torneio do metagame (F7): /tournaments, /tournaments/{id}/details|standings|pairings — placing, record, decklist (set+number) e taxonomia deck.id. SEM chave para este escopo; rate limit POR HEADER ("50-in-5min"). Prova real 2026-10-19: HTTP 200 sem key, torneio de 355 players com 355/355 standings + 355 listas de 20 cartas | 2026-10-19 | OK (HTTP 200; JSON conferido contra a documentacao; amostras salvas em data/meta/raw/) |
| [NEWS] | pokemon.com — news e features oficiais | https://www.pokemon.com/us/news/... e /us/features/... | ERRATA-002 (Mega Rising 29/10/2025; anuncio 17/08/2025), ERRATA-003 (mudancas de produto 29/09/2026), confirmacao indireta de POCKET-005 (deck strategy oficial Mega Blaziken ex, 12/11/2025) | 2026-10-18 | OK |

## Citas-literais ancora (prova das regras principais)

1. Deck building (20 cartas, max 2 copias, 1 Basico) — [DB], conferido 2026-10-18:
   > "To be usable in battle, your deck must contain 20 cards, including no more than two copies of any card with the same name and at least one Basic Pokemon."
2. Vitoria por pontos — [DB]:
   > "Winning a battle in Pokemon TCG Pocket requires you to earn three points by Knocking Out your opponent's Pokemon."
3. Derrota automatica — [DB]:
   > "Remember: if you have only one Pokemon in play and it gets Knocked Out, you lose the battle automatically."
4. Energy Zone — [DB]:
   > "There's no need to include Energy cards in Pokemon TCG Pocket decks - the Energy Zone provides one Energy each turn, which you can attach to your any of your Pokemon as you see fit."
   > "By default, the Energy Zone in Pokemon TCG Pocket will provide Energy for every type that's required for your Pokemon's attacks."
   > "However, you can manually set which Energy is generated by the Energy Zone while editing your deck."
5. Compra obrigatoria — [DB]:
   > "You always draw one card at the start of your turn."
6. Ataque sem custo Energy — [FAQ-BATTLE]:
   > "If no Energy symbol is displayed to the left of the attack name on a card, then it is an attack that can be used without any Energy attached to the Pokemon. This means that the attack can be used on the first turn of the player that goes first."
7. Descarte por efeito nao da pontos — [FAQ-BATTLE] (Klefki):
   > "No, a player does not get points if an opposing Pokemon in play is discarded due to an effect. Points are gotten only when an opponent's Pokemon is Knocked Out."
8. Energia da Zona vs Discard vs mover — [FAQ-BATTLE] (Jolteon ex Electromagnetic Wall):
   > "Jolteon ex's Electromagnetic Wall Ability takes effect only when Energy is attached to a Pokemon from the Energy Zone... do not come into effect: when Energy from the Discard Pile is attached... when Energy attached to one Pokemon is moved to a different Pokemon."
9. Efeito temporario removido na Bench — [FAQ-BATTLE] (Buzzwole ex Big Beat):
   > "However, all effects applied to a Pokemon are removed when that Pokemon returns to the Bench."
10. Janela "moved to Active this turn" — [FAQ-BATTLE] (Scizor Gale Thrust):
    > "Additional damage will not be added to the attack if Scyther moves from the Bench to the active spot and then evolves into Scizor."
11. Regra ex — [LL] ficha Gengar ex A1/123:
    > "When your Pokemon ex is Knocked Out, your opponent gets 2 points."
12. Regra Mega Evolution ex — [LL] ficha Mega Gengar ex B4b/141 (prova exigida pela aceitacao 3):
    > "When your Mega Evolution Pokemon ex is Knocked Out, your opponent gets 3 points."
    Complementos da mesma ficha: "Weakness: Fighting", "Retreat: 1".
13. Mega evolution ex — 3 pontos — [NEWS] deck strategy oficial Mega Blaziken ex (12/11/2025):
    > "if your opponent Knocks Out your Mega Evolution Pokemon ex, they get three points — an instant game over."
14. Mackanismica Pocket vs TCG fisico — [FAQ-GAMEPLAY]:
    > "The rules of Pokemon TCG Pocket are different from the Pokemon Trading Card Game. Please check the official website and within the game for more details on battle rules."

## Acesso tecnico as fontes de suporte

- O site support.pokemon.com protege paginas HTML com Cloudflare ("Just a moment..."); o corpo completo dos artigos foi obtido pelo endpoint publico JSON do help center Zendesk:
  `GET https://support.pokemon.com/api/v2/help_center/en-us/articles/{ARTICLE_ID}.json` → `article.body` (HTML oficial).
-pokemon.com paginas de features/strategy sao HTML server-side (curl comum basta).

## Captura FAQ-GAMEPLAY para a Area 15 (2026-10-19)

- As 10 mecanicas de app/ranqueada (APP-001..APP-010, docs/RULES.md Area 15)
  vieram do artigo 30330309361172 capturado em 19/10/2026 via Firecrawl
  (Composio; toolkit firecrawl) — superconjunto da captura de 18/10 por API
  do help center Zendesk (45 vs 43 secoes).
- Evidencia interna NAO versionada (texto de terceiros):
  armazenamento local de fontes do host (fora do repositorio, NAO versionado):
  `FAQ-GAMEPLAY-30330309361172-FIRECRAWL.md` e a variante do extrator estatico
  (`FAQ-GAMEPLAY-30330309361172.md`).
  Nenhum runtime le essas capturas: a base citavel segue sendo docs/RULES.md.
- A FAQ-GAMEPLAY NAO cobre mecanica de batalha: nenhuma regra NAO VERIFICADA
  das Areas 1-14 foi alterada, incluindo FORMAT-001 — a fonte cobre o
  funcionamento da ranqueada, nao o regulamento de formato.

## Atualizacao da base de regras sob demanda — `scripts/rules_refresh.py` (2026-10-19)

Decisao do Proprietario (19/10): a base de regras (docs/RULES.md) e ESTATICA e
local. A captura externa NUNCA e dependencia de runtime — Firecrawl/Composio e
ferramenta de MANUTENCAO, acionada MANUALMENTE quando houver suspeita de
atualizacao oficial (novo set, temporada, comunicado TPC). Nada agenda o
script (nada de cron); nenhum validador/builder/evaluator o chama — guarda na
suite (`tests/unit/test_rules_refresh.py`, 17 testes, inclui o grep que prova
que validate_deck.py, build_deck.py e evaluate_deck.py nao conhecem rede).

Quando rodar:
1. Suspeita de mudanca oficial (news TPC, novo set/temporada — a politica de
   fontes item 4 ja define esse gatilho —, ou post citando regra nova).
2. Rodar MANUALMENTE: `<venv do projeto>/bin/python3 scripts/rules_refresh.py`
   (mantenedor usa o venv por causa do SDK composio; a captura nunca escreve
   em data/pocket.sqlite). Opcional: `--report arquivo.md` salva o relatorio.
3. Ler o relatorio impresso: por fonte, "sem mudanca" (codigo 0, snapshot fica
   byte-intocado), "primeira captura" (codigo 0, cria a linha de base) ou
   "MUDANCA DETECTADA" (codigo 10) com secoes afetadas (headers `## `),
   sha256 anterior/atual e diff unificado.
4. Quem decide a mudanca no docs/RULES.md e o Proprietario — o script NUNCA
   edita RULES.md automaticamente. Sem decisao registrada, a captura fica
   apenas como evidencia interna.
5. A captura externa (snapshots em data/rules_snapshots/, FORA do git) NUNCA
   e versionada: texto de terceiros segue a politica deste arquivo; so o
   mecanismo (script + teste + esta secao) e codigo.

Conexao (requisito): o Firecrawl precisa de conta ACTIVE no Composio. O script
descobre sozinho a connected account do toolkit `firecrawl` com status ACTIVE
e o user_id dela — que pode ser id de projeto, NAO "default" (em 19/10/2026
era um id `pg-test-...`; identificador de conta nao e documentado em repositorio,
o script resolve a cada run). A credencial vem da variavel de processo
`COMPOSIO_API_KEY` ou do arquivo apontado por `RULES_REFRESH_ENV_FILE`
(default o mesmo .env do sync F11); a chave NUNCA va em argv. Sem conexao
(sem SDK no venv, sem credencial ou sem conta ACTIVE) o script termina com
codigo 3 e instrucao de reconexao — sem retry infinito. Captura vazia, abaixo
de 3000 bytes (padrao; `--min-bytes` ajusta), HTTP != 200 ou sem estrutura de
secoes = erro declarado (codigo 4), NUNCA "sem mudanca".

Linha de base em 19/10/2026 (criada pelo proprio script, codigo 0):
- faq-gameplay: 17.456 bytes, sha256 6b2615d1cf57a16317ec43beb514a90e56ecb19f4c1d6fc12ce6b976e01af371
- faq-battle:   4.518 bytes, sha256 41eeab87e6164a7a7636469088a414a8cc987bff9ae17d59de14bc43b2bad1d4
- toolkit version pinned 20261014_01; idempotencia provada (2o run = "sem
  mudanca" com snapshots byte-intocados) e deteccao provada (captura
  adulterada em COPIA = codigo 10 com secao nomeada; producao intocada).

## Coleta reproducible a partir do cache persistente (F5d, 19/10)

O cliente HTTP (`integrations/limitlesstcg-pocket/client.py`) grava toda
pagina baixada em `data/cache/pages` (caminho PERSISTENTE do projeto;
`POCKET_CACHE` pode sobrepor). O default `/tmp/pocket_cache` (efemero) foi
eliminado — escopo §21. Com o cache presente, reexecutar
`scripts/collect_pocket.py` NAO refaz fetch de rede: as paginas sao servidas
do disco (idempotencia offline provavel). Cache negativo (404) tambem
persiste no mesmo diretorio. Imagens NUNCA sao baixadas.

## Politica de fontes

1. NUNCA inventar regra (Regra 6 do escopo). Se nao ha fonte oficial, o item entra como `NAO VERIFICADA` com nota de lacuna — nunca como restricao.
2. Mecanica de jogo: Pokemon.com e suporte TPC sao fonte primaria. Existencia/legabilidade por carta: Limitless Pocket DB (F4).
3. Divergencia de fontes: registra-se a divergencia e as datas; escolhe-se a mais autoritativa e anota-se a outra como observacao.
4. Toda regra carrega data de verificacao e vigencia. Novo set/temporada = gatilho de reverificacao.
5. O catalogo real (F4, SQLite `data/pocket.sqlite`) e a fonte de existencia no runtime; este registry e a fonte das REGRAS citaveis.
6. Divergências da FONTE Limitless, registradas (F4b): a pagina de sets e a pagina do conjunto do mesmo site discordam em A3b (107 declarado vs 109 na listagem) e A4a (105 vs 110). Classificadas como `source_inconsistency` (falha da fonte, nao da coleta); a coleta segue a LISTAGEM do conjunto (oraculo por carta). Promos P-A/P-B: a fonte nao declara contagem — fora do calculo percentual por design.
7. Fontes comunitarias (Game8, TheGamer, Pokemon-zone, Bulbapedia, Reddit) sao pista de pesquisa apenas — aparecem no registry como "indicativo comunitario" na coluna Fonte das entradas NAO VERIFICADAS e nunca como prova.

## Lacunas em aberto (resumo para o Proprietario; detalhe em references/RULES.md, area 14/lista final)

Preparacao (bench 3, coin toss, mao inicial 5, garantia de Basico na mao), estruturas de turno (limite de ataque, fim de turno, timer), compra/limite de mao, primeira rodada de Energy da zona, numerico de fraqueza (+20), rotinas de condicao especial (poisoned, burned, asleep, paralyzed, confused, checkup, cura), regra geral de Ability x condicao, regras gerais de recuo (1/turno, bench, bloqueio por condicao), pontos por nocaute regular (1), deck-out nao perder, empate, temporada ranked/ban list e erratas de texto de carta.

## Coleta de metagame (F7, 2026-10-19)

- Fonte-raiz dos numeros de meta: [LL-API] (Developer API, JSON puro). Zero
  scraping de HTML enquanto a API resolver (regra do cartao t_04f33c18).
- Agregadores (pocket.untapped.gg, pokemontcgpocket.app, pocketmeta.app) sao
  APENAS validacao cruzada: nunca fonte de numero, nunca misturados sem
  normalizacao (FASE1 §5). Metodologia e regra de tiers: docs/META.md.
- Raw de torneio = dado de terceiros: fica em data/meta/raw/ (fora do git,
  mesma politica do catalogo). Snapshots apend-only por janela (7/14/30 dias).
