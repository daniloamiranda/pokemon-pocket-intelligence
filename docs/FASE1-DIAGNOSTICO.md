# Pokémon TCG Pocket Intelligence System — Fase 1: Diagnóstico de Ambiente e Fontes

**Documento:** Relatório de Investigação (Fase 1)
**Data da coleta:** 18 de outubro de 2026, 16:41–16:45 (-03)
**Executor:** Nick Fury (Orquestração Executiva) — coleta por ferramenta real, sem dados estimados
**Status:** Fase 1 concluída. Fase 2 (arquitetura/estrutura) **não iniciada** — aguarda autorização do Proprietário (regra ARC-OS: não criar pastas fora do padrão sem autorização prévia).
**Diretório de evidências (provisório):** `/opt/data/pokemon-pocket/evidence/`

---

## 1. Diagnóstico do ambiente Hermes

| Item | Resultado verificado |
|---|---|
| Host / SO | Linux 5.15.0-191-generic x86_64 |
| Python | 3.13.5 (sem módulo `pip`; PEP 668 ativo; `uv` instalado em /usr/local/bin) |
| SQLite (biblioteca) | 3.53.4 via `python3 -c "import sqlite3"` |
| SQLite CLI | **AUSENTE** (`sqlite3` não existe no PATH) → todo acesso será via Python |
| Ferramentas | `git`, `curl`, `uv`, `node` presentes |
| Armazenamento | `/workspace` e `/opt/data` no MESMO volume `/dev/sda3` — 490G, 56G usados, **409G livres** (persistente, não efêmero) |
| Perfis Hermes | 33 perfis em `/home/hermes/.hermes/profiles/` (isolamento por agente) |
| HOME Hermes | `/home/hermes/.hermes` (SSOT de skills, cron, kanban, memórias) |

**Recursos SQLite verificados por teste real:**
- FTS5: **SUPORTADO** (busca textual de nomes/efeitos de cartas é viável nativamente)
- `journal_mode=wal`: **OK**
- `foreign_keys=ON`: **OK** (integridade referencial viável)
- Soma disponível para o banco: 409 GB — folga total para catálogo, histórico de meta e snapshots.

---

## 2. Estrutura atual de skills

- Diretório de skills instaladas: `/home/hermes/.hermes/skills/` — **37 diretórios de skill**, organizados em subpastas de categoria (`arcsec/`, `productivity/`, `software-development/`, `autonomous-ai-agents/`, etc.), cada uma com `SKILL.md` + frontmatter YAML (name, description, version, metadata.hermes.tags) e arquivos de apoio em `references/`, `scripts/`, `templates/`, `assets/`.
- Criação/edição é feita pela ferramenta nativa **`skill_manage`** (não por criação manual de diretório). Um diretório criado "na mão" não registra a skill.
- Convenção observada nas skills ARCSEC: `description` com gatilho "Use quando/Use ao …" no início + nome em kebab-case.
- **Conclusão:** as 6 skills do projeto serão criadas via `skill_manage`, com `references/` para conteúdo pesado (regras, fontes, contratos) em vez de corpo gigante.

---

## 3. Recursos e integrações disponíveis

**Hermes nativo (já operacional — sem custo de infraestrutura nova):**
- **Kanban nativo**: `/home/hermes/.hermes/kanban.db` — tabelas `tasks`, `task_links`, `task_comments`, `task_events`, `task_runs`, `task_attachments`, `kanban_notify_subs`. É o mecanismo canônico de fila/delegação do Proprietário.
- **Cron nativo**: `/home/hermes/.hermes/cron/` com `jobs.json` + `executions.db` — **13 jobs ativos** hoje, com suportes `cron`, `interval` e `once` (ex.: "ARCSEC Sentinela de Integridade", `every 360m`; "Sentinela ARC-OS — sync 15min"). Não há necessidade de cron do sistema operacional.
- **Watchdog**: padrão já em produção no ecossistema (jobs `watchdog-TASK-0013-tron`, `Watchdog PLAN-0010` — hoje desabilitados). O projeto reutilizará o mecanismo existente, sem inventar um paralelo.
- **Navegador real** (`browser_exec`): necessário e suficiente — o banco de cartas e os sites de meta são renderizados em JavaScript.
- **Delegação multagente** (`delegate_task`) e 33 perfis de especialistas disponíveis.
- **Memória persistente** (Honcho + memory).

