# RULES.md — Registry de regras do Pokemon TCG Pocket

Catalogo citavel de regras do **Pokemon TCG Pocket** (jogo mobile TPC/DeNA; lancado 30/10/2024, iOS/Android).
Regra de ouro: NUNCA inventar regra sem fonte oficial (Regra 6 do escopo). Divergencia se registra com nota de nova verificacao (politica em references/SOURCES.md).

Legenda de status:
- `VERIFICADA` — fonte oficial (Pokemon.com, suporte oficial TPC ou fichario por carta) conferida na data registrada; citavel pelo validador.
- `NAO VERIFICADA` — competencia de area identificada, SEM fonte oficial ate o momento; fontes de comunidade (Game8, TheGamer, Pokemon-zone, etc.) constam APENAS como indicativo de pesquisa e jamais como prova. Nenhuma regra NAO VERIFICADA e aplicada como restricao pelo validador.

Data de verificacao desta revisao: **2026-10-18 (America/Sao_Paulo)**.

Fontes oficiais (detalhes e URLs em references/SOURCES.md):
- [DB] Pokemon.com — "Learn How to Build a Deck in Pokemon TCG Pocket" (deck building, TPC oficial; texto literal capiturado 2026-10-18).
- [FAQ-BATTLE] support.pokemon.com — "Pokemon TCG Pocket Battle Rules FAQ" (artigo 38906248102292, atualizado 2026-05-12; capturado 2026-10-18 via API oficial do help center).
- [FAQ-GAMEPLAY] support.pokemon.com — "Pokemon TCG Pocket Gameplay FAQ" (artigo 30330309361172) — delega regras de batalha aos Tips in-app (botao "?"); util para delimitar lacunas. Recaptura FULL em 2026-10-19 via Firecrawl (Composio): fonte das mecanicas de app/ranqueada da Area 15 (APP-001..APP-010).
- [LL] pocket.limitlesstcg.com — fichas por carta com texto literal de ataque, Weakness, Retreat e regra ex/Mega (fonte de existencia/legabilidade; F4).
- [NEWS] pokemon.com/news e /features — comunicados oficiais com datas (Mega Rising, ranked seasons, deck strategies oficiais).

---

## Area 1 — Preparacao da partida

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| SETUP-001 | bench_capacity_3 | Bench comporta no maximo 3 Pokemon | NAO VERIFICADA | indicativo comunitario (Game8, TheGamer, cardgamer) | - | - | aguardar ancora oficial/in-app |
| SETUP-002 | coin_toss_first_player | Moeda decide quem comeca | NAO VERIFICADA | indicativo comunitario (Game8) | - | - | aguardar ancora oficial |
| SETUP-003 | forced_basic_start | Mao inicial sempre garante Pokemon Basico (sem mulligan) | NAO VERIFICADA | indicativo comunitario (TheGamer) | - | - | EVOL-002 (deck building) e oficial; a garantia na Mao nao |
| SETUP-004 | opening_hand_5 | Mao inicial = 5 cartas | NAO VERIFICADA | indicativo comunitario | - | - | |

Nota de lacuna: a Gameplay FAQ oficial delega as regras de batalha aos Tips in-app; nenhuma pagina publica do Pokemon.com/suporte detalha a preparacao. Captura in-app pendente para o Proprietario.

---

## Area 2 — Vitoria e sistema de pontos

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| POCKET-002 | points_win_3 | 3 pontos vencem a batalha | VERIFICADA | [DB] | 2026-10-18 | vigente | n/a |
| POCKET-003 | points_ko_1 | Nocaute de Pokemon regular = 1 ponto (comunidade; deduzido do sistema 2/3) | NAO VERIFICADA | indicativo comunitario | - | - | confirmar ancora de 1 ponto |
| POCKET-004 | points_ex_2 | Pokemon ex nocaute = 2 pontos ao oponente (regra impressa na ficha) | VERIFICADA | [LL] ficha Gengar ex A1/123 | 2026-10-18 | vigente | n/a |
| POCKET-005 | points_mega_ex_3 | Mega Evolution ex nocaute = 3 pontos ao oponente (regra impressa na ficha) | VERIFICADA | [LL] ficha Mega Gengar ex B4b/141; [NEWS] Mega Blaziken ex deck strategy 12/11/2025 | 2026-10-18 | vigente | n/a |
| POCKET-006 | no_points_discard | Pokemon descartado por efeito NAO gera pontos; apenas nocaute gera | VERIFICADA | [FAQ-BATTLE] caso Klefki/Dismantling Keys | 2026-10-18 | vigente | n/a |
| POCKET-007 | auto_loss_last_pokemon | Derrota automatica se o unico Pokemon em jogo cai | VERIFICADA | [DB] | 2026-10-18 | vigente | n/a |
| POCKET-008 | deck_out_not_loss | Deck out NAO elimina o jogador (diferente do TCG fisico/Live) | NAO VERIFICADA | indicativo comunitario (Game8, TheGamer) | - | - | |
| POCKET-009 | tie_rule | Empate in-batalha: sem regra publica | NAO VERIFICADA | [FAQ-GAMEPLAY] cobre apenas rank points em tie | - | - | |

