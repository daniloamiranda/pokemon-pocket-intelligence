# TESTING.md — Suite de testes e ambiente (F5e)

A suite do projeto roda VERDE em qualquer interprete: no python3 do sistema
os casos dependentes do SDK Composio sao PULADOS com motivo explicito; no
venv rodam de fato. **Suite "vermelha" sem defeito de codigo nao e aceitavel**
(defeito F5e: ate 18/10 a suite dava ERROR fora do venv).

## 1. Como rodar a suite

```bash
# padrao do projeto (venv — todos os casos rodam):
/opt/data/f5_venv/bin/python3 -m unittest discover -s tests/unit -v
# Esperado: Ran 63 tests ... OK

# interprete do sistema (auditoria rapida — casos SDK-dependentes pulam com motivo):
python3 -m unittest discover -s tests/unit -v
# Esperado: Ran 63 tests ... OK (skipped=3)
#   skipped 'SDK composio ausente (venv) — ver docs/TESTING.md'
```

E2E de visao (quando as fixtures estao no disco):

```bash
python3 -m unittest discover -s tests/vision -v
```

Sem fixtures (`scripts/vision/fetch_fixtures.py`), os casos de imagem PULAM
com motivo claro (ver docs/INSTALLATION.md paragrafo 3).

## 2. Requisito de ambiente: SDK Composio (venv)

O modulo `integrations/google-sheets/sync.py` depende do SDK
`composio==0.22.0` (instalado apenas em `/opt/data/f5_venv`). Se o interprete
nao tiver o SDK:

- `sync.py` IMPORTA sem quebrar (guarda `try/except ImportError` desde o F5e);
  `client()` falha tarde com mensagem clara apontando para este documento;
- os testes que importam esse modulo PULAM com o motivo acima.

Criar o venv do zero (auditor novo sem `/opt/data/f5_venv`):

```bash
python3 -m venv /opt/data/f5_venv
/opt/data/f5_venv/bin/pip install composio==0.22.0
```

O venv e um detalhe de AMBIENTE, nao um artefato versionado. Credenciais
(`COMPOSIO_API_KEY`) ficam no .env do perfil c3po — nunca no repo
(docs/SYNC.md).

## 3. Interprete correto por fluxo

| Fluxo | Interprete | Por que |
|---|---|---|
| Suite unitaria (unidades puras) | qualquer | SDK-dependentes pulam |
| Suite completa (prova de ambiente venv) | `/opt/data/f5_venv/bin/python3` | 0 skipped por SDK |
| export_catalog.py / resync (Google Sheets) | `/opt/data/f5_venv/bin/python3` | precisa do SDK Composio |
| Coleta/migracao/catalogo/schema | `python3` (sistema) | stdlib only |

## 4. Bancos de producao NAO sao requisito de teste

NENHUM teste de unidade exige `data/pocket.sqlite` ou `data/sync_state.sqlite`
REAIS para passar (a suite e verde com eles AUSENTES — provado no F5e
movendo os dois fora da arvore):

- ledger: reconstruido DO ZERO em tmp isolado via `F5D_LEDGER_DB`
  (`test_f5d_ledger_cache.LedgerTmpCatalogFreeTest`);
- historico real (quando `data/sync_state.sqlite` existe): lido de COPIA
  read-only em tmp (`HistoricoRealReadOnlyTest`), nunca no vivo;
- canonico (`data/pocket.sqlite`): testes usam skip quando ausente e leitura
  `mode=ro` quando presente — NENHUM teste escreve nele;
- evaluator F9 (`test_f9_deck_evaluator.py`, BUG-002 card t_91d448dd): roda
  contra COPIA EFEMERA do canonico via backup API em tmp — `persist=True`
  escreve na copia, nunca no original; sem banco no checkout o caso PULA
  (a suite jamais fabrica `data/pocket.sqlite` vazio);
- E2E de visao usa fixtures locais baixadas do CDN — nunca a planilha nem a
  producao (ver `test_f6_card_vision.py`).

