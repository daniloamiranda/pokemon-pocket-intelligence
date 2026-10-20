# Protocolo de Sincronizaac eio SQLite -> Google Sheets
Projeto: pokemon-pocket-intelligence
Origem canonica: data/pocket.sqlite
Interface: Google Sheets via Composio v3
Ultima execucao real: 2026-10-19 (F11, job f5b_20261019T123010Z)

## 1. Credencial e escopo (PROIBIDOS)

- A chave COMPOSIO_API_KEY vive apenas no .env do perfil c3po
  (default `~/.hermes/profiles/c3po/.env` — raiz Hermes do usuario; override
  C3PO_ENV) e e lida em tempo de execucao
  pelo helper. NUNCA ecoar/imprimir/logar.
- OAuth e fornecido pela conta Composio gerenciada. Proibido criar app OAuth proprio.
- Nenhum segredo vai para a planilha.
- Escopo de escrita do projeto (R2): apenas a arvore deste repositorio (checkout local).

## 2. Alvo fixo

- Planilha: Pokemon TCG Pocket - Intelligence Database
- spreadsheetId: 1a8iGqr4w7y-QgCKX6ChGcshYmjKdhdOIeuuvLBkGit0
- URL: https://docs.google.com/spreadsheets/d/1a8iGqr4w7y-QgCKX6ChGcshYmjKdhdOIeuuvLBkGit0/edit
- Conta googlesheets conectada ACTIVE (Composio): ca_lOfRvM1J5601
  escopo drive + spreadsheets + userinfo.email, base sheets.googleapis.com/v4.
  (Nota: ha 3 contas googlesheets ACTIVE; esta e a unica com escopo spreadsheets.)

## 3. Toolchain

SDK: composio==0.22.0 (python <venv do projeto>). Toolkit version pinada: 20261018_00.
Ferramentas usadas: GOOGLESHEETS_CREATE_GOOGLE_SHEET1, GOOGLESHEETS_ADD_SHEET,
GOOGLESHEETS_BATCH_UPDATE, GOOGLESHEETS_CLEAR_VALUES, GOOGLESHEETS_FORMAT_CELL,
GOOGLESHEETS_GET_SHEET_NAMES.
Leitura de volta via c.tools.proxy -> sheets.googleapis.com/v4/spreadsheets/{id}/values/{tab}.

## 4. Protocolo de sync idempotente (integrations/google-sheets/sync.py)

sync_tab(name, values, ncols, retries=3, backoff_s=4.0)

1. GOOGLESHEETS_CLEAR_VALUES no range tab!A1:<last_col>2000
2. GOOGLESHEETS_BATCH_UPDATE com valores (2D) e valueInputOption=RAW
3. Leitura de volta via sheets.googleapis.com/v4/values
4. Assert linhas_nao_vazias == expected; registra job em Sincronizacoes com status success|pending
5. Em falha de rede: 3 tentativas com backoff exponencial; apos isso a linha do job fica status=pending (fila)

## 5. Abas (27) - mapa de camadas

- Analitica: Dashboard, Expansoes, Fontes, Sincronizacoes, Pendencias
- Catalogo: Cartas_Master, Ataques, Habilidades, Evolucoes, Treinadores, Energias
- DERIVADAS por elemento (regeneradas de Cartas_Master; somente leitura,
  JAMAIS cadastro independente): Grama, Fogo, Agua, Eletrico, Psiquico,
  Lutador, Sombrio, Metal, Dragao, Incolor
- Competitiva: Decks_Meta, Decks_Cartas, Matchups (F11 - populadas do SQLite)
- Producao: Decks_Criados, Deck_Cartas, Avaliacoes (F11 - populadas do SQLite)

## 6. Whitelist de colunas (regra de escrita)

- Cada aba tem cabecalho congelado e filtros.
- O helper so escreve dentro das colunas mapeadas no header.
- Abas derivas por tipo (Grama/Fogo/...) sao regeneradas a partir de
  Cartas_Master na totalidade; nenhuma edicao manual nelas deve ser
  considerada fonte de verdade.
