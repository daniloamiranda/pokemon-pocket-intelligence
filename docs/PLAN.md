# Pokémon TCG Pocket Intelligence System — Plano de Projeto (Fase 2-T1 · PLAN)

**Documento:** PLAN executável do projeto
**Owner:** leia_organa (PMO) — task `t_bb9a154c` (F2-T1)
**Data de emissão:** 2026-10-18 · Versão 1.0
**Fonte de verdade:** `docs/FASE1-DIAGNOSTICO.md` (auditado; intocado)
**Board:** `pokemon-pocket` (kanban nativo Hermes) — espelho vivo do plano
**Jev (DEC-0008):** `jev_batteries: required` — bateria `delegate` executada em 2026-10-18: decisão `act` (confidence 0.97, gate 0.90), roteamento `owner_self`; nouls `on_critical_path` 0.55 e `blocked_by_dependency` 0.32 — monitorados por DEC-0007, sem escalonamento imediato. Registro bruto em `/opt/data/pokemon-pocket/tmp/jev_delegate.out`.
**Enquadramento:** R2 — escrita apenas em `/workspace/ARCOS/projetos/pokemon-pocket-intelligence`

---

## 1. Visão Geral

| Item | Conteúdo |
|---|---|
| Objetivo | Sistema de inteligência para o Pokémon TCG Pocket: catálogo canônico em SQLite (FTS5/WAL/foreign_keys), validador de legalidade, reconhecimento por imagem, metagame de torneios via Limitless API, deck builder e deck evaluator, culminando no cenário de aceitação Mega Gengar ex executado e homologado ponta a ponta. |
| Horizonte | 2026-10-18 a 2026-11-13 (marcos por fase na Seção 5). |
| Status geral | AMARELO — F1 concluída com evidência; F2 em execução (tony_stark); F3–F10 enfileiradas com dependências formais; decisão D1 (OAuth Google) pendente afeta só a modalidade "Sheets" da F5. |
| Cenário de aceite | Seção 17 do escopo: deck competitivo com Mega Gengar ex + análise do meta + variante por imagem. Homologação independente na F10. |

---

## 2. Fases — Entregáveis, Dependências, Owners e Gates

Regra de Ouro 1: um card = um owner técnico nomeado. Regra de Ouro 2: nenhum card entra em progresso sem escopo fechado e entradas disponíveis (DoR).