Prova da classe (guarda BUG-002, secao 9): um run COMPLETO da suíte de hoje
deixa `data/pocket.sqlite` byte-intocado (md5 antes == depois) e o evaluator
so aceita escrita no caminho canonico com `BUG002_ALLOW_PERSIST=1` no
ambiente (intent do operador humano; agregadores passam a chancelar).

Escrita em producao (export_catalog, sync Google Sheets) fica FORA da suite
de testes — a suite nunca toca a planilha viva nem os bancos de producao.

## 5. Guarda anti-divergencia de skills (F12 — instalada = versionada)

O contrato **"skill no repo = skill instalada"** e vigiado por teste na suite:
`tests/unit/test_f12_skills_guard.py` roda o proprio
`scripts/install_skills.sh --verify` e compara a ARVORE COMPLETA de arquivos
(nao so o SKILL.md) de cada skill do repo com a copia canonica
(`/home/hermes/.hermes/skills/`) e com cada perfil-alvo (`tony_stark`,
`hermione_granger`, `leia_organa`, `c3po`). Arquivo divergente, ausente ou
EXTRA no destino reprova a suite.

```bash
# verificacao direta (o que a suite executa por tras do teste):
bash scripts/install_skills.sh --verify
# Esperado: "hash unico verificado: ok (readiness: available)" e rc=0.
```

**REGRA (aprendida as teimosas — F3, F6 e F7-F9 repetiram a mesma classe):**
skill editada no repo exige REDISTRIBUICAO + verify antes do aceite:

```bash
bash scripts/install_skills.sh          # copia repo -> canonica + perfis
bash scripts/install_skills.sh --verify # rc=0 obrigatorio no aceite
```

Detalhes que a F12 fixou na raiz:

- O instalador NUNCA herda `HERMES_HOME` do shell (o shell do agente aponta
  para o proprio perfil — foi isso que criou a arvore fantasma
  `profiles/tony_stark/profiles/` na era F7-F9, com "instalacao ok" na raiz
  errada). A raiz canonica e fixa: `/home/hermes/.hermes`; override explicito
  apenas via `HERMES_ROOT_SKILLS` (fail-fast rc=3 se a raiz nao existir).
- A comparacao cobre a arvore completa (`references/`, `weights.json`, etc.) —
  drift em arquivo auxiliar tambem e instalacao parcial.
- O teste da guarda e SOMENTE LEITURA: a suite nunca instala nada. Sem a raiz
  canonica no host (checkout cru), o caso pula com motivo explicito.
- Prova de falha (19/10/2026): tamper de 1 linha na copia do perfil c3po ->
  verify rc=1 (`FALHA ...@c3po ... divergente`), guarda rc=1 na suite apontando
  `pokemon-pocket-card-vision@perfil:c3po: SKILL.md divergente`; restore ->
  verify rc=0 e suite verde de novo.

## 6. Skill card-database (F13 — consulta e atualizacao do catalogo)

A 6a skill obrigatoria do escopo (secao 3.2) existe e esta instalada:
`skills/pokemon-pocket-card-database/` — envolve as ferramentas canonicas
(`scripts/db_query.py` read-only, `scripts/collect_pocket.py --dry-run`,
`scripts/db_migrate.py --status`), nunca reimplementa coleta. Os testes da F13
(`tests/unit/test_f13_card_database_skill.py`, 12 casos) sao SOMENTE LEITURA:

- consulta confere com leitura SQL direta independente (24/2.319/4.317 no
  aceite; piso monotônico — coleta aditiva so cresce);
- dry-run: prova temporal (< 1.2s, menos que UMA requisicao do rate limit) e
  mtimes de `data/pocket.sqlite` + `data/collection_report.json` intocados;
- declaracao da skill: frontmatter com `license: MIT` (decisao do Proprietario
  aplicada pela F14 — secao 7), related_skills resolvendo para skills reais e
  `gen_contracts.py` citando a skill em >= 4 contratos;