**Recursos INDISPONÍVEIS hoje (bloqueio real, não suposição):**
- **Google Workspace / Sheets: NÃO AUTENTICADO.** Não existe `gws`, nem `gcloud`, nem `googleapiclient`/`google.oauth2`/`gspread`/`pandas` instalados; e faltam os arquivos `google_token.json` e `google_client_secret.json` exigidos pela skill `google-workspace`.
- Consequência: **a camada Google Sheets do projeto depende de uma autorização OAuth única do Proprietário** (criar projeto no Google Cloud + OAuth Client "Desktop app" + consentimento). O fluxo é conduzido pela skill `google-workspace` (`scripts/setup.py`), com o segredo digitado em prompt mascarado — **nenhuma credencial passa pelo chat**.
- Plano B técnico (sem Sheets): espelho local `.xlsx`/`.csv` gerado do SQLite, com sincronização real quando a autorização existir.

---

## 4. Avaliação das fontes de cartas

### 4.1 Fonte canônica identificada (nível A)
**Limitless TCG Pocket Database — `pocket.limitlesstcg.com`** (verificado ao vivo)
- `GET /cards` → 200, listagem de **24 conjuntos** com nome, código, data e contagem.
- `GET /cards/{SET}` → 200 (ex.: `B4` "Ruler of the Skies", 233 cartas, 30/07/2026).
- `GET /cards/{SET}/{num}` → 200 com **ficha completa real**: nome, tipo elemental, HP, categoria, estágio, pré-evolução, ataque (custo + dano + efeito literal), fraqueza, custo de recuo, regra especial (ex.: regra Mega Evolution ex), ilustrador, raridade visual e **lista de versões/impressões** da mesma carta.
- Padrão de imagem verificável: `https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/{SET}/{SET}_{NNN}_EN_SM.webp`
- Cobertura até a data de referência: **24 conjuntos / 4.317 registros de carta** (incluindo artes alternativas), último lançamento **B4b "Deluxe Pack: Mega" — 429 cartas, 30/09/2026**.
- **Aviso legal verificado no rodapé:** o texto e as imagens são © The Pokémon Company / DeNA / Creatures; o site declara não ser afiliado. Uso deve ser por link/referência, sem redistribuir assets de imagem como se fossem nossos.

### 4.2 Datasets comunitários testados (candidatos a enriquecimento, não canônicos)

| Fonte | Resultado do teste real | Veredito |
|---|---|---|
| `flibustier/pokemon-tcg-pocket-database` (npm/CDN jsDelivr) | `cards.extra.json` baixado = 805.816 bytes, **2.522 cartas, 15 conjuntos**, para no `B1a`; campos: set, number, name, rarity, image, packs, element, type, stage, health, retreatCost, weakness, goodWith. **Sem ataques/habilidades em texto; sem estágio "mega"; nenhum Mega Gengar.** O `sets.json` do MESMO pacote já lista até `B4b` → **inconsistência interna entre arquivos** | **Reprovado como canônico.** Útil apenas como dado secundário de raridade/pacotes, com quebra de confiança |
| `R4PH1/PTCGP-Data` | Estrutura rica e real: `data/Pokemon.json` (1,35 MB), `Abilities`, `Abilities_detailed`, `AttackEffects`, `Evolutions` (162 KB), `Items`, `Supporters`, `Tools`, `Stadiums`, `Fossils`, `downloads/sets/*.json` (21 conjuntos), `Localizations.json` (traduções). **Último push: 29/05/2026**; conjunto mais novo: `B3a`. **Sem licença declarada**, 0 estrelas | **Bom modelo de schema; reprovado como fonte de verdade** por estar 5 meses atrás e não ter licença |
| `chase-manning/pokemon-tcg-pocket-cards` | URLs do README (`v4.json`, `expansions.json`) retornaram **404** no host testado | **Pendente de reverificação** (repositório pode ter migrado/renomeado). README declara MIT e dados raspados do Limitless |
| **TCGdex** (`api.tcgdex.net/v2`) | API viva (200). O site declara explicitamente **"TCG Pocket Integration"** com suporte a 10 idiomas, **incluindo Português Brasileiro**, jogos/séries/sets | **Investigar na Fase 1b** como fonte estruturada secundária — seria a via para nomes em pt-BR sem scraping |