- Campos editaveis via Sheets (whitelist de entrada SQLite), a ativar quando
  Decks_Criados existir: Cartas_Master.alias_ptbr, .user_note, .interest_tag.

## 7. Export incremental do catalogo (F5b, 2026-10-19)

Ponto unico do export: `integrations/google-sheets/export_catalog.py`.
Leitura: banco CANONICO `data/pocket.sqlite` aberto em mode=ro. Escrita do
ledger: banco LEDGER DEDICADO (F5d, 19/10) em `data/sync_state.sqlite`
(duravel e auditavel no repositorio; `F5D_LEDGER_DB` pode sobrepor) —
 nao e mais um clone do catalogo: o ledger tem APENAS sync_jobs,
sync_changes, source_records (+ sources para os FKs e schema_migrations),
e NENHUMA tabela de catalogo. Quem quiser dados de cartas abre
`data/pocket.sqlite` (unico caminho canonico). Identidade de cabeca de
cada banco: Application-ID 1 = pocket.sqlite (catalogo canonico),
2 = sync_state.sqlite (ledger de sync); comment no topo do SQL de cada
tabela do ledger diz o que ele e. Os hashes do F5b/F5c (4 jobs, 104
mudancas, 27 hashes de aba) foram migrados para o ledger dedicado; o
legado efemero /tmp/f5b_ledger.sqlite NAO e mais lido (escopo §21).

Fluxo por execucao:
1. Builders lendo o SQLite (Cartas_Master nivel impressao=4317; Ataques 2183
   post-F4c; Habilidades 189; Evolucoes 932; Treinadores 389 EM NIVEL
   IMPRESSAO (337 treinador + 52 pokemon_tool), visao de Cartas_Master -
   secao 7.4, corrigido no F5c de 163 em nivel carta; as 10 abas de
   elemento derivadas de Cartas_Master com nota de origem; Pendencias e
   Dashboard calculados do banco; Expansoes 24; Fontes).
2. Para cada aba: hash SHA-256 do payload vs source_records. Inalterada =>
   SKIP (zero clear/write). Alterada => write_increment (leitura previa,
   chunks first_cell_location <= 800, limpeza apenas de cauda, read-back
   assert). Nunca destroi o conteudo anterior em caso de falha.
3. sync_jobs (1 linha/job) + sync_changes (1 linha/aba/job) no LEDGER, com
   hash por aba; aba Sincronizacoes recebe espelho append-only.
4. `Pagina1` removida; header congelado + filtro basico nas abas de dados.

Provas de aceite (leitura DE VOLTA da planilha, 2026-10-19):
- Cartas_Master=4317, Ataques=2183, Habilidades=189, Evolucoes=932,
  Expansoes=24, soma das 10 abas de tipo=3928 (todos os prints de Pokemon),
  Fontes sem campo obrigatorio vazio, Dashboard com
  ids/att/ab/evol/prints/expansoes batendo com o banco.

F5c (19/10, pos-auditoria) - 3 defeitos do F5b fechados, provas lidas
DE VOLTA da planilha no job `f5b_20261019T005548Z`:
- LEDGER: sync_jobs=4 e sync_changes=104 lidos de volta do SQLite
  (4 no job f5b_20261019T005548Z, todos com hash); data/sync_state.sqlite.
- LINHAS DESALINHADAS: 21 linhas de Ataques e 5 de Evolucoes com print_ref
  vazio tinham a causa em cards SEM NENHUMA impressao no banco (residuo de
  scraping). Na aba, o print_ref agora e derivado do proprio card_id
  (limitless:SET/NUM -> SET/NUM) quando o card nao tem print; padrao
  conferido para os 21 ids e leitura de volta: ZERO linhas com primeiro
  campo vazio em Ataques / Evolucoes / Cartas_Master.
