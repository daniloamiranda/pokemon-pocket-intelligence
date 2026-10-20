# Procedimento de Release Pública (snapshot)

## Princípio

O repositório público (`github.com/daniloamiranda/pokemon-pocket-intelligence`)
é um **snapshot da árvore `main`** deste repositório canônico — nunca um
espelho do histórico interno.

Razão: o histórico interno contém arte de cartas de terceiros e o blob do
banco operacional, cuja redistribuição viola `docs/ATTRIBUTION.md`. O snapshot
publica somente a árvore rastreada no HEAD, que já passou pela varredura de
publicabilidade (ver checklist abaixo).

## Regras invioláveis

1. **Publicar SEMPRE por snapshot da árvore** (`git archive` da árvore do HEAD
   ou equivalente). **NUNCA** usar `git push` do histórico interno.
2. **A credencial de publicação vive exclusivamente no `.env` do perfil do
   operador custódio** (fora deste repositório, nunca versionada). Nenhum
   outro operador ou agente — inclusive o CEO — utiliza ou carrega essa
   credencial. A operação do repositório remoto é escopo do custódio.
3. Nenhum segredo, caminho interno de infraestrutura ou arte de terceiros
   entra na árvore publicada.
4. Cada versão nova é um commit adicional no repositório público contendo a
   árvore integral do HEAD local; sem reescrita de histórico público.

## Critério de versionamento (SemVer, 0.x até a 1.0)