| Id | Fase | Card (status) | Owner | Depende de | Entregáveis | Gate (critérios de saída) |
|---|---|---|---|---|---|---|
| F1 | Diagnóstico | (sem card próprio; documentado) | nick_fury | — | `docs/FASE1-DIAGNOSTICO.md` + evidências | Documento auditado com cenário Mega Gengar ex |
| F2 | Arquitetura: contratos JSON + migrations SQLite | `t_028fced4` (running) | tony_stark (CTO); execução: Flynn Carsen (DB) e Doutor Estranho | F1 | `contracts/*.json`; `database/migrations/0001_init.sql`; runner idempotente; `docs/DATABASE.md` | 12 contratos validam por JSON Schema; banco criado do zero; segunda execução idempotente; PRAGMA foreign_keys=ON, WAL e FTS5 funcionando; teste de migração + integridade; commit |
| F3 | Skill pokemon-pocket-rules + validador | `t_d984f234` (todo) | tony_stark | F2 | skill via `skill_manage`; registry de regras (ID + fonte + vigência); validador com fixtures | Validador reprova os 6 casos obrigatórios e aprova deck de fixture; suite verde com saída real; nenhum deck aceito sem citar a regra |
| F4 | Catálogo: coletor Limitless + carga SQLite | `t_39416151` (todo) | tony_stark; coletor: Doutor Estranho | F2 (F3 entra na validação da carga) | coletor de `pocket.limitlesstcg.com` (browser real, rate limit conservador, UA identificado); upsert com `source_id/collected_at/verified_at`; separação identidade mecânica × impressão | Ao menos 95% dos registros dos 24 conjuntos (4.317 registros); Mega Gengar ex com 5 impressões e 1 identidade; zero duplicação por (set, number); coletor reexecutável; relatório de cobertura com lacunas |
| F5 | Google Sheets via Composio + sincronização | `t_f3da6e2e` (todo) | tony_stark; execução: c3po (credencial Composio) | F2 + F4 | planilha; abas do diagnóstico §9; sync incremental com `sync_jobs/sync_changes`; whitelist de colunas de retorno | Planilha acessível com URL real; sync de lote real provado por leitura de volta; reexecução sem duplicar; falha de rede deixa fila `pending`; plano B local `.xlsx/.csv` sem OAuth |
| F6 | Skill card-vision (imagem para carta) | `t_7f2650c1` (todo) | tony_stark | F2 + F4 | pipeline de reconhecimento (navegador + FTS5) com desambiguação | Reconhece conjunto de teste; diferencia impressões da mesma identidade mecânica; imagem ruim retorna "incerto" com motivo; confiança reportada |
| F7 | Skill meta-analyzer (Limitless API, snapshots, tiers) | `t_04f33c18` (todo) | tony_stark | F2 + F4 | integração Limitless Developer API (placings, decklists, matches, webhooks); snapshots históricos; validação cruzada | Coleta real datada (n eventos e n decklists); snapshot gravado; leitura de período 7/14/30 dias; tiers com metodologia documentada; "sem evidência" quando a amostra não bastar; `docs/SOURCES.md` atualizado |
| F8 | Skill deck-builder | `t_89d318e2` (todo) | tony_stark | F2 + F3 + F4 (F7 enriquece) | análise da carta principal; sinergia mecânica justificada; lista de 20 cartas validada pela F3 | Deck legal para ao menos 3 cartas principais diferentes; justificativa mecânica por carta; persistência em `decks/deck_cards`; nenhuma carta inventada |
| F9 | Skill deck-evaluator | `t_3afdfbcb` (todo) | tony_stark | F2 + F7 + F8 | dimensões com pesos documentados; nota 0–100 (não é winrate); matchups com nível de confiança | Nota reproduzível; matchups com amostra real ou selo de teórico; relatório comparando deck criado com o meta real; persistência em `deck_evaluations` |
| F10 | Homologação independente + cenário Mega Gengar ex | `t_5592aa3e` (todo) | hermione_granger (QA independente) | F5 + F6 + F7 + F8 + F9 | bateria da seção 18 do escopo; cenário 17 com variante por imagem; relatório de homologação | Veredito e evidência por item; saída real colada no card; persistência comprovada; causa raiz por reprovação; parecer com riscos residuais |
| GATE | Licença e publicação | `t_f6f9e508` (todo) | Proprietário (human_owner) | F10 | decisão de licença; varredura de segredos; autorização explícita | licença definida; histórico limpo; aceite registrado; repositório remoto criado só depois |

Decisão D4 (times e owners): resolvida por este plano — tony_stark (donos técnicos das Fases 2 a 9), hermione_granger (gate QA da F10), Proprietário (GATE), leia_organa (cronograma).

---

## 3. Decisões pendentes do Proprietário — status no plano

| Decisão | Situação | Efeito no plano |
|---|---|---|
| D1 — OAuth Google Sheets | Pendente | Bloqueia só a modalidade "Sheets" da F5; plano B de espelho `.xlsx/.csv` permite avançar sem OAuth |
| D2 — Diretório do projeto | Resolvida de fato | Estrutura já existe com git e diagnóstico |
| D3 — Escopo competitivo (API key, projeto público) | Pendente | F7 inicia em modo sem chave dentro do rate limit; API key é decisão de negócio do Proprietário |
| D4 — Times e owners | Resolvida pelo PLAN (Seção 2) | Sem efeito pendente |
| D5 — Automação (cron/watchdog) | Cancelada para esta fase | Escopo da F2-T1 proíbe criar cron; decisão volta ao Proprietário quando a operação contínua for exigida |
| D6 — Idiomas (inglês canônico + pt-BR via TCGdex) | Pendente | Plano assume inglês canônico (alinha com §8 do diagnóstico); pt-BR entra como enriquecimento via TCGdex |