### 4.3 Política derivada
`pocket.limitlesstcg.com` = **fonte primária de cartas** (contrato completo por carta). Datasets comunitários só entram como *enriquecimento auditado* (raridade, tradução, custo de recuo) e **nunca sobrescrevem** dado canônico sem justificativa registrada. Toda linha carrega `source_id`, `collected_at`, `verified_at` e `validation_status`.

---

## 5. Avaliação das fontes competitivas (metagame)

- **Limitless (fonte-raiz):** `play.limitlesstcg.com/tournaments/?game=pocket` → 200. Todos os sites relevantes declaram **derivar do Limitless** — logo, o Limitless é o dado de origem e os demais são derivados.
- **`pocket.untapped.gg/en/tier-list`** (verificado ao vivo, atualizado ~13 h antes da consulta): **82 arquétipos, 39.000 partidas**. Amostra real lida: Tier A Magnezone/Miraidon ex (54,2% · 3,2% · 2.500 jogos), Mega Altaria ex/Happiny (54,1% · 0,7%), Hoopa ex/Mega Sableye ex (53,1%); Tier B Mega Altaria ex/Espeon (52,1% · **8,4% · 6.600 jogos**); Tier C Mega Lucario ex/Lucario (48,5% · **7,8% · 6.100**); Tier D Mega Altaria ex/Chingling (43,9%). **Nenhuma entrada de Gengar em toda a página.**
- **`pokemontcgpocket.app`** (política de dados exemplar): janela rolante de 30 dias, escopo "public standard Swiss", mínimo de 64 jogadores, mínimo 3 decklists por arquétipo, mínimo 3 jogos por confronto, máximo 30 torneios. Snapshot lido: 30 torneios, 6.247 decklists, 17.005 partidas, **cobertura local de cartas 571/571 = 100%**. É o modelo metodológico a ser adotado na atribuição de tiers.
- **`pocketmeta.app`** (PocketMeta): declara origem Limitless e cálculo próprio de uso/winrate/tier, com tamanho de amostra por página. Ex.: Hoopa ex/Mega Absol ex com 3,7% de share e 219 decks; Mega Altaria ex/Happiny 0,7% em 39 decks (56,6% ajustado) — **amostras diferentes não são confronto direto**.
- **`www.pokemonmeta.com`**: é listado pelo próprio Limitless como aplicação-showcase de tier list/decklists/winrates para Pocket. Porém **a extração estática retornou "Something went wrong... Reload Page"** (app JS) → exige navegador real (o `browser_exec` resolve).
- **`tcgpocketmeta.com`**: resolve como "TCGP Pocket - Pokemon TCG Meta Stats" (Tier List, Matchup Analysis, Deck Statistics, Meta Trends); conteúdo também renderizado em JS, mínimo em HTML estático.
- **`pokedaily.net/tcg/pocket/meta`**: declara agregação do Limitless a cada 6 h ("40 torneios recentes, 3.480 decklists"), mas as páginas exibem período de maio/junho de 2026 → **risco de conteúdo defasado**, usar somente como validação cruzada.
- **`ptcgphub.com/decks`**: 20 decks, formato B4a, atualizado em 02/09/2026.

