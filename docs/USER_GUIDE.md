# USER_GUIDE.md — Como usar o sistema Pokemon TCG Pocket Intelligence

Projeto: pokemon-pocket-intelligence · Owner técnico: tony_stark (CTO)
Atualizado: 2026-10-19 (inclui F8 · deck-builder)

---

## 1. O que o sistema responde

1. **Que carta é essa?** (por imagem) → `pokemon-pocket-card-vision` (F6)
2. **O que está jogando e ganhando?** (metagame real) → `pokemon-pocket-meta-analyzer` (F7)
3. **Que deck eu monto com a minha carta?** → `pokemon-pocket-deck-builder` (F8)
4. **Essa lista é legal?** → `pokemon-pocket-rules` + `scripts/validate_deck.py` (F3)
5. O quão bom é esse deck? (nota + matchups) → `pokemon-pocket-deck-evaluator` (F9: `python3 scripts/eval/evaluate_deck.py --deck-id <deck_id>`; docs/EVALUATOR.md)

## 2. Requisitos

- Python 3.12+ (sem pip obrigatório; stdlib only)
- Banco canônico em `data/pocket.sqlite` (populado pela F4)
- Corpus de metagame em `decks`/`deck_cards` (populado pela F7)
- Cache de fichas em `data/cache/pages` (populado pela F4; opcional para re-parse de trainers)

Instalação das skills no Hermes: `bash scripts/install_skills.sh --verify` (hash único).

## 3. Construir um deck (F8)

```bash
python3 scripts/deck/build_deck.py "Mega Gengar ex"
```

Saída JSON: veredicto, deck_id persistido, lista de 20 com justificativa
mecânica por carta (com amostra real citada), plano de energia, como jogar,
análise competitiva (arquétipos/tiers da F7) e fontes.

- **veredicto `valido`**: núcleo empírico forte (>=12 listas reais na janela).
- **veredicto `fallback`**: lista LEGAL, mas pouca evidência de torneio —
  trate as justificativas como teóricas.
- **`ilegal`/`inconsistente`**: NADA é persistido (o validador F3 decide).

Cartas principais suportadas: `python3 scripts/deck/build_deck.py --list-mains`.

## 4. Validar qualquer lista (F3)

```bash
python3 scripts/validate_deck.py <deck.json> --catalog <catalog.json>
```

Veredicto: `legal`/`illegal` + `violations` com rule_id (DECK-001..REST-001,
EVOL-001/002) + `satisfied_rules` (citação das regras que permitem a lista).

## 5. Analisar o metagame (F7)

```bash
python3 scripts/meta/collect_meta.py        # coleta incremental (checkpoint)
python3 scripts/meta/meta_pipeline.py --days 30
```

Relatórios em `data/meta/reports/`; tiers S/A/B/C/D pela regra F7 v1
(gates >=20 listas e >=100 jogos; faixas S>=55/A>=52/B>=49/C>=45/D<45);
"sem evidência" com amostra citada quando os gates não passam.

## 6. Persistência e governança

- `decks`/`deck_cards`/`deck_specifications` — todo deck do builder fica com id.
- Migrações: `python3 scripts/db_migrate.py` (idempotente; 0001..0004).
- Fontes: `docs/SOURCES.md`; integridade: `docs/DATABASE.md`.
- **Nenhuma carta inventada**: o builder recusa card_id que não resolva no
  catálogo (veredito `carta_inexistente` no JSON).

## 7. Limitações declaradas

- Texto de Trainer/Tool vem do cache F4; ficha sem cache = texto vazio
  (declarado, nunca inventado).
- Energia é "commit por partida" — planos de energia são TEXTOS derivados do
  custo do ataque real, não cartas da lista.
- Arquétipos sem gate de amostra (F7) têm análise teórica, não de torneio.