Citas literais verificadas:
- [DB] "Winning a battle in Pokemon TCG Pocket requires you to earn three points by Knocking Out your opponent's Pokemon."
- [DB] "Remember: if you have only one Pokemon in play and it gets Knocked Out, you lose the battle automatically".
- [FAQ-BATTLE] "No, a player does not get points if an opposing Pokemon in play is discarded due to an effect. Points are gotten only when an opponent's Pokemon is Knocked Out."
- [LL] Gengar ex (A1/123): "When your Pokemon ex is Knocked Out, your opponent gets 2 points."
- [LL] Mega Gengar ex (B4b/141): "When your Mega Evolution Pokemon ex is Knocked Out, your opponent gets 3 points."
- [NEWS] "if your opponent Knocks Out your Mega Evolution Pokemon ex, they get three points — an instant game over." (deck strategy oficial de Mega Blaziken ex, 12/11/2025)

---

## Area 3 — Estrutura de turno

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| TURN-001 | draw_at_start | Compra obrigatoria no começo de cada proprio turno | VERIFICADA | [DB] "You always draw one card at the start of your turn" | 2026-10-18 | vigente | n/a |
| TURN-002 | attack_once_per_turn | Ativo ataca no maximo 1 vez por turno | NAO VERIFICADA | indicativo comunitario/TCG geral | - | - | |
| TURN-003 | attack_ends_turn | Ataque encerra o turno | NAO VERIFICADA | comunidade | - | - | |
| TURN-004 | turn_timer_90s | Timer de 90 segundos por turno (versus) | NAO VERIFICADA | comunidade (Pokemon-zone) | - | - | |
| TURN-005 | first_player_restrictions | Turno 1 do primeiro jogador: sem Energy da zona e sem ataque (alternativa: ataques sem Energy funcionam — ver ATK-003) | NAO VERIFICADA | comunidade (Game8, TheGamer) | - | - | ATK-003 menciona "first turn of the player that goes first" p/ ataques sem custo, meio indireto |

---

## Area 4 — Compra (inicial e por turno)

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| DRAW-001 | draw_one_per_turn | 1 carta por turno | VERIFICADA | [DB] | 2026-10-18 | vigente | n/a |
| DRAW-002 | opening_hand_5 | Mao inicial de 5 | NAO VERIFICADA | comunidade | - | - | |
| DRAW-003 | hand_limit | Limite de cartas na mao: sem regra publica | NAO VERIFICADA | comunidade (Game8 comments) | - | - | |

---

## Area 5 — Zona de Energia

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| POCKET-001 | energy_zone_no_cards | Nenhuma carta de Energia no deck (Energy Zone fornece) | VERIFICADA | [DB] | 2026-10-18 | vigente | n/a |
| POCKET-010 | energy_zone_one_per_turn | Energy Zone fornece 1 Energy por turno | VERIFICADA | [DB] | 2026-10-18 | vigente | n/a |
| POCKET-011 | energy_zone_default_types | Por padrao, forneca Energy para cada tipo requerido pelos ataques do deck (exemplo Druddigon) | VERIFICADA | [DB] | 2026-10-18 | vigente | n/a |
| POCKET-012 | energy_zone_manual_set | Energy gerada pode ser configurada manualmente no editor de deck | VERIFICADA | [DB] | 2026-10-18 | vigente | n/a |
| POCKET-013 | energy_zone_vs_discard | Energy da Energy Zone ≠ Energy do Discard Pile ≠ Energy movida entre Pokemon (efeitos que "olham" apenas a primeira, caso Jolteon ex/Electromagnetic Wall) | VERIFICADA | [FAQ-BATTLE] | 2026-10-18 | vigente | n/a |
| POCKET-014 | first_player_no_zone | Primeiro turno do primeiro jogador nao gera/recebe Energy da zona | NAO VERIFICADA | comunidade (Game8, TheGamer, cardgamer) | - | - | |

