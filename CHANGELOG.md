# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
versionamento segue [SemVer](https://semver.org/lang/pt-BR/). Enquanto o
projeto não atinge a 1.0, a versão `0.MINOR.PATCH` sinaliza que os contratos
públicos de dados (`contracts/*.json`) e as skills consumidas por agentes
ainda estão em formação — ver `docs/RELEASE.md` para o critério completo.

## [0.2.1] - 2026-10-19

### Corrigido
- Portabilidade do código executável: nenhum caminho do host de
  desenvolvimento em `.py`/`.sh`. Defaults de ambiente derivados na execução
  (`C3PO_ENV`, `RULES_REFRESH_ENV_FILE`/`--env-file`, `HERMES_ROOT_SKILLS`,
  `TCGP_HERMES_ROOT`, `TCGP_VENV_PY`); `sys.path` de
  `resync_attacks_abilities.py` derivado de `__file__`; `sync.py` resolve a
  credencial tardiamente (importação leve) com falha rápida e mensagem clara
  quando o `.env` não existe. Sem mudança de comportamento no host do
  operador (defaults resolvem os mesmos arquivos de antes).
- Saneamento editorial da documentação de procedimento: caminhos absolutos
  do host substituídos por formas portáteis (`<venv do projeto>`,
  `$HERMES_ROOT`, armazenamento local do executor), convenção declarada em
  `docs/TESTING.md`; registros de auditoria (HOMOLOGACAO) preservados.
- Redistribuição da skill `pokemon-pocket-rules` (referência `RULES.md`
  re-sincronizada com `docs/RULES.md`) — verificação única restaurada
  ("hash único verificado: ok").

## [0.2.0] - 2026-10-19

### Adicionado
- `bin/tcgp` — comando curto, ponto único de entrada do fluxo completo
  (monta, valida, avalia e explica um deck em uma chamada), com subcomandos
  `deck`, `eval`, `meta`, `cartas` e `refresh`.
- Saída do deck-builder com uma linha por carta (nome + quantidade à
  esquerda, papel à direita) e seção "como funciona" gerada a partir do deck
  real — fim do texto fixo que citava carta ausente do deck.
- `data/card_roles.yaml` — 45 papéis curados com `text_evidence`; papéis de
  Pokemon derivados do `effect_text` real da ficha (`scripts/deck/card_roles.py`).
- `docs/USAGE.md` — guia de uso com 9 exemplos reais (247 linhas).
- Área 15 no `docs/RULES.md` — 10 mecânicas de app/ranqueada verificadas
  contra a fonte oficial, e `scripts/rules_refresh.py` para atualização sob
  demanda (manutenção manual; nunca em runtime, nunca em cron).
- `docs/RELEASE.md` — procedimento de release pública por snapshot,
  critério de versionamento e registro das decisões.
- `CHANGELOG.md` (este arquivo) — histórico de versões no padrão Keep a
  Changelog.
- Suítes de teste `tests/unit/test_ux1_deck_output.py` e
  `tests/unit/test_ux2_tcgp.py` (485 linhas; suíte total 190/190 verde nos
  dois interpretadores, banco de produção md5-intocado).

### Alterado
- `scripts/deck/build_deck.py` — integração com os papéis por carta.
- `README.md` — forma natural de uso via `bin/tcgp`.
- `skills/pokemon-pocket-deck-builder/SKILL.md`, `docs/DECK.md`,
  `docs/TESTING.md` — alinhamento de documentação com o novo fluxo.

### Limitações conhecidas (declaradas)
- 29 regras de combate seguem NÃO VERIFICADA — a fonte oficial delega essas
  regras aos Tips in-app e nenhuma página pública as detalha; nenhuma delas
  é usada pelo validador.
- A nota 0-100 do avaliador é qualidade heurística, não winrate; a precisão
  estatística é limitada pelas amostras (matchups com 1 a 3 jogos).
- O banco catálogo NÃO é versionado: quem clonar precisa construir o
  catálogo localmente (`python3 scripts/collect_pocket.py &&
  python3 scripts/db_migrate.py`) — ver `docs/INSTALLATION.md` e README.
- Papéis de carta são rótulos de vocabulário fechado; Treinadores com pouco
  texto no catálogo podem exibir rótulo genérico.
- Menções a caminhos do host do operador permanecem em documentação de
  procedimento interno e em poucos defaults de ferramentas de manutenção
  deste fleet (sempre com override por variável de ambiente); retenção
  consciente nesta release — zero segredo (varredura negativa no
  publicado), risco explorável nulo; saneamento editorial + patch de
  portabilidade planejados para a próxima release.

## [0.1.0] - 2026-10-19 (retroativa)

Primeira release pública utilizável (commit público `2fdca07`, "Initial
public release"; árvore do commit interno `898a5f3`; 102 arquivos, publicada
por snapshot — ver `docs/RELEASE.md`).

### Adicionado
- Base estática de regras verificadas (`docs/RULES.md`), catálogo de cartas,
  coleta de metagame e avaliação de decks.
- 6 skills Pokemon TCG Pocket (rules, card-vision, meta-analyzer,
  deck-builder, deck-evaluator, card-database) e contratos JSON versionados
  (`contracts/`).
- `LICENSE` (MIT); dados de terceiros nunca redistribuídos
  (`docs/ATTRIBUTION.md`).

[0.2.1]: https://github.com/daniloamiranda/pokemon-pocket-intelligence/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/daniloamiranda/pokemon-pocket-intelligence/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/daniloamiranda/pokemon-pocket-intelligence/releases/tag/v0.1.0