- TREINADORES: reconstruida em nivel impressao, visao de Cartas_Master
  (secao 7.4): 389 linhas (337 treinador + 52 pokemon_tool); reconciliacao
  3928 (tipos) + 389 = 4317 = Cartas_Master confere por leitura de volta.
- PROVA DE INCREMENTAL: 2a execucao consecutiva sem mudanca = 24 abas
  skipadas por hash, zero clear/write nas abas de catalogo (as 2 unicas
  reescritas sao Pendencias+Dashboard, que carimbam job_id/hora do job -
  por definicao mudam a cada execucao).
- DECISAO TECNICA (probe 13): o endpoint bruto values:batchUpdate do proxy
  Composio devolve HTML de erro nesta integracao; o caminho funcional e o
  TOOLKIT (GOOGLESHEETS_BATCH_UPDATE + first_cell_location). Registrada
  aqui para nao repetir o diagnostico.

## 9. Camada competitiva/de producao (F11, 19/10/2026)

As 6 abas sao populadas pelo MESMO export (builders em
export_catalog.py, mapa COMPETITIVE_SOURCES com o SQL de origem de cada
aba - fonte da verdade das provas de aceite):

- Decks_Meta: tournament_results JOIN decks JOIN tournaments (decklists
  reais do corpus F7 com torneio, data, jogador, colocacao, arquetipo).
- Decks_Cartas: deck_cards desses decks (quantidade agregada por
  deck+card+print; print vazio -> ref derivada do card_id).
- Matchups: tabela matchups da F7 (win_rate_a_pct em escala 0-100,
  amostra, janela, selo de confianca dos gates da propria F7).
- Decks_Criados / Deck_Cartas: deck_specifications do builder F8 (a
  MESMA lista de 20 cartas entregue ao Proprietario, com funcao/motivo).
- Avaliacoes: deck_evaluations do evaluator F9 (nota 0-10 do banco,
  nota x10 na aba, pesos f9-v1, melhor/pior dimensao, detalhe).

Contrato das abas F11 (write_tab_full): clear + write em chunks de 800 +
LEITURA DE VOLTA PAGINADA (2000 linhas) com assert de contagem exata;
RETOMAVEL sob quota (429 espera 60s e retoma do chunk seguinte - a janela
do Sheets e POR MINUTO por usuario); skip por hash so apos VERIFICACAO
por leitura de volta (hash integro no ledger nao garante aba completa:
processo morto no meio da escrita deixa aba pela metade). Guarda
anti-placeholder na leitura: qualquer celula com a palavra reservada
quebra o sync (nenhuma aba termina com placeholder). Grade de cada aba
ajustada ao payload (fit_grids) para respeitar o limite de 10M celulas
do Google Sheets. main() abre DUAS conexoes: canonico (mode=ro) para os
builders e ledger dedicado para sync_jobs/sync_changes/source_records
(defeito latente do F5d corrigido no F11). Pendencias nao lista mais a
pendencia "decks_f7_f9" (resolvida por esta fase).

Testes de guarda: tests/unit/test_f11_sheets_competitive.py (3 niveis:
fonte sem placeholder/sem build_future_tab; builders reais com contagem
== SQL de origem; transporte falso provando que aba placeholder/vazia
quebra o assert). Prova de aceite por leitura de volta (19/10): 6288 /
84347 / 10840 / 4 / 40 / 2 - TUDO OK, zero AGUARDANDO.

## 8. Estado atual (19/10/2026)

- 27 abas: Pagina1 removida; as 25 de dados populadas; Dashboard,
  Sincronizacoes e Pendencias vivas.
- Ledger do sync em sync_jobs/sync_changes (canonico no clone SQLite;
  a aba Sincronizacoes e espelho auditavel).
- Campos editaveis via Sheets (whitelist de entrada SQLite), a ativar quando
  Decks_Criados existir: Cartas_Master.alias_ptbr, .user_note, .interest_tag.