Citas literais:
- [DB] "There's no need to include Energy cards in Pokemon TCG Pocket decks - the Energy Zone provides one Energy each turn, which you can attach to your any of your Pokemon as you see fit."
- [DB] "By default, the Energy Zone in Pokemon TCG Pocket will provide Energy for every type that's required for your Pokemon's attacks." (exemplo Druddigon)
- [DB] "However, you can manually set which Energy is generated by the Energy Zone while editing your deck."
- [FAQ-BATTLE] "Jolteon ex's Electromagnetic Wall Ability takes effect only when Energy is attached to a Pokemon from the Energy Zone... do not come into effect: when Energy from the Discard Pile is attached... when Energy attached to one Pokemon is moved to a different Pokemon."

---

## Area 6 — Ataques (custo, dano, efeitos)

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| ATK-001 | cost_declared | Ficha declara custo em Energy por ataque | VERIFICADA | [LL] fichas (ex: Mega Charizard Y ex Crimson Dive exige [F][F][F][C]; deck strategy oficial) | 2026-10-18 | vigente | custo zero nos ataques sem simbolo — ATK-003 |
| ATK-002 | damage_declared | Dano impresso na ficha; nocaute quando dano >= HP | VERIFICADA | [LL] fichas; [DB] "bring one of your opponent's Pokemon down to zero HP" | 2026-10-18 | vigente | ataques de efeito puro podem ter dano 0/ausente |
| ATK-003 | no_cost_attack | Ataque sem simbolo de Energy a esquerda do nome pode ser usado sem Energy, inclusive no turno 1 do jogador que comeca | VERIFICADA | [FAQ-BATTLE] | 2026-10-18 | vigente | n/a |
| ATK-004 | effect_per_card | Efeitos de ataque são os impressos (ex: extra 50 do Gale Thrust do Scizor; self damage secreto do Mega Charizard Y ex Crimson Dive) | VERIFICADA | [FAQ-BATTLE]; [LL] fichas | 2026-10-18 | vigente | nunca extrapolar para fora da ficha |

---

## Area 7 — Recuo e custo

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| RET-001 | retreat_cost_field | Ficha traz "Retreat: N" (custo em Energy) | VERIFICADA | [LL] fichas (Mega Gengar ex B4b/141 "Retreat: 1"; Gengar ex A1/123 "Retreat: 2") | 2026-10-18 | vigente | custo 0 = gratis |
| RET-002 | retreat_pay_attached | Recuo pago com Energy ATTACH no Pokemon (nao da mao) | VERIFICADA (a confirmar ambas com ficha explicita) | [NEWS] deck strategy oficial (Leaf reduz Retreat Cost de Ho-Oh ex; Levitate recua com custo 0) | 2026-10-18 | vigente | cartas tipo Leaf/X Speed alteram |
| RET-003 | retreat_once_per_turn | Recuo limitado a 1 por turno | NAO VERIFICADA | comunidade | - | - | |
| RET-004 | bench_needed_to_retreat | Recuo exige Pokemon na Bench para promov | NAO VERIFICADA | comunidade | - | - | |
| RET-005 | asleep_paralyzed_no_retreat | Asleep/Paralyzed nao podem recuar | NAO VERIFICADA | comunidade | - | - | Area 9 tambem pendente |

---

## Area 8 — Fraquezas

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| WEAK-001 | weakness_printed | Ficha declara Weakness por tipo | VERIFICADA | [LL] fichas (Mega Gengar ex B4b/141 "Weakness: Fighting"; Marowak ex A1/153 "Weakness: Grass"; Gengar ex A1/123 "Weakness: Darkness") | 2026-10-18 | vigente | n/a |
| WEAK-002 | weakness_plus20 | Fraqueza aplica +20 de dano no Pocket (NAO 2x do TCG fisico) | NAO VERIFICADA | comunidade (Game8, Pokemon-zone) | - | - | sem ancora numerica oficial em ficha ou site TPC |

Lacuna: fichas do Limitless exibem apenas o tipo da fraqueza, sem numerico. Ainda falta ancora oficial do "+20".

---