**Conclusão de governança de fontes:** a arquitetura correta é **coletar do Limitless via API documentada** e usar os agregadores (untapped / pokemontcgpocket.app / pocketmeta.app) apenas como **validação cruzada**, nunca misturando estatísticas de origens diferentes sem normalização (regra 4.6 do escopo).

---

## 6. Disponibilidade de APIs e datasets — o achado mais importante da Fase 1

**Existe API oficial e documentada do Limitless para dados de torneio.**
Fonte: `https://docs.limitlesstcg.com/developer` (200, lido na íntegra)
- Endpoints para **placings, decklists e matches**, mais **webhooks** para torneios finalizados.
- **Não exige API key**, exceto o endpoint `/decks` em `/games`; **rate limits são informados nos headers** da resposta.
- API key é concedida **apenas a projetos públicos com caso de uso legítimo** — explicitamente **não para uso privado**. Existe formulário em `/account/settings/api`; duas formas de envio: query `?key=` ou header `X-Access-Key`.
- **Impacto no projeto:** o caminho sancionado é (a) operar com os endpoints sem chave dentro do rate limit; (b) se precisarmos de volume alto/decklists completos, **submeter o projeto como público** — o que é uma decisão de negócio do Proprietário, não uma escolha técnica.

**APIs/datasets adicionais:** TCGdex v2 (com declaração de integração Pocket, 10 idiomas incl. pt-BR, MIT); datasets comunitários em JSON (flibustier, R4PH1); `pokemontcg.io` responde 200 mas é do **TCG físico/Live**, não do Pocket → **descartado para este projeto** conforme regra 2.1.

**Scraping:** `play.limitlesstcg.com/robots.txt` → 404 (sem restrição declarada); `pokemonmeta.com` e `tcgpocketmeta.com` → robots.txt 200 (a respeitar). Política adotada: **API primeiro; HTML renderizado só onde não existe API, com rate limit conservador, User-Agent identificado e sem redistribuir imagens.**

---

## 7. Proposta de arquitetura definitiva

```
USUÁRIO (Danilo / Telegram)
        │
   ORQUESTRADOR (Nick Fury → delega via Kanban nativo)
        │
   ┌────┴───────────────────────────────────────────┐
   │  pokemon-pocket-rules        (regras/legalidade)│
   │  pokemon-pocket-card-database(catálogo + sync)  │
   │  pokemon-pocket-card-vision  (imagem → carta)   │
   │  pokemon-pocket-meta-analyzer(meta/tiers)       │
   │  pokemon-pocket-deck-builder (sinergia/lista)   │
   │  pokemon-pocket-deck-evaluator(pontuação/matchup)│
   └────┬───────────────────────────────────────────┘
        │  contratos JSON versionados (contracts/)
   ┌────┴───────────────┐
   │ SQLite (canônico)  │  ← WAL + foreign_keys + FTS5 (verificado)
   └────┬───────────────┘
        │ sync incremental (sync_jobs / sync_changes)
        ├──→ Google Sheets (visualização/auditoria) [PENDENTE: OAuth]
        └──→ Exportação local .xlsx/.csv (plano B imediato)
                 ↑
        Coletor: Limitless Developer API (torneios)
                 pocket.limitlesstcg.com (cartas, via navegador)
                 + validação cruzada (untapped, pokemontcgpocket.app, TCGdex)
```

Princípios: SQLite é a **fonte canônica**; Sheets é **interface**, com escrita de retorno restrita a uma **whitelist de colunas**; cada skill é invocável isoladamente; nenhuma skill depende da implementação interna de outra — apenas do contrato.

---

## 8. Modelo relacional inicial do SQLite