Formato `MAJOR.MINOR.PATCH` ([SemVer](https://semver.org/lang/pt-BR/)):

- **Enquanto não há 1.0**: `0.x.y` sinaliza que os contratos públicos de dados
  (`contracts/*.json`) e as skills consumidas por agentes ainda estão em
  formação. A 1.0 ficará retida até que haja estabilidade de contrato
  declarada e suficiente histórico de uso — decisão do Proprietário (19/10),
  que excluiu a 1.0 para esta release.
- **MINOR (0.x)** reflete a **dimensão da entrega, não a data**: cada incremento
  de MINOR corresponde a acréscimo de **capacidade observável** para o usuário
  (novo fluxo, novo comando, nova fonte de verdade), não a correções internas.
- **PATCH (z)** somente para correção sem mudança de capacidade.
- **Sem churn de número**: a release pública publicada é exatamente a que
  recebe a tag; o `CHANGELOG.md` registra a mesma versão.
- A decisão final do número é do CEO, com os pareceres do time (CTO, QA, PMO)
  registrados no board antes da publicação.

## Checklist pré-publicação (gate da release)

1. **Paridade de árvore**: contagem e caminhos de `git ls-tree -r HEAD`
   conferidos contra a árvore a publicar.
2. **Extensões proibidas**: nenhuma `.webp`/`.png`/`.jpg`/`.jpeg`/`.gif`
   (arte de terceiros) nem `.sqlite`/`.db`/`.env` (dado operacional/segredo).
3. **Varredura de conteúdo**: zero credencial real (padrões de token de
   provedores, chaves privadas, atribuições `*_KEY`/`*_TOKEN` com valor),
   zero e-mail pessoal e zero caminho interno do host de desenvolvimento,
   árvore de perfis do operador) em arquivo publicado.
4. **Presença**: `LICENSE` (MIT) na raiz, `README.md`, e as skills do projeto
   sob `skills/`.
5. **Pós-publicação**: acesso **anônimo** (sem token) ao raw do `LICENSE`
   deve retornar HTTP 200 — prova de que o repositório é público.

## Procedimento (v1, aplicada em 19/10/2026)

1. Exportar a árvore: `git archive --format=tar HEAD` (ou cópia equivalente
   da árvore rastreada).
2. Criar/atualizar o repositório público com essa árvore como commit único
   (squash) — a publicação inaugural usou esse método ("Initial public
   release").
3. Executar o checklist do gate contra o resultado publicado (paridade,
   varredura, acesso anônimo).
4. Registrar a release (commit local correspondente + data + resultado da
   verificação) na seção abaixo.
5. A partir da v0.2.0: criar **tag `v0.x.y`** e **GitHub Release** com release
   notes completas (o que mudou, quebras de contrato, limitações conhecidas,
   como usar, licença e atenção a dados de terceiros); entrar a mesma versão
   no `CHANGELOG.md`.

## Histórico de releases

- **2026-10-20** — **v0.2.1** (patch: portabilidade; sem capacidade nova).
  - Commit público `01a6941` "Release v0.2.1 — portability: no host paths in
    the published tree" (árvore do commit interno `a5edf36`, card PORT
    t_b30fbe58); tag anotada `v0.2.1` e GitHub Release
    (`/releases/tag/v0.2.1`, notas com as 5 limitações declaradas).
  - Motivo: o snapshot da v0.2.0 (`fd33e17`) retinha resíduo de caminho
    interno — 56 linhas em 24 arquivos (docs de procedimento e defaults de
    manutenção), declarado nas notas daquela release e sanado no commit
    interno `a5edf36`. Este patch publica a árvore já saneada.
  - Verificação do publicado (clone anônimo, sem token): 110 arquivos;
    zero `.webp/.png/.jpg/.jpeg/.gif/.sqlite/.db/.env`; **zero** caminho
    absoluto da máquina de desenvolvimento (diretório pessoal do operador,
    armazenamento do executor ou raiz do workspace); **zero** padrão de
    credencial/chave; paridade blob-sha **110/110** contra o HEAD canônico;
    `LICENSE` (MIT) presente; `bin/tcgp` modo 755.
  - Prova `tcgp` no clone anônimo: `--help` rc=0; sem catálogo (banco não
    versionado) `"Mega Altaria ex" --copiar` e `meta --top 3` recusam com
    rc=127 e a instrução de construção — comportamento honesto esperado.
    Com catálogo local (banco copiado para o clone, fora do versionamento):
    fluxo completo rc=0 com **papel por carta** (`deck-mega-altaria-ex-005`,
    sem carta fantasma) e `meta --top 3` rc=0 (snapshot snap-full-2026-10-19).
  - Fonte de dados de terceiros: nenhuma arte/banco redistribuído.

- **2026-10-19** — **v0.1.0 (retroativa)** e **v0.2.0**.
  - `v0.1.0` → commit público `2fdca07` "Initial public release"
    (102 arquivos; árvore do commit interno `898a5f3`). Tag anotada
    aplicada retroativamente na decisão de versionamento do CEO.
  - `v0.2.0` → commit público `fd33e17` (árvore do commit interno
    `ce4277c`; 110 arquivos = 102 + 8 novos: `bin/tcgp`, `docs/USAGE.md`,
    `data/card_roles.yaml`, `scripts/deck/card_roles.py`, testes UX-1/UX-2
    e atualização do snapshot). Paridade 110/110 blob-sha contra o HEAD
    canônico; GitHub Releases criadas para as duas tags (v0.2.0 `latest`) com
    release notes no padrão Keep a Changelog e as limitações declaradas.
  - Varredura do publicado: zero `.webp/.png/.jpg/.jpeg/.gif/.sqlite/.db/
    .env`, zero padrão de credencial/token/chave privada. Resíduo de caminho
    interno: 55 linhas em 23 arquivos (docs de procedimento + defaults de
    manutenção com override por env + guardas de teste por design) —
    retenção consciente declarada nas release notes; patch de portabilidade
    v0.2.1 e saneamento editorial em cards próprios. Prova `tcgp` no clone
    anônimo: `--help`, `meta --top 3` e `"Mega Altaria ex" --copiar`
    executados (sem catálogo: recusa honesta rc=127 com instrução; com
    catálogo local: rc=0 com papel por carta e nota heurística).
  - **2026-10-19 (v1, sem tag)** — commit público `2fdca07`
    "Initial public release" (102 arquivos; árvore do commit interno
    `898a5f3`). Verificação de custódia pelo CTO: paridade 102/102,
    zero credencial, zero arte/banco; achados de caminhos internos em
    documentação registrados para saneamento no próximo snapshot.

## Decisão de versionamento registrada (19/10/2026)

- **v0.1.0 (retroativa)** — atribuída ao commit público inicial `2fdca07`
  ("Initial public release", árvore do interno `898a5f3`): primeira release
  pública utilizável (base estática + catálogo + skills), publicada sem tag
  nem CHANGELOG — quebra de processo sanada a partir desta release.
- **v0.2.0 (esta)** — recomendada pelo CTO (parecer no card REL3-CTO,
  t_d29c0212): a v2 acrescenta **capacidade observável** — fluxo completo de
  deck em uma chamada (`bin/tcgp`), saída com papel por carta e "como
  funciona" gerada do deck real, tabela curada `data/card_roles.yaml`,
  `docs/USAGE.md`, Área 15 de mecânicas verificadas e atualização sob demanda
  (`scripts/rules_refresh.py`). Delta medido v1→v2: 13 arquivos, +1.906/−31
  linhas, 7 arquivos novos, zero mudança em `contracts/` (sem quebra de
  contrato → não é MAJOR; capacidade nova → não é PATCH).
- Pareceres QA (t_dce8ead0) e PMO (t_a0ea3829) em tramitação no board; voto
  do CEO registrado no card REL2 (t_6f6b0f62): v0.2.0 + tag retroativa
  v0.1.0. Decisão final do CEO registrada no card antes da publicação.