## Area 9 — Condicoes especiais

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| COND-001 | special_conditions_exist | Mecanicas de condicoes especiais existem via efeitos declarados em ficha | VERIFICADA | [NEWS] deck strategy (Terminating Tail do Mega Sceptile ex gera Poison) | 2026-10-18 | vigente | lista fechada de estados a confirmar |
| COND-002 | poisoned | Envenenado: rotina exata no Pocket | NAO VERIFICADA | comunidade | - | - | |
| COND-003 | burned | Queimado: rotina exata (coin flip p/ curar?) | NAO VERIFICADA | comunidade | - | - | |
| COND-004 | asleep | Adormecido: bloqueia ataque/recuo? curado por moeda? | NAO VERIFICADA | comunidade | - | - | |
| COND-005 | paralyzed | Paralisado: bloqueia ataque/recuo por 1 turno? | NAO VERIFICADA | comunidade | - | - | |
| COND-006 | confused | Confundido: coin flip antes de atacar? | NAO VERIFICADA | comunidade | - | - | |
| COND-007 | checkup_order | Ordem de resolucao (poison>burn>asleep>paralyzed)? | NAO VERIFICADA | comunidade | - | - | |
| COND-008 | cure_by_evolution | Evolucao/retorno a Bench curam condicoes | NAO VERIFICADA | comunidade | - | - | |

Lacuna critica para F8/F9: ainda sem ancora oficial (nome, rotina, ordem, cura) — Pokemon.com e suporte TPC nao publicam detalhamento.

---

## Area 10 — Habilidades

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| ABIL-001 | ability_declared | Ability definida unicamente por ficha (texto literal) | VERIFICADA | [LL] fichas (Leafeon ex Forest Breath, Druddigon Rough Skin, Oricorio Safeguard) | 2026-10-18 | vigente | n/a |
| ABIL-002 | ability_frequency | Frequência de uso (once-per-turn, continuo, once-per-game) vem do texto da ficha | VERIFICADA (por ficha) | [LL] fichas | 2026-10-18 | vigente | n/a |
| ABIL-003 | ability_location_rule | Regra de uso (Active Spot vs Bench) vem do texto da ficha | VERIFICADA | [LL] fichas ("works only when Leafeon ex is your Active Pokemon") | 2026-10-18 | vigente | n/a |
| ABIL-004 | ability_status_blocks | Ability bloqueada por condicao especial | NAO VERIFICADA | comunidade | - | - | |

---

## Area 11 — Efeitos continuos vs temporarios ("durante o proximo turno")

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| EFF-001 | effect_removed_on_bench | Efeito aplicado a Pokemon e removido quando ele volta a Bench | VERIFICADA | [FAQ-BATTLE] (Buzzwole ex Big Beat) | 2026-10-18 | vigente | n/a |
| EFF-002 | effect_this_turn_window | Efeito "movido para Active neste turno" nao acumula dano extra se a movida veio de nocaute no turno do oponente ou de evolução depois de mover | VERIFICADA | [FAQ-BATTLE] (Scizor Gale Thrust) | 2026-10-18 | vigente | n/a |

Citas:
- [FAQ-BATTLE] "However, all effects applied to a Pokemon are removed when that Pokemon returns to the Bench."
- [FAQ-BATTLE] "Additional damage will not be added to the attack if Scyther moves from the Bench to the active spot and then evolves into Scizor."

---

## Area 12 — Interacao e ordem de resolução de efeitos

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| RES-001 | card_text_precedence | Conflitos de resolução resolvidos por leitura literal da carta; casos ambíguos viram item no FAQ-BATTLE | VERIFICADA | [FAQ-BATTLE] natureza dos casos | 2026-10-18 | vigente | FAQ cresce caso a caso |
| RES-002 | reveal_scope | Regras de quantos/quais cartas sao reveladas por efeito (ex Prank Spinner So 1 carta) | VERIFICADA | [FAQ-BATTLE] Prank Spinner | 2026-10-18 | vigente | n/a |
| RES-003 | simultaneous_effects | Sem fonte oficial para ordem generalizada de efeitos simultâneos | NAO VERIFICADA | comunidade | - | - | |

---