**Núcleo de cartas (com separação identidade mecânica × impressão):**
- `expansions` (id, code, name, series, release_date, card_count, source_id)
- `cards` — **identidade mecânica** (id, canonical_name, category, element, stage, evolves_from_id, hp, weakness, retreat_cost, special_rule, mechanical_hash)
- `card_prints` — **impressão/arte** (id, card_id, set_code, number, rarity, artist, image_url, is_promo)
- `card_attacks` (id, card_id, name, energy_cost JSON, damage, effect_text, sort_order)
- `card_abilities` (id, card_id, name, kind, effect_text)
- `card_evolutions` (card_id, pre_evo_card_id, stage)
- `card_localizations` (card_id, lang, name, effect_text)
- `card_legality` (card_id, format, legal, from_date, to_date, reason)

**Regras e validação:** `rules` (id, code, title, description, category, source_id, verified_at, valid_from, valid_to, exceptions, examples)

**Metagame:** `meta_archetypes`, `meta_snapshots`, `archetype_cards`, `tournaments`, `tournament_results`, `matchups`, `tiers`
**Decks:** `decks`, `deck_cards` (com `print_id`), `deck_evaluations`, `evaluation_dimensions`
**Governança de dados:** `sources`, `source_records`, `sync_jobs`, `sync_changes`, `audit_logs`, `schema_migrations`

Índices previstos: `cards(canonical_name)`, FTS5 sobre nome+efeitos, `card_prints(set_code, number)` UNIQUE, `card_attacks(card_id)`, `matchups(archetype_a, archetype_b, period)`.

Convenções: chaves estáveis, `UNIQUE` em chave natural da fonte, **upsert** com preservação de dado completo, `audit_logs` para toda alteração, nenhuma sobrescrita destrutiva.

---

## 9. Estrutura proposta do Google Sheets

Planilha: **"Pokémon TCG Pocket — Intelligence Database"**

- **Camada analítica:** `Dashboard`, `Expansões`, `Fontes`, `Sincronizações`, `Pendências`
- **Camada de catálogo:** `Cartas_Master` (única cadastral) + `Ataques`, `Habilidades`, `Evoluções`, `Treinadores`, `Energias`
- **Abas por tipo (DERIVADAS de Cartas_Master, somente leitura):** Grama, Fogo, Água, Elétrico, Psíquico, Lutador, Sombrio, Metal, Dragão, Incolor
- **Camada competitiva:** `Decks_Meta`, `Decks_Cartas`, `Matchups`, `Tiers`
- **Camada de produção:** `Decks_Criados`, `Deck_Cartas`, `Avaliações`

Formatação: cabeçalhos congelados, filtros, validação de dados em colunas controladas, links para imagem e fonte, data de atualização por aba, indicadores de integridade, proteção das abas derivadas contra edição manual.
**Regra dura:** abas por tipo e abas derivadas **nunca** são cadastros independentes — são regeneradas a partir de `Cartas_Master`/SQLite.

---

## 10. Estratégia de sincronização

- **SQLite → Sheets:** exportação **incremental** por `sync_jobs`/`sync_changes` (log de mudanças com hash de conteúdo), em lotes, com marcação por sheet/tab, retomada idempotente e registro de execução.
- **Sheets → SQLite:** **somente campos da whitelist** (ex.: apelido em pt-BR, nota do usuário, tag de interesse). Fluxo obrigatório: validar → detectar conflito → checar integridade → registrar em `audit_logs` → aplicar em transação. Nenhuma edição manual destrói dado canônico silenciosamente.
- **Offline:** se o Sheets estiver indisponível, as consultas continuam no SQLite; as alterações ficam em fila com status `pending`, sem duplicação (chave natural + hash).
- **Backups:** cópia íntegra do SQLite antes de cada ciclo de sync, em diretório persistente (não temporário), com retenção definida.

---

## 11. Estrutura de diretórios proposta

Caminho proposto (dentro do padrão ARC-OS): `/workspace/ARCOS/projetos/pokemon-pocket-intelligence/`
(hoje `ARCOS/projetos/` contém apenas `laya-poc`; a estrutura abaixo é nova e **depende de autorização**.)