---

## 4. Caminho Crítico (CPM)

```
F1 (ok) - F2 - F3 - F4 -+-> F5 ----------------+---> F10 -> GATE
                        +-> F6 ----------------|
                        +-> F7 -> F8 -> F9 ----+(F9 depende de F7 e de F8)
```

Cadeia determinante (zero folga): **F2 → F3 → F4 → F8 → F9 → F10 → GATE**.

- Atraso em qualquer fase dessa cadeia desloca o fim do projeto.
- F5/F6 têm folga até o início da F10; se F4 atrasar mais de uma semana, elas voltam ao caminho crítico.
- F7 alimenta F9 pelas tabelas de meta; F8 e F9 compartem o mesmo owner técnico (tony_stark) — protegido pela mitigação R-09.

---

## 5. Marcos (datas alvo a partir de 2026-10-18)

| Marco | Data alvo | O que prova | Libera |
|---|---|---|---|
| M2 | 2026-10-21 | contratos e migration 0001 versionados | F3, F4 |
| M3 | 2026-10-24 | validador reprova os 6 casos e aprova fixture | F4, F8 |
| M4 | 2026-10-29 | catálogo com cobertura declarada e lacunas | F5, F6, F7, F8 |
| M5 | 2026-11-03 | sync idempotente provado por leitura de volta | F10 |
| M6 | 2026-11-05 | imagem para carta com desambiguação | variante por imagem da F10 |
| M7 | 2026-11-07 | metagame coletado com tiers e metodologia | F9, F10 |
| M8 | 2026-11-10 | ao menos 3 decks legais com justificativas | F9, F10 |
| M9 | 2026-11-11 | deck avaliado e comparado ao meta | F10 |
| M10 | 2026-11-13 | cenário Mega Gengar ex ponta a ponta homologado | GATE |

Deslize superior a 2 dias em um marco do caminho crítico aciona replanejamento formal com nick_fury (Regra de Ouro 6).

---

## 6. Riscos e Mitigação

| # | Risco | Impacto | Probabilidade | Mitigação |
|---|---|---|---|---|
| 1 | Mudança de DOM no Limitless | Alto | Média | Contrato de extração versionado; testes-golden; detecção de quebra no coletor |
| 2 | OAuth Google pendente (D1) | Médio | Alta | Plano B local `.xlsx/.csv` com paridade de conteúdo; Sheets entra quando autorizado sem mudar arquitetura |
| 3 | Rate limit sem API key (D3) | Médio | Média | Fila com backoff; snapshot serve períodos longos; cruzamento com untapped e pokemontcgpocket.app |
| 4 | Datasets comunitários defasados ou sem licença | Alto se canônico | Baixa | Nunca canônicos; enriquecimento auditado; consistência entre tabelas no gate de QA |
| 5 | Ambiguidade estatística (popularidade não é desempenho) | Médio | Média | Metodologia do pokemontcgpocket.app; "sem evidência, sem tier"; amostra citada |
| 6 | Fronteira Pocket vs TCG físico | Alto | Baixa | pokemontcg.io descartado; legalidade Pocket validada antes de qualquer deck |
| 7 | Risco jurídico de imagens | Alto | Baixa | Armazenar URL e metadados, nunca a arte; ATTRIBUTION no GATE |
| 8 | Drift interno entre arquivos de fontes | Médio | Baixa | Teste de consistência entre tabelas no gate de QA |
| 9 | Sobrecarga de tony_stark (8 fases técnicas) | Alto | Alta | Flynn Carsen e Doutor Estranho assumem execução por fase; revisão do CTO mantida; ajuste de capacidade se M4 deslizar |
| 10 | Autor-avaliação na homologação | Médio | Baixa | hermione_granger é gate formal; quem implementou não homologa |