## Area 13 — Restricoes de formato

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| DECK-001 | deck_size_20 | Deck tem exatamente 20 cartas | VERIFICADA | [DB] | 2026-10-18 | vigente | nenhuma |
| DECK-002 | copies_max_2 | Max 2 copias por nome | VERIFICADA | [DB] | 2026-10-18 | vigente | nenhuma |
| DECK-003 | card_exists | Carta existe no catalogo | VERIFICADA | [LL] / DB canônico F4 | 2026-10-18 | vigente | nenhuma |
| DECK-004 | format_legality | Carta legal no formato vigente (por release de set) | VERIFICADA | [LL] / DB canônico F4 (card_legality) | 2026-10-18 | vigente | temporada ranked pode adicionar regras — FORMAT-001 pendente |
| EVOL-001 | evolution_pre_req | Stage 1 exige o Basico; Stage 2 exige Stage 1; Mega (mega_ex) exige o pre-requisito da cadeia (pelo nome/id, mesmo principio) | VERIFICADA | [LL] fichas (campo evolves/pre-evolution) | 2026-10-18 | vigente | Rare Candy/evolução direta conforme ficha |
| EVOL-002 | needs_basic | Pelo menos 1 Pokemon Basico no deck | VERIFICADA | [DB] | 2026-10-18 | vigente | nenhuma |
| REST-001 | special_rule_limits | Restricões declaradas na ficha (special_rule) | VERIFICADA | [LL] fichas | 2026-10-18 | vigente | aplica-se somente se a ficha declarar |
| FORMAT-001 | season_rules | Regras de temporada ranked | NAO VERIFICADA | comunidade (Pokemon-zone; [NEWS] indica temporadas B1/B4b SP) | - | - | fora do escopo de legalidade deck |

---

## Area 14 — Alterações/erratas oficiais com data

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| ERRATA-001 | faq_battle_timeline | FAQ-BATTLE registra casos novos (artigo Atualizado 12/05/2026) | VERIFICADA | [FAQ-BATTLE] (data "Updated" no artigo) | 2026-10-18 | vigente | revisar a cada novo caso |
| ERRATA-002 | mega_rules_debut | Mega Evolution Pokemon ex debutou em Mega Rising (29/10/2025) com a mecânica de 3 pontos | VERIFICADA | [NEWS] 17/08/2025 e 23/10/2025 | 2026-10-18 | vigente | n/a |
| ERRATA-003 | product_changes_channel | Mudanças de processo/produto anunciadas via pokemon.com/news (ex: community decks, fim de rental decks, out/2026) | VERIFICADA | [NEWS] "Deluxe Pack: Mega is Now Available" 29/09/2026 | 2026-10-18 | vigente | n/a |
| ERRATA-004 | card_text_errata | Erratas oficiais de texto de carta individual | NAO VERIFICADA | comunidade | - | - | sem canal publico identificado |

---

## Area 15 — Mecanicas de app e ranqueada

> **ESCOPO (produto, nao legalidade):** esta area descreve MECANICA DE PRODUTO/APP —
> operacao do aplicativo (virada de data, missoes, economia, decks alugados, flair) e
> do modo ranqueado — e NAO legalidade de deck. O validador NAO usa estas linhas como
> restricao: o veredicto de legalidade continua citando apenas as regras das Areas
> 2-13 conforme a secao "Citacao obrigatoria". Nenhum runtime le a captura externa:
> a base citavel e este arquivo (docs/RULES.md); a captura citada abaixo e apenas
> evidencia de origem (interna, NAO versionada — texto de terceiros).
>
> **Fonte e captura:** [FAQ-GAMEPLAY] support.pokemon.com, artigo 30330309361172,
> capturado em 2026-10-19 via Firecrawl (Composio) — evidencia interna em
> armazenamento local de fontes do host (fora do repositorio, NAO versionado)
> (superconjunto, 45 secoes, da captura de 2026-10-18 por API do help center).
>
> **Lacuna intencional:** a FAQ-GAMEPLAY NAO cobre mecanica de batalha (bench, mao
> inicial, timer de turno, fraqueza +20, condicoes especiais, recuo, deck out,
> empate in-batalha) — nenhuma regra NAO VERIFICADA das Areas 1-14 foi alterada
> por esta area. Em particular, FORMAT-001 (regras de temporada/ban list) CONTINUA
> NAO VERIFICADA: a fonte cobre o funcionamento da ranqueada, nao o regulamento
> de formato.