```
pokemon-pocket-intelligence/
├── README.md
├── docs/            ARCHITECTURE, DATABASE, RULES, SOURCES, SKILLS, SYNC, TESTING, USER_GUIDE, CHANGELOG, INSTALLATION
├── contracts/       card.json, card_variant.json, deck.json, matchup.json, evaluation.json, ...
├── database/        migrations/ schemas/ backups/  (schema puro — dado operacional fica em data/pocket.sqlite, F4b)
├── integrations/    limitless/ limitlesstcg-pocket/ tcgdex/ crosscheck/
├── orchestration/   pipelines, registry de skills, políticas de custo
├── tests/           unit/ integration/ fixtures/ golden/
└── scripts/         coleta, validação, sync, auditoria
```
As 6 skills **não** ficarão aqui: vivem em `/home/hermes/.hermes/skills/` (com `references/` apontando para a documentação do projeto), porque é o mecanismo real de descoberta/carregamento do Hermes.

---

## 12. Dependências

**Já disponíveis:** Python 3.13.5 + sqlite3 3.53.4 (FTS5/WAL/foreign_keys OK), git, curl, node, uv, navegador real, Kanban nativo, cron nativo, delegação multiagente.
**A conquistar (com autorização):**
1. **OAuth Google** (Sheets) — ação do Proprietário + skill `google-workspace`.
2. **Cache local de HTML/imagens** — nenhuma biblioteca extra obrigatória (urllib + Python stdlib bastam; `pandas/openpyxl` só se quisermos XLSX nativo — instalação via `uv`, escopo controlado).
3. **API key Limitless** — só se decidirmos expor o projeto publicamente.
**Nunca:** credenciais no Sheets, no chat ou no repositório.

---

## 13. Riscos técnicos

1. **Mudança de DOM no site do Limitless** (cartas são HTML renderizado) → mitigar com contrato de extração versionado + testes-golden + detecção de quebra.
2. **Sem licença/defasagem dos datasets comunitários** → nunca canônicos; auditoria de licença antes de qualquer uso em massa.
3. **Rate limit e ausência de API de cartas** → fila de coleta com backoff e cache local agressivo; uma coleta serve para semanas.
4. **Google Sheets indisponível até o OAuth** → plano B em `.xlsx/.csv` local desde a Fase 5.
5. **Ambiguidade de estatística competitiva** (popularidade ≠ desempenho; amostras pequenas) → política explícita de "sem evidência ⇒ sem tier", herdada do modelo do `pokemontcgpocket.app`.
6. **Fronteira jogo/versão** (Pocket ≠ TCG físico/Live) → validação obrigatória de legalidade no Pocket antes de qualquer deck.
7. **Risco jurídico de imagem** → armazenar URL/link e metadados, não redistribuir arte da TPC.
8. **Drift de dados internos** (visto no npm: `cards` em `B1a` vs `sets` em `B4b`) → teste de consistência entre tabelas deve fazer parte do gate de QA.

---

## 14. Plano de implementação priorizado (revisado pelo diagnóstico)

| Fase | Entrega | Observação pós-investigação |
|---|---|---|
| 1 | Diagnóstico | **CONCLUÍDA** (este documento) |
| 2 | Arquitetura, contratos, migrations, diretórios | Bloqueada só por autorização de diretório |
| 3 | Regras + validador de legalidade | Pode começar imediatamente (fonte: documentação oficial do jogo) |
| 4 | Catálogo (SQLite) com coleta do Limitless | **Acelerada**: fonte canônica já identificada e contrato por carta já mapeado |
| 5 | Sheets + sync | Plano B local até OAuth; Sheets entra quando autorizado |
| 6 | Visão (imagem → carta) | Viável: padrão de imagem e ficha completa já verificado |
| 7 | Meta (Limitless API + snapshots + tiers) | **Acelerada**: API oficial documentada, sem chave |
| 8 | Deck Builder | Depende de 3+4 |
| 9 | Deck Evaluator | Depende de 7+8 |
| 10 | Integração, homologação e cenário Mega Gengar ex | QA independente obrigatório (gate) |