---

## 7. Checklists de Aceite por Fase

- F2: contratos validam JSON Schema; migrate cria do zero; idempotente; PRAGMAs ok; teste cobre migração e integridade; commit.
- F3: skill carregável; registry com ID e fonte; 6 casos reprovados com evidência; fixture aprovada; deck jamais aceito sem citar regra.
- F4: cobertura contada por conjunto; Mega Gengar ex com 5 impressões e 1 identidade; zero duplicação por (set, number); relatório com lacunas; coletor idempotente.
- F5: URL real; abas do §9; cabeçalho congelado e filtros; sync com leitura de volta; reexecução sem duplicar; fila pending em falha.
- F6: conjunto de teste reconhecido; impressões explicadas; imagem ruim declarada incerta; confiança reportada.
- F7: coleta datada; leitura 7/14/30; tiers com metodologia; Mega Gengar ex sem evidência quando for o caso; SOURCES atualizado.
- F8: 3 ou mais cartas principais geram deck legal; justificativa mecânica por carta; persistência; nenhuma carta inventada.
- F9: nota reproduzível com pesos; matchups com amostra ou selo teórico; comparação com meta real; persistência.
- F10: veredito e evidência por item; saída real colada; persistência comprovada; causa raiz; riscos residuais.
- GATE: licença; varredura de segredos; autorização em prosa; repositório remoto somente após aceite.

---

## 8. Mapeamento Card x Fase (aceitação 2 do envelope)

| Card | Título | Fase |
|---|---|---|
| `t_028fced4` | F2 · Estrutura, contratos JSON e migrations SQLite | F2 |
| `t_bb9a154c` | F2 · Plano de fases, marcos e caminho crítico (esta task) | F2 (artefato PLAN) |
| `t_d984f234` | F3 · rules + validador | F3 |
| `t_39416151` | F4 · Catálogo | F4 |
| `t_f3da6e2e` | F5 · Sheets e sync | F5 |
| `t_7f2650c1` | F6 · card-vision | F6 |
| `t_04f33c18` | F7 · meta-analyzer | F7 |
| `t_89d318e2` | F8 · deck-builder | F8 |
| `t_3afdfbcb` | F9 · deck-evaluator | F9 |
| `t_5592aa3e` | F10 · Homologação | F10 |
| `t_f6f9e508` | GATE · aceite do Proprietário | GATE |

Cobertura: 11 de 11 cards mapeados. Nenhuma fase sem card; nenhum card fora do plano.

---

## 9. Registro Jev da bateria da F2-T1

- Bateria `delegate` executada em 2026-10-18, modelo pinned `typesafe/jev-1.13`.
- Resultado: decision `act` (confidence 0.97 maior ou igual ao gate 0.90); probabilidades: `owner_self` 0.98, `owner_tony` 0.02, `owner_nick` 0.00; nouls: `on_critical_path` 0.55, `blocked_by_dependency` 0.32.
- Postura: Jev é advisory; a cadeia decide. Prossegui como PMO. Nouls em zona de atenção (0.40-0.60) exigem monitoramento do caminho crítico — se M2 ou M4 deslizarem mais de 2 dias, escalonar a nick_fury em até 1 ciclo (DEC-0007).
- Auditoria: o Auditor Periódico Jev (segunda, 08:30) pode rodar `verify` sobre este documento.

---

## 10. Ações do PMO nos próximos ciclos

1. Acompanhar `t_028fced4` (F2 do CTO) até M2 (2026-10-21).
2. Cobrar no GATE (`t_f6f9e508`) as decisões D1 e D3, que desbloqueiam as modalidades finais de F5 e F7.
3. Se M4 deslizar, replanejar formalmente com nick_fury antes de comprometer as datas finais.
4. Espelho vivo: fechamento de cada marco significa o card correspondente mudando de status no board; atraso é visível no `kanban_show` de cada card.