| ID | Codigo | Regra | Status | Fonte | Verificado | Vigencia | Excecoes |
|---|---|---|---|---|---|---|---|
| APP-001 | date_rollover_0600_utc | Virada de data do jogo as 06:00 UTC — governa missoes diarias, janelas de evento e o conceito de "dia"; a fonte adverte que a virada pode nao ocorrer exatamente nesse horario | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |
| APP-002 | ranked_requires_player_level_3 | Ranqueada exige nivel de jogador 3 — nivel em que a funcao de batalha e liberada (a outra causa declarada de indisponibilidade e temporada encerrada em processamento de resultados) | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |
| APP-003 | ranked_tie_freezes_points | Empate em ranqueada: pontos nao sobem nem descem, porem a sequencia de vitorias (win streak) e zerada | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | regra de PONTOS de ranqueada; nao cobre empate in-batalha (POCKET-009 segue NAO VERIFICADA) |
| APP-004 | win_streak_bonus_cap_5 | Bonus de sequencia de vitorias so aumenta ate 5 vitorias consecutivas; alem de 5, o bonus permanece igual ao de 5 | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |
| APP-005 | versus_reconnect_window_120s | Crash ou desconexao em partida versus: janela de reconexao de ~120 segundos; sem reconectar nesse prazo, derrota | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |
| APP-006 | battle_result_recorded_offscreen | Resultado da batalha e registrado e os pontos sao atualizados mesmo se a tela de resultados nao for vista (ex: app fechado) | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |
| APP-007 | match_after_season_end_not_counted | Partida de ranqueada que termina apos o fim do periodo da temporada nao conta para o rank dessa temporada | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |
| APP-008 | rental_deck_one_use_per_match | Deck alugado: usos limitados e nao ampliaveis; comecar uma partida consome 1 uso independentemente do resultado (vitoria, derrota ou desistencia); NAO pode ser usado em versus | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |
| APP-009 | pack_points_per_expansion_no_expiry | Pack points: nao expiram, sao acumulados por expansao e trocaveis apenas por cartas daquela mesma expansao; o codigo de expansao (A1, A1a, A2) define a quais booster packs as cartas pertencem | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | podem existir cartas da expansao que nao saem de booster packs (nota da propria fonte) |
| APP-010 | gold_frame_eligibility | Gold frame (flair): elegiveis apenas cartas de raridade 1, 2 ou 3 diamantes; NAO elegiveis parallel foil, raridade 4 diamantes ou superior, e promos | VERIFICADA | [FAQ-GAMEPLAY] | 2026-10-19 | vigente | n/a |

Citas literais verificadas (captura de 2026-10-19, artigo 30330309361172):
- [FAQ-GAMEPLAY] "The date changes at 6:00 a.m. (UTC). Updates for various events also typically occur at the same time. Please note that date change may not occur exactly at the above time." (APP-001; o mesmo artigo repete a virada ao tratar de missoes diarias)
- [FAQ-GAMEPLAY] "You haven't reached player level 3, which is when the battle feature is unlocked." (APP-002)
- [FAQ-GAMEPLAY] "If your game ends in a tie, your ranked match points will not increase or decrease. However, your win streak points will be reset." (APP-003)
- [FAQ-GAMEPLAY] "Win streak points only increase up to five consecutive wins. For consecutive wins beyond five, the bonus remains the same as for five wins." (APP-004)
- [FAQ-GAMEPLAY] "you may attempt to rejoin the match within the reconnection window of around 120 seconds. If you cannot reconnect within that timeframe, you lose the match." (APP-005; o artigo repete a politica em duas secoes de desconexao, com o mesmo prazo)
- [FAQ-GAMEPLAY] "If you are unable to view the battle results screen (for example if you closed the app), the battle outcome is still recorded, and your points will be updated accordingly." (APP-006)
- [FAQ-GAMEPLAY] "If your ranked match ends after the season period, the results will not be counted toward your rank for that season." (APP-007)
- [FAQ-GAMEPLAY] "Once you start a match with a rental deck, that will count as one use of that rental deck regardless of the outcome—win, loss, or forfeit." + "you cannot use rental decks in versus battles." (APP-008)
- [FAQ-GAMEPLAY] "No, pack points do not expire." + "Opening booster packs of a given expansion earns you pack points for that expansion. Those points can be exchanged only for cards that appear in that expansion." + "The expansion code (such as A1, A1a, and A2) tells you which cards belong to which booster packs." (APP-009)
- [FAQ-GAMEPLAY] "Cards with 1-, 2-, or 3-diamond rarity are eligible for gold frame flair." + "Cards not eligible for gold frames include parallel foil cards, 4 diamond–rarity or higher cards, and promo cards." (APP-010)

