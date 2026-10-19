#!/usr/bin/env python3
"""F2 - Gera os 12 contratos JSON Schema das 6 skills.

Cada contrato:
- $schema: draft 2020-12
- $id + title + description
- x-version / x-owner / x-skills (metadados ARCSEC)
- required minimo, properties tipadas, additionalProperties: false
- exemplo embutido em x-example

Run:  python3 scripts/gen_contracts.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "contracts"
OUT.mkdir(exist_ok=True)

META = {
    "$schema": "http://json-schema.org/draft/2020-12/schema",
    "x-owner": "tony_stark",
    "x-stage": "F2",
}


def contract(cid, title, desc, props, required, example, skills):
    doc = {
        **META,
        "$id": f"https://arcsec.io/schemas/pokemon-pocket/{cid}.json",
        "title": title,
        "description": desc,
        "type": "object",
        "x-version": "2.0.0",
        "x-skills": skills,
        "properties": props,
        "required": required,
        "additionalProperties": False,
        "x-example": example,
    }
    (OUT / f"{cid}.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  contracts/{cid}.json")


# helpers de sub-objeto
def dims(confidence):
    return confidence

# ---------------------------------------------------------------- 1. card.json
contract(
    "card", "Card - identidade mecanica da carta",
    "Identidade MECANICA da carta (independente de impressao/arte). Impressoes vivem em card_variant.json / card_prints. "
    "Fonte canonica: pocket.limitlesstcg.com (FASE1 §4.3).",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$",
               "description": "ID canonico estavel (ex.: mega-gengar-ex-B4b)"},
        "canonical_name": {"type": "string", "minLength": 1},
        "category": {"type": "string",
                     "enum": ["pokemon", "trainer_item", "trainer_supporter", "trainer_stadium",
                              "pokemon_tool", "energy_basic", "energy_special"]},
        "element": {"type": ["string", "null"],
                    "enum": ["grass", "fire", "water", "lightning", "psychic", "fighting",
                             "darkness", "metal", "dragon", "colorless", None]},
        "stage": {"type": ["string", "null"], "enum": ["basic", "stage1", "stage2", "mega_ex", None]},
        "evolves_from_id": {"type": ["string", "null"]},
        "hp": {"type": ["integer", "null"], "minimum": 0},
        "weakness_element": {"type": ["string", "null"],
                             "enum": ["grass", "fire", "water", "lightning", "psychic", "fighting",
                                      "darkness", "metal", None]},
        "retreat_cost": {"type": ["integer", "null"], "minimum": 0, "maximum": 4},
        "special_rule": {"type": ["string", "null"],
                         "description": "Regra especial literal (ex.: 'Mega Evolution ex')"},
        "mechanical_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$",
                            "description": "SHA-256 do payload mecanico — base de dedup/upsert"},
        "source_id": {"type": "string"},
        "collected_at": {"type": "string", "format": "date-time"},
        "verified_at": {"type": ["string", "null"], "format": "date-time"},
        "validation_status": {"type": "string", "enum": ["pending", "verified", "divergent", "rejected"]},
        "is_ex": {"type": "boolean", "default": False},
        "attacks": {"type": "array", "items": {"type": "object",
                    "properties": {"name": {"type": "string"},
                                   "energy_cost": {"type": "array", "items": {"type": "string"}},
                                   "damage": {"type": ["integer", "null"]},
                                   "effect_text": {"type": ["string", "null"]},
                                   "sort_order": {"type": "integer"}},
                    "required": ["name"], "additionalProperties": False}},
        "abilities": {"type": "array", "items": {"type": "object",
                      "properties": {"name": {"type": "string"},
                                     "kind": {"type": "string", "enum": ["ability", "ancient_trait"]},
                                     "effect_text": {"type": "string"}},
                      "required": ["name", "effect_text"], "additionalProperties": False}},
    },
    ["id", "canonical_name", "category", "source_id", "collected_at", "mechanical_hash"],
    {"id": "mega-gengar-ex-B4b", "canonical_name": "Mega Gengar ex", "category": "pokemon",
     "element": "darkness", "stage": "mega_ex", "hp": 210, "weakness_element": "fighting",
     "retreat_cost": 1, "is_ex": True, "special_rule": "Mega Evolution ex",
     "attacks": [{"name": "Labyrinth of Shadows", "energy_cost": ["darkness", "darkness", "darkness", "colorless"],
                  "damage": 120,
                  "effect_text": "Durante o proximo turno do oponente, ele nao pode jogar nenhuma carta de Treinador da propria mao.",
                  "sort_order": 0}],
     "mechanical_hash": "a" * 64, "source_id": "limitless-pocket-db",
     "collected_at": "2026-10-18T16:45:00-03:00", "verified_at": "2026-10-18T16:45:00-03:00",
     "validation_status": "verified"},
    ["pokemon-pocket-card-database", "pokemon-pocket-deck-builder",
     "pokemon-pocket-deck-evaluator", "pokemon-pocket-rules"],
)

# ---------------------------------------------------------------- 2. card_variant.json
contract(
    "card_variant", "CardVariant - impressao/arte da carta",
    "Impressao (print) de uma carta mecanica: conjunto, numero, raridade, arte. Varias impressoes = mesma identidade "
    "mecanica. UNIQUE (card_id, set_code, number) no banco. Imagens sao URL, nunca asset redistribuivel (FASE1 §13.7).",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "card_id": {"type": "string"},
        "set_code": {"type": "string", "description": "Codigo de conjunto (ex.: B4b)"},
        "number": {"type": "string"},
        "rarity": {"type": ["string", "null"], "description": "Simbolo visual (ex.: raridade por simbolos)"},
        "artist": {"type": ["string", "null"]},
        "image_url": {"type": ["string", "null"], "format": "uri",
                      "description": "URL apenas — NUNCA redistribuir bytes de arte"},
        "is_promo": {"type": "boolean", "default": False},
        "source_id": {"type": "string"},
        "collected_at": {"type": "string", "format": "date-time"},
    },
    ["id", "card_id", "set_code", "number", "source_id", "collected_at"],
    {"id": "mega-gengar-ex-B4b-141", "card_id": "mega-gengar-ex-B4b", "set_code": "B4b",
     "number": "141", "rarity": "C4", "artist": "5ban Graphics", "is_promo": False,
     "source_id": "limitless-pocket-db", "collected_at": "2026-10-18T16:45:00-03:00"},
    ["pokemon-pocket-card-database", "pokemon-pocket-card-vision"],
)

# ---------------------------------------------------------------- 3. expansion.json
contract(
    "expansion", "Expansion - conjunto de cartas",
    "Conjunto/colecao do Pocket. Fonte canonica de listagem: pocket.limitlesstcg.com/cards "
    "(FASE1 §4.1: 24 conjuntos em 18/10/2026).",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "code": {"type": "string", "description": "Codigo curto (ex.: B4b)"},
        "name": {"type": "string"},
        "series": {"type": ["string", "null"]},
        "release_date": {"type": "string", "format": "date"},
        "card_count": {"type": "integer", "minimum": 0},
        "source_id": {"type": "string"},
    },
    ["id", "code", "name", "release_date", "source_id"],
    {"id": "exp-B4b", "code": "B4b", "name": "Deluxe Pack: Mega", "series": "Deluxe Pack",
     "release_date": "2026-09-30", "card_count": 429, "source_id": "limitless-pocket-db"},
    ["pokemon-pocket-card-database"],
)

# ---------------------------------------------------------------- 4. rule.json
contract(
    "rule", "Rule - regra de jogo (registry de legalidade)",
    "Uma regra oficial documentada, com fonte, data de verificacao e vigencia. Regra 6 do escopo: NUNCA inventar "
    "regra sem fonte. Todo ID e estavel e citavel pelo validador.",
    {
        "id": {"type": "string", "pattern": "^[A-Z][A-Z0-9_-]+$"},
        "code": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "category": {"type": "string",
                     "enum": ["deck_size", "copies_limit", "legality", "evolution", "restriction", "format", "governance"]},
        "source_id": {"type": "string"},
        "verified_at": {"type": "string", "format": "date-time"},
        "valid_from": {"type": "string", "format": "date"},
        "valid_to": {"type": ["string", "null"], "format": "date"},
        "exceptions": {"type": "array", "items": {"type": "string"}},
        "examples": {"type": "array", "items": {"type": "string"}},
    },
    ["id", "code", "title", "description", "category", "source_id", "verified_at", "valid_from"],
    {"id": "DECK-001", "code": "deck_size_20", "title": "Deck tem exatamente 20 cartas",
     "description": "Um deck TCG Pocket possui exatamente 20 cartas. Diferente de 20 = reprovado.",
     "category": "deck_size", "source_id": "pocket-rulebook",
     "verified_at": "2026-10-18T16:45:00-03:00", "valid_from": "2025-10-30",
     "exceptions": [], "examples": []},
    ["pokemon-pocket-rules"],
)

# ---------------------------------------------------------------- 5. deck.json
contract(
    "deck", "Deck - lista de 20 cartas",
    "Uma lista construida ou extraida de torneio. Cartas nunca por nome solto — sempre por card_id do catalogo. "
    "Legalidade e validada pelo pokemon-pocket-rules contra o registry de rules.",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "name": {"type": "string"},
        "format": {"type": "string"},
        "total_cards": {"type": "integer", "const": 20},
        "archetype": {"type": ["string", "null"]},
        "cards": {"type": "array", "minItems": 1, "items": {"$ref": "deck_card.json"}},
        "source_id": {"type": "string"},
        "collected_at": {"type": "string", "format": "date-time"},
    },
    ["id", "name", "format", "total_cards", "cards", "source_id"],
    {"id": "deck-mega-gengar-001", "name": "Mega Gengar ex - prototype", "format": "standard",
     "total_cards": 20, "archetype": "mega-gengar-ex",
     "cards": [{"card_id": "mega-gengar-ex-B4b", "quantity": 2},
               {"card_id": "haunter-B4b", "quantity": 2},
               {"card_id": "gastly-B4b", "quantity": 2}],
     "source_id": "local-build"},
    ["pokemon-pocket-deck-builder", "pokemon-pocket-deck-evaluator", "pokemon-pocket-rules"],
)

# ---------------------------------------------------------------- 6. deck_card.json
contract(
    "deck_card", "DeckCard - linha do deck (carta + copias)",
    "Item atomico do deck: card_id + quantidade (1 ou 2 copias; restricoes especiais podem baixar o limite). "
    "print_id e OPCIONAL — referencia a impressao especifica.",
    {
        "card_id": {"type": "string"},
        "quantity": {"type": "integer", "minimum": 1, "maximum": 2},
        "print_id": {"type": ["string", "null"]},
    },
    ["card_id", "quantity"],
    {"card_id": "mega-gengar-ex-B4b", "quantity": 2},
    ["pokemon-pocket-deck-builder", "pokemon-pocket-deck-evaluator"],
)

# ---------------------------------------------------------------- 7. meta_archetype.json
contract(
    "meta_archetype", "MetaArchetype - arquetipo competitivo",
    "Arquetipo observado no metagame. Sem estatistica inventada — Source exigida. Nenhum tier e atribuido sem "
    "evidencia (FASE1 §5 e Anexo A: Mega Gengar ex sem evidencia = sem tier).",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "name": {"type": "string"},
        "core_cards": {"type": "array", "items": {"type": "string"}, "minItems": 1,
                       "description": "IDs de cartas nucleo do arquetipo"},
        "tier": {"type": ["string", "null"], "enum": ["A", "B", "C", "D", "F", "unknown", None]},
        "tier_basis": {"type": ["string", "null"],
                       "description": "Metodologia atribuindo o tier — obrigatoria SE tier != null"},
        "source_id": {"type": "string"},
    },
    ["id", "name", "core_cards", "source_id"],
    {"id": "arch-hoopa-mega-absol", "name": "Hoopa ex / Mega Absol ex",
     "core_cards": ["hoopa-ex-B4", "mega-absol-ex-B4"], "tier": "B",
     "tier_basis": "pocketmeta.app snapshot 2026-10-18 (3.7% share, 219 decks)",
     "source_id": "pocketmeta"},
    ["pokemon-pocket-meta-analyzer"],
)

# ---------------------------------------------------------------- 8. meta_snapshot.json
contract(
    "meta_snapshot", "MetaSnapshot - fotografia periodica do metagame",
    "Snapshot com janela rolante e escopo declarado (FASE1 §5 — modelo metodologico pokemontcgpocket.app).",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "window_start": {"type": "string", "format": "date"},
        "window_end": {"type": "string", "format": "date"},
        "scope": {"type": "string", "description": "ex.: 'public standard Swiss'"},
        "tournament_count": {"type": "integer", "minimum": 0},
        "decklist_count": {"type": "integer", "minimum": 0},
        "match_count": {"type": "integer", "minimum": 0},
        "archetypes": {"type": "array", "items": {"type": "object",
                       "properties": {"archetype_id": {"type": "string"},
                                      "share_pct": {"type": "number"},
                                      "win_rate_pct": {"type": "number"},
                                      "tier": {"type": ["string", "null"]}},
                       "required": ["archetype_id"], "additionalProperties": False}},
        "source_id": {"type": "string"},
        "collected_at": {"type": "string", "format": "date-time"},
    },
    ["id", "window_start", "window_end", "scope", "source_id", "collected_at"],
    {"id": "snap-2026-10-18", "window_start": "2026-09-18", "window_end": "2026-10-18",
     "scope": "public standard Swiss, min 64 players", "tournament_count": 30,
     "decklist_count": 6247, "match_count": 17005,
     "source_id": "pokemontcgpocket-app", "collected_at": "2026-10-18T16:45:00-03:00"},
    ["pokemon-pocket-meta-analyzer"],
)

# ---------------------------------------------------------------- 9. matchup.json
contract(
    "matchup", "Matchup - confronto entre arquetipos",
    "Par (a, b) com taxa de vitoria e evidencia. sample_size e OBRIGATORIO — sem evidencia nao existe matchup "
    "(FASE1 §5: amostras diferentes nao sao confronto direto).",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "archetype_a": {"type": "string"},
        "archetype_b": {"type": "string"},
        "win_rate_a_pct": {"type": "number", "minimum": 0, "maximum": 100},
        "sample_size": {"type": "integer", "minimum": 1},
        "window_period": {"type": "string"},
        "source_id": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    ["id", "archetype_a", "archetype_b", "win_rate_a_pct", "sample_size", "window_period", "source_id"],
    {"id": "mu-hoopa-sableye-2026-10", "archetype_a": "arch-hoopa-mega-absol",
     "archetype_b": "arch-mega-sableye", "win_rate_a_pct": 53.1, "sample_size": 6600,
     "window_period": "2026-10-18", "source_id": "untapped", "confidence": "high"},
    ["pokemon-pocket-meta-analyzer", "pokemon-pocket-deck-evaluator"],
)

# ---------------------------------------------------------------- 10. evaluation.json
contract(
    "evaluation", "Evaluation - nota heuristica de deck",
    "Avaliacao multidimensional com PESOS EXPLICITOS e niveis de confianca. Nenhum score sem evidencia "
    "(FASE1 §13.5: popularidade != desempenho). Confidence 'theoretical' marca analise sem dados de torneio.",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "deck_id": {"type": "string"},
        "overall_score": {"type": "number", "minimum": 0, "maximum": 10},
        "dimensions": {"type": "array", "minItems": 1, "items": {"type": "object",
                       "properties": {"name": {"type": "string"},
                                      "score": {"type": "number", "minimum": 0, "maximum": 10},
                                      "weight": {"type": "number", "minimum": 0, "maximum": 1},
                                      "reason": {"type": ["string", "null"]}},
                       "required": ["name", "score", "weight"], "additionalProperties": False}},
        "weights_documented": {"type": "string",
                               "description": "Referencia ao documento de pesos"},
        "confidence": {"type": "string", "enum": ["theoretical", "low", "medium", "high"]},
        "generated_at": {"type": "string", "format": "date-time"},
    },
    ["id", "deck_id", "overall_score", "dimensions", "weights_documented", "confidence"],
    {"id": "eval-mega-gengar-001", "deck_id": "deck-mega-gengar-001", "overall_score": 6.5,
     "dimensions": [{"name": "consistency", "score": 7.0, "weight": 0.3},
                    {"name": "win_rate_expected", "score": 6.0, "weight": 0.4,
                     "reason": "sem dados de torneio — teorico"}],
     "weights_documented": "docs/EVALUATION-WEIGHTS.md",
     "confidence": "theoretical", "generated_at": "2026-10-18T20:00:00-03:00"},
    ["pokemon-pocket-deck-evaluator"],
)

# ---------------------------------------------------------------- 11. source.json
contract(
    "source", "Source - fonte de dados com governanca",
    "Toda linha do banco carrega source_id (FASE1 §4.3). tier conforme diagnostico: canonical "
    "(pocket.limitlesstcg.com) / crosscheck (untapped, pokemontcgpocket.app, pocketmeta.app) / enrichment (TCGdex).",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "name": {"type": "string"},
        "base_url": {"type": "string", "format": "uri"},
        "kind": {"type": "string", "enum": ["api", "scrape", "dataset", "manual", "rulebook"]},
        "tier": {"type": "string", "enum": ["canonical", "crosscheck", "enrichment"]},
        "policy": {"type": ["string", "null"],
                   "description": "Politica de uso (robots, rate limit, licenca)"},
        "requires_key": {"type": "boolean", "default": False},
        "notes": {"type": ["string", "null"]},
    },
    ["id", "name", "base_url", "kind", "tier"],
    {"id": "limitless-pocket-db", "name": "Limitless TCG Pocket Database",
     "base_url": "https://pocket.limitlesstcg.com", "kind": "scrape", "tier": "canonical",
     "policy": "Uso por link/referencia — nenhuma imagem redistribuida", "requires_key": False},
    ["pokemon-pocket-card-database", "pokemon-pocket-meta-analyzer"],
)

# ---------------------------------------------------------------- 12. sync_job.json
contract(
    "sync_job", "SyncJob - execucao de coleta/sincronizacao",
    "Registro de coleta incremental (SQLite -> Sheets / Limitless -> SQLite). Idempotencia: retomada com base em "
    "cursor, nao em re-execucao cega (FASE1 §10). status='pending' em fila offline.",
    {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_.-]+$"},
        "source_id": {"type": "string"},
        "direction": {"type": "string", "enum": ["pull", "push"]},
        "entity": {"type": "string", "enum": ["cards", "card_prints", "meta", "decks", "matchups", "sheets"]},
        "cursor": {"type": ["string", "null"]},
        "status": {"type": "string", "enum": ["pending", "running", "success", "failed", "skipped"]},
        "started_at": {"type": ["string", "null"], "format": "date-time"},
        "finished_at": {"type": ["string", "null"], "format": "date-time"},
        "items_changed": {"type": "integer", "minimum": 0},
        "error": {"type": ["string", "null"]},
    },
    ["id", "source_id", "direction", "entity", "status"],
    {"id": "sync-cards-0001", "source_id": "limitless-pocket-db", "direction": "pull",
     "entity": "cards", "status": "pending"},
    ["pokemon-pocket-card-database", "pokemon-pocket-meta-analyzer"],
)

print("OK — 12 contratos gerados em contracts/")