- instalacao continua vigiada pela guarda F12 (secao 5), que itera o repo
  dinamicamente — a 6a skill entra sem lista fixa.

Sem o catalogo em `data/pocket.sqlite`, os casos dependentes de banco PULAM
com motivo explicito (dependencia de ambiente, nao defeito); os casos de
declaracao rodam em qualquer checkout.


## 7. Guarda de licenca (F14 — MIT no codigo, identidade com o LICENSE da raiz)

Contrato da decisao do Proprietario (19/10/2026): o CODIGO e MIT (`LICENSE` na
raiz) e as SEIS skills declaram `license: MIT` no frontmatter. A guarda
`tests/unit/test_f14_license_guard.py` reprova a suite quando:

- o `LICENSE` da raiz desaparece ou tem identificador nao reconhecido
  (mapa minimo da guarda — identificador novo exige atualizacao consciente
  dela, nada de drift silencioso);
- SKILL.md do repo declara licenca AUSENTE ou divergente (ex.:
  `proprietary` de era anterior);
- copia instalada (canonica + perfis `tony_stark`, `hermione_granger`,
  `leia_organa`, `c3po`) declara licenca divergente do `LICENSE` da raiz —
  cobra a classe `copia de perfil antiga`, complementar a guarda F12
  (secao 5, que compara a arvore inteira).

```bash
# verificacao direta (o que a suite executa por tras do teste):
python3 -m unittest tests.unit.test_f14_license_guard -v
# Esperado: Ran 3 tests ... OK
```

Prova de falha (19/10/2026): `license: "proprietary"` na copia do perfil
c3po -> guarda rc=1 nomeando `pokemon-pocket-rules@perfil:c3po: license
'proprietary' != raiz 'MIT'`; restauracao byte-exata (hash 857b25758cd8...
confirmado) -> rc=0 e `install_skills.sh --verify` verde de novo. O teste e
SOMENTE LEITURA e itera `skills/` do repo sem lista fixa — skill nova entra
por iteracao.


## 8. Guarda de deck_id (F15+ — serie furada nao gera colisao)

O deck-builder (`scripts/deck/build_deck.py`) derivava o proximo deck_id de
COUNT(*)+1 sobre o slug — contagem nao e sequencia: a revalidacao F8b furou
a serie `deck-mega-gengar-ex-%` (restaram 002/003) e o COUNT+1 recalculava
o 003 JA existente -> `sqlite3.IntegrityError` no comando canonico do
cenario 17 (BUG-001 do reteste F15; repro 2/2 da QA + reproducao
independente do CEO em 19/10, producao intocada). O proximo id agora deriva
do MAIOR sufixo existente (`MAX(CAST(substr(id,-3) AS INTEGER))+1` por slug)
com guarda de colisao residual (sufixo incrementa em vez de crashar).

A guarda `tests/unit/test_f15plus_deckid_guard.py` (6 casos, banco EFEMERO
em memoria com o DDL real de producao — a suite nao escreve nem exige
`data/pocket.sqlite`) cobre a classe do defeito: buraco real de producao
(002/003) gera 004; build -> apagar registro abaixo do max -> build de novo
gera id DISTINTO (o codigo antigo reprova com IntegrityError aqui — prova
vermelho/verde real); serie vazia reconstroi sem colisao; builds seguidos
geram ids distintos; deck_cards nao duplica e irmaos ficam intocados; e o
fonte nao reassume o antipattern COUNT-como-sequencia.

```bash
python3 -m unittest tests.unit.test_f15plus_deckid_guard -v
# Esperado: Ran 6 tests ... OK
```


## 9. Guarda BUG-002 (F15+): producao byte-intocada apos um run COMPLETO da suite

