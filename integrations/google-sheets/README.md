# Protocolo de Sincronizaac eio SQLite -> Google Sheets
Projeto: pokemon-pocket-intelligence
Origem canonica: data/pocket.sqlite
Interface: Google Sheets via Composio v3
Ultima execucao real: 2026-10-18 (~20:30 UTC-3)

## 1. Credencial e escopo (PROIBIDOS)

- A chave COMPOSIO_API_KEY vive apenas no .env do perfil c3po
  (/home/hermes/.hermes/profiles/c3po/.env) e e lida em tempo de execucao
  pelo helper. NUNCA ecoar/imprimir/logar.
- OAuth e fornecido pela conta Composio gerenciada. Proibido criar app OAuth proprio.
- Nenhum segredo vai para a planilha.
- Escopo de escrita do projeto (R2): apenas /workspace/ARCOS/projetos/pokemon-pocket-intelligence.

## 2. Alvo fixo

- Planilha: Pokemon TCG Pocket - Intelligence Database
- spreadsheetId: 1a8iGqr4w7y-QgCKX6ChGcshYmjKdhdOIeuuvLBkGit0
- URL: https://docs.google.com/spreadsheets/d/1a8iGqr4w7y-QgCKX6ChGcshYmjKdhdOIeuuvLBkGit0/edit
- Conta googlesheets conectada ACTIVE (Composio): ca_lOfRvM1J5601
  escopo drive + spreadsheets + userinfo.email, base sheets.googleapis.com/v4.
  (Nota: ha 3 contas googlesheets ACTIVE; esta e a unica com escopo spreadsheets.)

## 3. Toolchain

SDK: composio==0.22.0 (python /opt/data/f5_venv). Toolkit version pinada: 20261018_00.
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
- Competitiva: Decks_Meta, Decks_Cartas, Matchups
- Producao: Decks_Criados, Deck_Cartas, Avaliacoes

## 6. Whitelist de colunas (regra de escrita)

- Cada aba tem cabecalho congelado e filtros.
- O helper so escreve dentro das colunas mapeadas no header.
- Abas derivas por tipo (Grama/Fogo/...) sao regeneradas a partir de
  Cartas_Master na totalidade; nenhuma edicao manual nelas deve ser
  considerada fonte de verdade.
- Campos editaveis via Sheets (whitelist de entrada SQLite), a ativar quando
  Decks_Criados existir: Cartas_Master.alias_ptbr, .user_note, .interest_tag.

## 7. Estado atual (18/10/2026)

- 27 abas criadas + cabcabelho l1 escrito (GOOGLESHEETS_BATCH_UPDATE x27, 0 falhas).
- Dados reais sincronizados: Expansoes (24 linhas + cabecalho), Fontes (1 linha),
  Sincronizacoes (2 registros de job).
- Idempotencia: 4 reexecucoes do sync de Expansoes = 25 linhas estaveis, zero duplicacao.
