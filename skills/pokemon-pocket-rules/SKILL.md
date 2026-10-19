---
name: pokemon-pocket-rules
description: "Use ao validar decks de Pokemon Pocket ou ver suas regras."
version: "1.0.0"
author: "tony_stark"
license: MIT
metadata:
  hermes:
    tags: [pokemon-pocket, rules, legality]
    related_skills: [pokemon-pocket-card-database, pokemon-pocket-deck-builder]
---

# pokemon-pocket-rules — Regras oficiais do Pokemon TCG Pocket + validador de legalidade

## O que esta skill cobre
Somente **Pokemon TCG Pocket** (jogo mobile TPC/DeNA). NUNCA presumir mecanica do TCG fisico/Live.

## Registry de regras
- `references/RULES.md` — catalogo de regras com ID, fonte oficial, data de verificacao, vigencia e excecoes. Fonte da verdade citavel pelo validador.
- Nunca inventar regra sem fonte; divergencia se registra (adicionar nota de verificacao com data).
- `references/SOURCES.md` — fontes oficiais usadas e o que cada uma comprova.

## Validador
- `scripts/validate_deck.py` (no repositorio do projeto) — CLI: `python3 scripts/validate_deck.py <deck.json> --catalog <catalog.json>`.
- Catalogo antes da Fase 4 = **fixture** apenas (`tests/fixtures/catalog_fixture.json`). Nao validar existencia contra o Limitless ate a F4.
- Veredictos: `legal` (cada regra satisfeita citada no veredicto) ou `illegal` (lista de violacoes com RULE-<ID>).

## Gabarito de uso
1. Ler o deck (contrato contracts/deck.json: cards por card_id + quantity 1..2).
2. Chamar o validador; nunca aprovar deck "no olho".
3. Para pergunta de regra, responder com o ID da regra e a fonte + data de verificacao.