O reteste F15 (card t_3539dc38 -> diag. no t_fd4343fb) descobriu que a suite
F9 escrevia no banco de producao: `test_12`/`test_30` chamavam
`E.evaluate(..., persist=True, db_path=producao)` — cada run gravava 1 insert
de recusa + 2 upserts de avaliacao em `audit_logs`/`deck_evaluations
(ator `tony_stark:f9`; exemplo real: overall_score 7.98 re-upsertado 12x em
4 runs, updated_at a cada ciclo, sem corrupcao de conteudo) e o md5 do
arquivo oscilava por churn de WAL checkpoint SEM mudanca logica. Isso
contradizia esta secao 4. Collateral: `setUpClass` conectava
`sqlite3.connect(str(DB))` direto na producao — em checkout cru CRIA
`data/pocket.sqlite` vazio.

Fix (commit BUG-002):

- `scripts/eval/evaluate_deck.py` ganha `open_eval_db()`: banco ausente
  levanta `RuntimeError` ANTES de criar arquivo (nada de sqlite vazio
  fabricado), e `persist=True` no caminho canonico recusa com `RuntimeError`
  por default — escrita deliberada em producao exige
  `BUG002_ALLOW_PERSIST=1` no ambiente (operador/agregador como intencao
  explicita); copias e bancos de homologacao ficam livres;
- `tests/unit/test_f9_deck_evaluator.py` copia o canonico para tmp via
  sqlite3 backup API (`setUpClass`), roda persist=True REAL na copia, e
  PULA com motivo se o banco nao existe (checkout cru);
- `_tmp_spec()` escreve specs temporarias em tmpdir do SISTEMA, nao dentro
  de `data/` (residuo `.json` de run anterior era lixo no diretorio de
  producao).

A guarda `tests/unit/test_f15plus_prod_guard.py` cobre a classe
(SOMENTE LEITURA sobre producao):

- run COMPLETO da suite inproc `md5(data/pocket.sqlite)` ANTES == DEPOIS e
  nenhum residuo `-wal/-shm` criado na hora do run em `data/`;
- `open_eval_db()` recusa persist canonico sem a chave e fail-fast com
  banco ausente (prova em tmp, nunca em producao: passa caminho inexistente);
- a chave `BUG002_ALLOW_PERSIST` so existe no docstring/contrato do
  evaluator — nenhum teste da suite seta a variavel (a suite NUNCA opta por
  escrita em producao).

```bash
python3 -m unittest tests.unit.test_f15plus_prod_guard -v
# Esperado: Ran 4 tests ... OK (subprocesso da suite full vem mais tarde)
```

## 10. Guarda rules_refresh (t_fafb754f): Firecrawl e manutencao, nunca runtime

Decisao do Proprietario (19/10): a base de regras (docs/RULES.md) e estatica
e local; o Firecrawl/Composio e ferramenta de MANUTENCAO acionada SOB DEMANDA
manual (`scripts/rules_refresh.py`), nunca dependencia de runtime. A guarda
`tests/unit/test_rules_refresh.py` (17 testes) cobre:

- fluxo do maintainer SEM REDE (`--offline` injeta captura): primeira captura
  = linha de base (codigo 0); sem mudanca = codigo 0 com snapshot byte-intocado
  (zero escrita); mudanca = codigo 10 com secoes afetadas (`## `) e diff;
  captura vazia/curta/sem estrutura/HTTP != 200 = codigo 4 e NUNCA vira
  snapshot (erro declarado, nunca "sem mudanca");
- sem conexao Composio/Firecrawl = codigo 3 com instrucao de reconexao,
  provado SEM rede (falha na credencial antes de qualquer SDK);
- GREP de guarda: `validate_deck.py`, `build_deck.py` e `evaluate_deck.py`
  sem nenhum padrao de rede/Firecrawl/Composio (runtime 100% offline) e o
  propio maintainer sem libs de rede diretas nem agendamento embutido.

```bash
/opt/data/f5_venv/bin/python3 -m unittest tests.unit.test_rules_refresh -v
# Esperado: Ran 17 tests ... OK (idem no interprete do sistema)
```