---

## Resumo de lacunas para o Proprietario (aceitação 5)

Areas SEM fonte oficial em 2026-10-18 (há apenas indicativos comunitários, não usáveis como regra):

1. Preparacao da partida (SETUP-001..004): bench max 3, coin toss, garantia de Basico na mao, opening hand 5.
2. Turno (TURN-002..005): limite de ataque, fim de turno, timer.
3. Compra (DRAW-002, DRAW-003): tamanho da mao inicial, limite de mao.
4. Zona de Energia (POCKET-014): primeira rodada, energia por rodada exactmente.
5. Fraqueza (WEAK-002): "+20" sem ancora numerica oficial.
6. Condicoes especiais (COND-002..008): rotinas por estado, ordem, cura; nenhum texto oficial.
7. Habilidades (ABIL-004): interação com conditiones.
8. Recuo (RET-003..005): 1 por turno, precisa de bench, bloqueado por Asleep/Paralyzed.
9. Vitoria (POCKET-003/008/009): ponto por KO regular (1), deck out não perde, tie sem regra.
10. Formato (FORMAT-001): temporada ranked; ban list; erratas de texto (ERRATA-004).

Acao sugerida: captura das telas Tips in-app (botao "?" de cada tela de batalha) — a Gameplay FAQ oficial diz explicitamente que lá estão as regras; sem ancora digital publicável.

## Citacao obrigatoria (aceitação 4)

- Deck **legal**: o veredicto cita `DECK-001 + DECK-002 + DECK-003 + DECK-004 + EVOL-002`, mais `EVOL-001` quando o deck tem Pokemon de estagio e `REST-001` quando ha restricao declarada na ficha. Nenhuma regra NAO VERIFICADA entra no veredicto de legalidade.
- Deck **ilegal**: o veredicto lista cada regra violada com `rule_id` + mensagem.

## Notas de implementacao (fidelidade codigo x registry)

- **DECK-002 (F8b, 2026-10-19, card t_f29d4466)**: implementacao em
  `scripts/validate_deck.py` com DUPLA dimensao, ambas obrigatorias —
  (i) por identidade mecanica (card_id): nenhuma entrada isolada > 2 copias;
  (ii) por NOME canonico (`cards.canonical_name`): soma das copias de TODAS
  as entradas e TODAS as identidades do mesmo nome. Motivo: a ficha/registry
  registra "Max 2 copias por nome" — no jogo real, 2x Gastly (Mega Rising)
  + 1x Gastly (Genetic Apex) = 3 cartas Gastly = ILEGAL. O veredicto cita
  DECK-002 como violada com a soma por nome na mensagem.
- **EVOL-001 (F8b)**: o pre-requisito declarado na ficha e por NOME
  ("Evolves from Gastly"). O validador aceita o pre presente por card_id OU
  por nome canonico equivalente (quando o catalogo amarra por id em
  `card_evolutions`), mantendo a cadeia do deck coerente.
- **EVOL-001 (F3b, 2026-10-19, card t_87df73e6)**: a checagem passa a cobrir
  o stage `mega_ex` — a cadeia Mega exige o pre-requisito da ficha pelo
  nome/id, no mesmo principio evolutivo de stage1/stage2. Base: ERRATA-002
  (Mega Evolution Pokemon ex, debut Mega Rising 29/10/2025) — a mega nao é
  um Basico autossuficiente: evolui (ver card_evolutions; ex.: Mega Gengar ex
  B2b/39 <- Haunter). Deck feito a mao com Mega ex orfao agora e ILEGAL.
  Revalidacao auditada dos deck_specifications no mesmo commit: 2 specs
  ilegais removidos com trilha em audit_logs (deck-mega-gengar-ex-001 e
  deck-mega-blaziken-ex-001, ambos sem o pre no deck).

## Notas de mecanica (nunca presumir do TCG fisico)

- Energy Zone fornece 1 Energy por turno; deck nao leva cartas de Energia (oficial).
- Pokemon ex no Pocket: pontos vindos do texto da ficha (ex = 2; Mega Evolution ex = 3). Nao existe limite geral de "ex" por deck; REST-001 aplica a restricao só quando declarada na ficha.
- Sem mulligan por falta de Basico (deducao da Gameplay FAQ): construir deck com Basico é regra de construção (EVOL-002), não de mao.
- Multi-impressao (F4): texto é copiado por identidade mecânica (mechanical_hash), não por impressão.