---

## 15. Critérios de aceitação

- Regras documentadas com ID, fonte oficial, data de verificação e exceções.
- Validador rejeitando: tamanho ≠ 20, mais de 2 cópias, carta inexistente, carta ilegal no formato, evolução sem base, restrição específica.
- Catálogo com cobertura **declarada e auditada** (24 conjuntos até 18/10/2026), com lacunas **explicitamente listadas**, IDs únicos, zero duplicação, fonte rastreável por linha.
- SQLite com integridade referencial ativa + FTS5 + backups + migrações versionadas.
- Sheets criado e sincronizado (ou plano B local com paridade de conteúdo), com recuperação demonstrada após falha.
- Reconhecimento de imagem validado, com declaração de incerteza quando aplicável.
- Meta coletado com fonte, data, tamanho de amostra e sem estatística inventada; tiers com metodologia; "sem evidência" quando for o caso.
- Deck Builder produzindo lista **legal** com a carta principal preservada; Evaluator com nota heurística, pesos documentados e matchups com nível de confiança.
- Documentação completa (11 documentos) e cenário **Mega Gengar ex** executado ponta a ponta com persistência comprovada.

---

## Anexo A — Evidência do cenário de aceitação (Mega Gengar ex)

**Verificado em `pocket.limitlesstcg.com` (fonte primária), 18/10/2026:**

- **Nome:** Mega Gengar ex
- **Tipo:** Sombrio (Darkness) · **HP:** 210 · **Estágio:** Stage 2 · **Evolui de:** Haunter
- **Ataque:** "Labyrinth of Shadows" — custo **DDDC** (3 Sombrio + 1 Incolor), **120 de dano**, efeito: *"Durante o próximo turno do seu oponente, ele não pode jogar nenhuma carta de Treinador da própria mão."*
- **Fraqueza:** Lutador · **Recuo:** 1
- **Regra especial:** Mega Evolution ex — quando este Pokémon ex de Mega Evolução é Nocauteado, o oponente ganha **3 pontos**.
- **Impressões (5) — todas mecanicamente idênticas:** B2b Mega Shine #39 (◊◊◊◊), #79 (☆☆), #114 (☆☆); B4b Deluxe Pack: Mega #141 (◊◊◊◊), #419 (☆☆). Ilustradores: PLANETA CG Works / 5ban Graphics.
- **Presença no metagame:** **nenhuma**. A tier list do `pocket.untapped.gg` (82 arquétipos, 39.000 partidas, atualizada ~13 h antes da consulta) **não contém nenhuma entrada de Gengar** → pela metodologia exigida no escopo (item 9.5), **não há evidência suficiente para atribuir tier**. Qualquer análise do deck nesse cenário será explicitamente **teórica**, jamais apresentada como resultado de torneio.

---

## Anexo B — Decisões pendentes do Proprietário

- **D1. Google Sheets:** autorizar o OAuth (Google Cloud + OAuth Desktop + consentimento) ou seguir com espelho local `.xlsx/.csv` por enquanto?
- **D2. Diretório do projeto:** autorizar a criação de `/workspace/ARCOS/projetos/pokemon-pocket-intelligence/`?
- **D3. Escopo de coleta competitiva:** arquitetura pública (habilita API key e decklists completos do Limitless) ou uso estritamente privado nos endpoints sem chave?
- **D4. Times e owners:** confirmar o CTO (tony_stark) como dono técnico da execução, com QA independente (hermione_granger) no gate, e Leia (leia_organa) no cronograma.
- **D5. Automação:** autorizar o registro das tarefas no Kanban nativo e a criação de **um** job de cron (cartas semanal + meta diário) com watchdog, ou manter execução manual nesta fase?
- **D6. Idiomas:** catálogo em inglês canônico + tradução pt-BR (via TCGdex/ROM do jogo) — confirmar preferência.
