#!/usr/bin/env python3
"""F8 · Deck-builder determinístico do Pokemon TCG Pocket (card t_89d318e2, R2).

Pipeline 100% SQL-led (zero rede, zero texto inventado):
 1) resolve a carta principal no catálogo (card_id exato ou nome via FTS5);
 2) núcleo empírico: co-ocorrência REAL nas listas de torneio coletadas pela
    F7 (tabela decks/deck_cards, fonte play.limitlesstcg.com); decks gerados
    pelo próprio builder (id 'deck-%') NÃO entram no núcleo (F8b: o motor
    não pode citar a própria saída como evidência empírica);
 3) função mecânica declarada por carta (regras nomeadas por família + texto
    REAL da ficha: card_attacks/card_abilities; trainers re-parseados do
    cache F4 em data/cache/pages quando a ficha está em cache);
 4) lista de 20: carta principal SEMPRE presente (proibição do card),
    pré-requisitos de evolução via card_evolutions (EVOL-001) resolvendo a
    IDENTIDADE do pré-requisito por NOME + tipo coerente com a linha
    principal (F8b: nunca compõe 3 cartas do mesmo nome — DECK-002 é por
    NOME — e não abre tipo novo na Energy Zone), quantidade por ranking
    empírico, máxima 2 cópias; revalidação OBRIGATÓRIA pelo validador F3
    (scripts/validate_deck.py) antes de qualquer persistência;
 5) persiste em decks/deck_cards + deck_specifications (migration 0004
    ADITIVA com JSON de justificativas/fontes/amostra; FK CASCADE);
    proximo deck_id = MAX(sufixo)+1 por slug, NUNCA COUNT(*) (BUG-001/F15+:
    serie furada pela revalidacao F8b fazia COUNT+1 recalcular id existente);
 6) veredicto com amostra citada: valido | sem_evidencia | fallback.

Energia: as 4.865 listas reais do corpus F7 provam que listas do Pocket NÃO
contêm cartas de energia — energia é commitada por partida. O plano de
energia é TEXTO de saída derivado do custo real do ataque da ficha.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))

import client as f4client      # noqa: E402
import validate_deck as V3     # noqa: E402
import card_roles as CR        # noqa: E402  (UX-1/t_bd7c1cc1: papeis + relatorio humano)

DB_PATH = ROOT / "data" / "pocket.sqlite"
CACHE = ROOT / "data" / "cache" / "pages"
CORPUS_SOURCE_ID = "play.limitlesstcg.com"
DECK_SIZE = 20
COPIES_MAX = 2
FALLBACK_THRESHOLD = 12        # núcleo com menos listas reais que isso = selo de fallback
NOW = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC naive (collected_at e UTC)


# ---------------------------------------------------------------------------
# Funções mecânicas — regras nomeadas (F8 v1; motivo citável em cada uma)
# ---------------------------------------------------------------------------
FAMILY_RULES = [
    (r"professor(?:'s)? research", "draw",
     "Compra: recicla a mão e compra 2 — presente em 4.802 dos 4.865 decks reais do corpus (98,7%)"),
    (r"^copycat$", "draw",
     "Compra: iguala o tamanho da mão do oponente — 4.644 decks reais (95,4%) usam"),
    (r"^(cyrus)$", "control",
     "Captura: traz de volta o ativo adversário que recuou — 3.541 decks reais (72,8%)"),
    (r"^(poke ball|poké ball)$", "search",
     "Busca: puxa 1 Pokémon Básico do deck — 4.249 decks reais (87,3%)"),
    (r"^rare candy$", "evolution",
     "Evolução: pula do Básico direto para o Estágio 2 — 1.499 decks reais (30,8%)"),
    (r"^wally$", "evolution",
     "Evolução: coloca no banco a evolução direto do deck — usada nos decks reais do Mega Gengar ex"),
    (r"^sabrina$", "control",
     "Captura: troca o ativo adversário por um Básico do banco dele — 1.936 decks reais (39,8%)"),
    (r"^pokemon center lady$|^pokémon center lady$", "heal",
     "Cura: remove 30 de dano e troca o ativo — 1.826 decks reais (37,5%)"),
    (r"^x speed$", "mobility",
     "Mobilidade: custo de recuo -1 no turno — 1.035 decks reais (21,3%)"),
    (r"^giant cape$", "protection",
     "Proteção: +30 HP no Pokémon equipado — 1.008 decks reais (20,7%)"),
    (r"^rocky helmet$", "protection",
     "Proteção ofensiva: 20 de dano de retorno ao ser golpeado — 205 decks reais"),
    (r"^(lucky ice pop)$", "protection",
     "Proteção: impede dano de ataque no Pokémon equipado no turno adversário — 1.376 decks reais"),
    (r"^field blower$", "meta-response",
     "Resposta ao meta: descarta Tool adversária — 1.701 decks reais (35,0%)"),
    (r"^(hand scope|red card)$", "meta-response",
     "Resposta ao meta: informação/pressão de mão adversária"),
    (r"^(team rocket's boss|team rocket's master plan|team rocket's grunt)$", "control",
     "Controle: manipula banco/mão adversária (família Team Rocket)"),
    (r"^(iolite|erika)$", "heal", "Cura: recupera HP do Pokémon (família de cura)"),
    (r"^(communication|pokemon communication|pokémon communication)$", "search",
     "Busca: troca Pokémon da mão pelo deck"),
    (r"^(mythical slab|rotom dex|pokedex|pokédex)$", "search",
     "Busca/informação: manipula o topo do deck"),
    (r"^(repel)$", "control", "Controle: o adversário compra menos no próximo turno"),
    (r"^(prank spinner)$", "meta-response", "Resposta ao meta: descarta a Tool adversária ativa"),
    (r"^(deceptive needle)$", "meta-response",
     "Resposta ao meta: Tool com efeito ofensivo contra Tool adversária — 586 decks reais"),
    (r"^(lucky egg|small balloon|inflatable boat)$", "protection",
     "Proteção/sustentação do ativo (família de Tools defensivas)"),
    (r"^(flame patch|elemental switch|quick-grow extract)$", "energy-accel",
     "Energia: melhora o anexo/fluxo de energia — acelera o commit do ataque"),
    (r"^(maintenance|big malasada)$", "support",
     "Suporte geral de consistência"),
]

FALLBACK_RULES = {
    "pokemon": "core-companion",
    "trainer_supporter": "support",
    "trainer_item": "utility",
    "pokemon_tool": "support",
    "trainer_stadium": "stadium",
    "energy_basic": "energy",
    "energy_special": "energy",
}


def mechanical_function(card: dict, text: str) -> tuple[str, str]:
    """(função mecânica, motivo citável) — regras nomeadas sobre a ficha REAL."""
    name = (card.get("canonical_name") or "")
    for rx, fn, why in FAMILY_RULES:
        if re.search(rx, name, re.I):
            return fn, why
    # texto real do ataque/habilidade pode completar (fichas de Pokémon)
    tl = (text or "").lower()
    if tl:
        if "can't play any trainer" in tl or "can't use any supporter" in tl:
            return "control", "Controle: bloqueia Trainer/Supporter adversários (efeito real da ficha)"
        if "now asleep" in tl or "fell asleep" in tl:
            return "control", "Controle: adormece o ativo adversário (efeito real da ficha)"
        if "switch" in tl and ("with 1 of your benched" in tl or "opponent's active" in tl):
            return "mobility", "Mobilidade: reposiciona por efeito real da ficha"
        if "flip a coin" in tl and "shuffle" in tl:
            return "disruption", "Disrupção: efeito de moeda da ficha real"
        if ("search" in tl) or ("look at" in tl and "deck" in tl):
            return "search", "Busca: efeito real da ficha manipula o deck"
        if "draw" in tl:
            return "draw", "Compra: efeito real da ficha compra cartas"
        if "heal" in tl or "remove" in tl and "damage" in tl:
            return "heal", "Cura: efeito real da ficha remove dano"
        if ("attached" in tl or "attach" in tl) and "energy" in tl:
            return "energy-accel", "Energia: efeito real da ficha manipula energia"
    fn = FALLBACK_RULES.get(card.get("category") or "", "utility")
    who = card.get("canonical_name", cid_str(card))
    return fn, f"Companheiro de linha: presença real com a carta principal no corpus ({fn}) [{who}]"


def cid_str(c: dict) -> str:
    return c.get("id") or "?"


# ---------------------------------------------------------------------------
# 1) carta principal / ficha real
# ---------------------------------------------------------------------------

def resolve_main(con, name_or_id):
    r = con.execute("""SELECT id, canonical_name, category, element, stage, hp, is_ex,
        weakness_element, retreat_cost, special_rule
        FROM cards WHERE id=?""", (name_or_id,)).fetchone()
    if r is None:
        # FTS5: sanear snapshot de query (hifens/pontuação quebram MATCH)
        sanitized = re.sub(r'[^\w\s]', ' ', name_or_id).strip()
        if sanitized:
            try:
                r = con.execute("""SELECT c.id, c.canonical_name, c.category, c.element, c.stage,
                    c.hp, c.is_ex, c.weakness_element, c.retreat_cost, c.special_rule
                    FROM cards c JOIN cards_fts f ON f.card_id=c.id
                    WHERE cards_fts MATCH ? AND c.category='pokemon'
                    ORDER BY c.is_ex DESC, c.hp DESC LIMIT 1""",
                    ('"' + sanitized + '"',)).fetchone()
            except sqlite3.OperationalError:
                r = None
    if r is None:
        r = con.execute("""SELECT id, canonical_name, category, element, stage, hp, is_ex,
            weakness_element, retreat_cost, special_rule FROM cards
            WHERE lower(canonical_name)=lower(?) AND category='pokemon'
            ORDER BY is_ex DESC, hp DESC LIMIT 1""", (name_or_id,)).fetchone()
    return dict(r) if r else None


_MAIN_TEXT_RE = re.compile(
    r'<div class="card-text-section(?:\s*card-text-artist)?">(.*?)</div>', re.S)


def trainer_text_from_cache(set_code: str, number: str) -> str:
    """Texto real de trainer/tool do cache F4 (nunca inventado)."""
    h = f4client._cache_key(f"/cards/{set_code}/{number}", None)
    fp = CACHE / f"{h}.html"
    if not fp.exists():
        return ""
    html = fp.read_text(encoding="utf-8", errors="replace")
    outs = []
    for sec in _MAIN_TEXT_RE.findall(html):
        t = unescape(re.sub(r"<[^>]+>", " ", sec))
        t = " ".join(t.split())
        if t and not t.startswith("Illustrated by") and "Trainer - " not in t:
            outs.append(t)
    return " / ".join(outs[1:]) if len(outs) > 1 else (outs[0] if outs else "")


def main_text(con, card) -> str:
    """Texto real (ataques/habilidades ou trainer re-parseado); '' se nada."""
    cid = card["id"]
    parts = []
    for r in con.execute("SELECT name, effect_text FROM card_attacks WHERE card_id=?", (cid,)):
        parts.append(f"{r['name']}: {r['effect_text'] or ''}")
    for r in con.execute("SELECT name, effect_text FROM card_abilities WHERE card_id=?", (cid,)):
        parts.append(f"{r['name']} (habilidade): {r['effect_text'] or ''}")
    if parts:
        return " / ".join(p for p in parts if p.strip(": "))
    if card["category"].startswith("trainer") or card["category"] == "pokemon_tool":
        r = con.execute("""SELECT set_code, number FROM card_prints WHERE card_id=? AND is_promo=0
            ORDER BY set_code, number LIMIT 1""", (cid,)).fetchone()
        if r:
            return trainer_text_from_cache(r["set_code"], r["number"])
    return ""


# ---------------------------------------------------------------------------
# 2) núcleo empírico (lista real de torneios)
# ---------------------------------------------------------------------------

def empirical_nucleus(con, main_id, days):
    # F8b: decks gerados pelo próprio builder (id 'deck-%') ficam FORA do
    # núcleo — a saída do motor nunca é evidência empírica de si mesma.
    rows = list(con.execute("""
        SELECT d.id, d.collected_at FROM decks d
        JOIN deck_cards dc ON dc.deck_id=d.id
        WHERE dc.card_id=? AND d.id NOT LIKE 'deck-%'""", (main_id,)))
    cutoff = None
    if days:
        cutoff = (NOW - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    scoped = [r for r in rows if not cutoff or (r["collected_at"] or "") >= cutoff]
    if not scoped and rows:
        scoped = rows  # janela sem dados -> usa tudo (declarado na saída)
    deck_ids = [r["id"] for r in scoped]
    tally = Counter()
    if deck_ids:
        q = ",".join("?" * len(deck_ids))
        for r in con.execute(f"""SELECT card_id, COUNT(DISTINCT deck_id) ndecks,
                SUM(quantity) tot FROM deck_cards WHERE deck_id IN ({q}) GROUP BY card_id""",
                deck_ids):
            tally[r["card_id"]] = (r["ndecks"], r["tot"])
    return len(deck_ids), tally


def evolution_chart(con, card_ids):
    if not card_ids:
        return {}
    q = ",".join("?" * len(card_ids))
    return {r["card_id"]: r["pre_evo_card_id"] for r in con.execute(
        f"SELECT card_id, pre_evo_card_id FROM card_evolutions WHERE card_id IN ({q})",
        card_ids)}


def pick_pre_identity(con, pre_id, main_card):
    """F8b: resolve a IDENTIDADE do pré-requisito de evolução por NOME + tipo.

    card_evolutions registra UM card_id de pré-requisito; quando existem
    várias identidades do mesmo nome canônico (ex: Gastly psíquico A1/120 vs
    Gastly sombrio B2b/37), prefere a identidade do MESMO elemento da linha
    principal — nunca abre tipo novo na Energy Zone. Devolve o card_id
    escolhido (pode ser o próprio pre_id quando já é coerente ou não há
    outra identidade). Determinístico (empate: menor card_id).
    """
    pre = con.execute("SELECT id, canonical_name, element FROM cards WHERE id=?",
                      (pre_id,)).fetchone()
    if pre is None:
        return pre_id
    main_el = (main_card or {}).get("element")
    if main_el and pre["element"] == main_el:
        return pre_id  # identidade original já coerente com a linha principal
    cands = [dict(r) for r in con.execute(
        "SELECT id, element FROM cards WHERE canonical_name=? AND id != ? ORDER BY id",
        (pre["canonical_name"], pre_id))]
    if not cands:
        return pre_id
    if main_el:
        same_el = sorted(c["id"] for c in cands if c["element"] == main_el)
        if same_el:
            return same_el[0]
    return pre_id


# ---------------------------------------------------------------------------
# 3) montagem dos 20
# ---------------------------------------------------------------------------

def build_list(con, main, days):
    n_decks, tally = empirical_nucleus(con, main["id"], days)
    picks = []          # list[dict(card_id, quantity, function, reason, source)]
    by_id = {cid: v for cid, v in tally.items() if cid != main["id"] and v[0] > 0}
    ranked = sorted(by_id.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))

    total = 0
    chosen_names = set()   # F8b: nomes canônicos já presentes (DECK-002 é por NOME)
    chosen = {main["id"]}  # card_ids já no deck
    pick_names = {}        # card_id -> nome canônico do pick (agregação por NOME)

    def add(cid, card, q, fn, why, meta):
        nonlocal total
        q = min(q, DECK_SIZE - total, COPIES_MAX)
        if q <= 0:
            return False
        picks.append({"card_id": cid, "quantity": q, "function": fn,
                      "reason": why, **meta})
        total += q
        if card and card.get("canonical_name"):
            chosen_names.add(card["canonical_name"])
            pick_names[cid] = card["canonical_name"]
        return True

    # (a) carta principal — SEMPRE (proibição do card) + a PRÓPRIA linha de
    # evolução reservada ANTES do núcleo (F8b: o deck é montado em torno da
    # principal; a linha dela não pode ficar sem espaço — era o buraco que
    # deixou um Mega Gengar ex SEM Haunter nenhum no deck-001).
    fn, why = mechanical_function(main, main_text(con, main))
    add(main["id"], main, 2,
        "main-card",
        f"Carta principal pedida ({fn if fn != 'main-card' else 'núcleo ofensivo'}); "
        f"presença real no corpus: {n_decks} lista(s); ficha: {main['canonical_name']} "
        f"({main['element']}, stage {main['stage']}, HP {main['hp']})",
        {"real_decks": n_decks})
    # Deixa sempre 2 cópias da principal (o núcleo real usa 2 em 12/12 decks)
    for p in picks[:1]:
        p["quantity"] = 2
    total = sum(p["quantity"] for p in picks)

    chain = [main["id"]]
    while True:
        pre = con.execute("SELECT pre_evo_card_id FROM card_evolutions WHERE card_id=?",
                          (chain[0],)).fetchone()
        if not pre:
            break
        chain.insert(0, pre["pre_evo_card_id"])
    for prec in chain[:-1]:  # do Básico para a principal
        prec_resolved = pick_pre_identity(con, prec, main)
        if prec_resolved in chosen:
            continue
        precard = dict(con.execute("SELECT * FROM cards WHERE id=?",
                                   (prec_resolved,)).fetchone())
        if precard.get("canonical_name") in chosen_names:
            chosen.add(prec_resolved)
            continue
        fnp, why_p = mechanical_function(precard, main_text(con, precard))
        why_pre = (f"Pré-requisito de evolução da própria principal (EVOL-001): "
                   f"{precard['canonical_name']} abre a linha de {main['canonical_name']}")
        meta_pre = {"forced_by": "EVOL-001"}
        if prec_resolved != prec:
            why_pre += (f" [identidade {prec_resolved} preferida a {prec}: "
                        f"mesmo nome, tipo {precard['element']} coerente com a "
                        f"linha principal {main['element']}]")
            meta_pre["identity_basis"] = {
                "requested": prec, "chosen": prec_resolved,
                "criterion": f"mesmo nome + elemento {precard['element']} da linha principal"}
        if not add(prec_resolved, precard, 1, fnp, why_pre, meta_pre):
            break  # sem espaço para a própria linha: validador F3 reprova a jusante
        chosen.add(prec_resolved)

    def q_of(cid, nd, tot, ndecks):
        q = 2 if nd == ndecks else (2 if tot >= 3 else 1)
        return max(1, min(q, COPIES_MAX))

    # (b) resto do núcleo empírico por ranking (com filtro de cadeia completa)
    for cid, (nd, tot) in ranked:
        if total >= DECK_SIZE:
            break
        if nd * 2 < n_decks:   # presença < 50% do núcleo real: fora da lista
            continue
        card = dict(con.execute("SELECT id, canonical_name, category, element, stage, hp, is_ex, weakness_element, retreat_cost, special_rule FROM cards WHERE id=?", (cid,)).fetchone())
        q = q_of(cid, nd, tot, n_decks)
        fn, why = mechanical_function(card, main_text(con, card))
        why = (f"{fn}: presente em {nd}/{n_decks} listas reais com {main['canonical_name']} "
               f"({tot} cópias no agregado) — " + why)
        # F8b — DECK-002 é por NOME: se o nome canônico já está representado
        # na lista por OUTRA identidade, esta identidade NÃO entra; em vez
        # disso, a cópia existente do nome recebe o top-up empírico (até 2
        # no total do nome) — cópias agregam por NOME, como no jogo real.
        if card["canonical_name"] in chosen_names:
            same = next((p for p in picks
                         if pick_names.get(p["card_id"]) == card["canonical_name"]), None)
            if same and same["quantity"] < q and total < DECK_SIZE:
                extra = min(q - same["quantity"], DECK_SIZE - total)
                if extra > 0:
                    same["quantity"] += extra
                    total += extra
                    same["reason"] += (f" [F8b: +{extra} copia(s) por presença real "
                                       f"({nd}/{n_decks} listas) — agregado por NOME]")
            continue
        # filtro de cadeia completa: só entra Pokemon não-Basic cuja cadeia
        # esteja INTEIRA representada (EVOL-001 é checada pelo validador;
        # aqui garantimos que o núcleo não insere coisa impossível de evoluir)
        if card.get("stage") in ("stage1", "stage2", "mega_ex"):
            # cadeia completa: [basico, ..., cid]; EVOL-001 exige CADA pre presente
            chain = [cid]
            while True:
                pre = con.execute("SELECT pre_evo_card_id FROM card_evolutions WHERE card_id=?", (chain[0],)).fetchone()
                if not pre:
                    break
                chain.insert(0, pre["pre_evo_card_id"])
            myq = q_of(cid, nd, tot, n_decks)
            needed = [c for c in chain[:-1] if c not in chosen]
            if needed:
                # reserva espaco: 1 copia de cada pre faltante + 1 da propria carta
                reserve = len(needed) + 1
                if DECK_SIZE - total < reserve:
                    continue   # nao cabe: skip honesto (nada entra sem cadeia)
                added_all = True
                for prec in needed:
                    prec_resolved = pick_pre_identity(con, prec, main)
                    if prec_resolved in chosen:
                        # mesmo nome já representado (F8b): não duplica identidade
                        continue
                    prec_row = con.execute("SELECT * FROM cards WHERE id=?", (prec_resolved,)).fetchone()
                    if prec_row is None:
                        added_all = False
                        break
                    precard = dict(prec_row)
                    if precard.get("canonical_name") in chosen_names:
                        chosen.add(prec_resolved)
                        continue
                    fnp, why_p = mechanical_function(precard, main_text(con, precard))
                    why_pre = (f"Pré-requisito de evolução (EVOL-001): {precard['canonical_name']} "
                               f"completa a cadeia de {card['canonical_name']}")
                    meta_pre = {"forced_by": "EVOL-001"}
                    if prec_resolved != prec:
                        why_pre += (f" [identidade {prec_resolved} preferida a {prec}: "
                                    f"mesmo nome, tipo {precard['element']} coerente com a "
                                    f"linha principal {main['element']}]")
                        meta_pre["identity_basis"] = {
                            "requested": prec, "chosen": prec_resolved,
                            "criterion": f"mesmo nome + elemento {precard['element']} da linha principal"}
                    if not add(prec_resolved, precard, 1, fnp, why_pre, meta_pre):
                        added_all = False
                        break
                    chosen.add(prec_resolved)
                if not added_all:
                    continue
        q = q_of(cid, nd, tot, n_decks)
        fn, why = mechanical_function(card, main_text(con, card))
        why = (f"{fn}: presente em {nd}/{n_decks} listas reais com {main['canonical_name']} "
               f"({tot} cópias no agregado) — " + why)
        if add(cid, card, q, fn, why, {"real_decks": nd, "copies_in_corpus": tot}):
            chosen.add(cid)

    # (c) pré-requisitos de evolução que faltaram (EVOL-001) — ITERATIVO:
    # repete até a cadeia de TODAS as escolhidas estar completa (Stage 2 pode
    # puxar Stage 1 que puxa Básico; o validador F3 é quem confere no fim)
    for _pass in range(4):
        evo = evolution_chart(con, [p["card_id"] for p in picks])
        added = False
        for p in list(picks):
            cid = p["card_id"]
            pre = evo.get(cid)
            if not pre or total >= DECK_SIZE:
                continue
            pre_resolved = pick_pre_identity(con, pre, main)
            if pre_resolved in chosen:
                continue   # F8b: mesmo nome/id já representado no deck
            precard = dict(con.execute(
                "SELECT * FROM cards WHERE id=?", (pre_resolved,)).fetchone())
            if precard.get("canonical_name") in chosen_names:
                chosen.add(pre_resolved)
                continue
            q = min(2, DECK_SIZE - total)
            if q <= 0:
                break
            fn, why = mechanical_function(precard, main_text(con, precard))
            pre_name = precard["canonical_name"]
            cid_name = dict(con.execute(
                "SELECT canonical_name FROM cards WHERE id=?", (cid,)).fetchone())["canonical_name"]
            why_pre = (f"Pré-requisito de evolução (EVOL-001): {pre_name} "
                       f"evolui para {cid_name}")
            meta_pre = {"forced_by": "EVOL-001"}
            if pre_resolved != pre:
                why_pre += (f" [identidade {pre_resolved} preferida a {pre}: "
                            f"mesmo nome, tipo {precard['element']} coerente com a "
                            f"linha principal {main['element']}]")
                meta_pre["identity_basis"] = {
                    "requested": pre, "chosen": pre_resolved,
                    "criterion": f"mesmo nome + elemento {precard['element']} da linha principal"}
            if add(pre_resolved, precard, q, fn, why_pre, meta_pre):
                chosen.add(pre_resolved)
                added = True
        if not added:
            break

    return picks, total, n_decks


# ---------------------------------------------------------------------------
# 4) validação F3 (single source of truth)
# ---------------------------------------------------------------------------

def catalog_projection(con):
    evo = {}
    for r in con.execute("SELECT card_id, pre_evo_card_id FROM card_evolutions"):
        evo[r["card_id"]] = r["pre_evo_card_id"]
    cards = []
    for r in con.execute("SELECT id, canonical_name, category, stage, special_rule FROM cards"):
        sr = None
        if r["special_rule"]:
            if isinstance(r["special_rule"], str):
                try:
                    parsed = json.loads(r["special_rule"])
                except (json.JSONDecodeError, TypeError):
                    parsed = None
                sr = parsed if isinstance(parsed, dict) else None
            elif isinstance(r["special_rule"], dict):
                sr = r["special_rule"]
        cards.append({"card_id": r["id"], "name": r["canonical_name"],
                      "category": r["category"], "stage": r["stage"],
                      "evolves_from": evo.get(r["id"]),
                      "legal": True, "legal_formats": ["standard"],
                      "special_rule": sr})
    return {"cards": cards}


# ---------------------------------------------------------------------------
# 5) energia + estratégia (TEXTOS derivados da ficha real)
# ---------------------------------------------------------------------------

ELEMENT_PT = {"grass": "Grama", "fire": "Fogo", "water": "Água", "lightning": "Elétrico",
              "psychic": "Psíquico", "fighting": "Luta", "darkness": "Escuridão",
              "metal": "Metal", "dragon": "Dragão", "colorless": "Incolor"}


def energy_plan(con, main):
    att = attack_of(con, main["id"])
    if not att:
        return "Carta principal sem ataque no catálogo — plano de energia não aplicável.", []
    costs = json.loads(att["energy_cost"] or "[]")
    names = [ELEMENT_PT.get(e, e) for e in costs]
    lines = [f"Ataque principal '{att['name']}' exige: {', '.join(names) if names else 'nenhuma'}."]
    if costs and len(set(costs)) > 1:
        lines.append("Custo híbrido (tipos distintos): o anexo depende do fornecimento de "
                     "mais de um tipo — monte o pacote de energia para o tipo dominante e "
                     "aceite a incompatibilidade honestamente declarada.")
    lines.append("Energia NÃO está na lista de 20 (regra do formato Pocket: commit por "
                 "partida, provado nas 4.865 listas reais do corpus).")
    return "\n".join(lines), costs


def attack_of(con, card_id):
    best = None
    for r in con.execute("""SELECT name, energy_cost, damage, effect_text
            FROM card_attacks WHERE card_id=? ORDER BY sort_order""", (card_id,)):
        d = dict(r)
        if best is None or (d["damage"] or 0) > (best["damage"] or 0):
            best = d
    return best


def user_guide_main(con, main, n_decks, picks, curated=None):
    """UX-1 (card t_bd7c1cc1): "como funciona" em 2-4 linhas, gerado do que o
    deck REALMENTE contem — linha de evolucao presente na lista, ataque real
    da principal, motores de compra/busca, apoio e plano de energia.

    Substitui a guia fixa do F8, que citava "Gastly" mesmo em decks sem a
    carta (defeito confirmado em execucao real no deck-mega-altaria-ex-001:
    deck tem Swablu/Darkrai/Igglybuff e ZERO Gastly). Toda frase vem de
    card_roles.how_it_works, que so cita cartas presentes em `picks`.
    """
    return CR.how_it_works(con, main, picks, n_decks, curated)


def competitive_analysis(con, main, n_decks):
    """Tentativa REL com as tier tables do snapshot 30d (F7) — se existir."""
    rows = list(con.execute("""
        SELECT a.id, a.name, s.tier, s.share_pct, s.win_rate_pct, s.sample_decks, s.sample_matches
        FROM meta_snapshot_archetypes s JOIN meta_archetypes a ON a.id=s.archetype_id
        JOIN meta_snapshots sn ON sn.id=s.snapshot_id
        WHERE sn.window_end >= ? AND a.id LIKE '%gengar%'
        ORDER BY sn.window_end DESC LIMIT 10""",
        ((NOW - timedelta(days=30)).strftime("%Y-%m-%d"),)))
    verdict = "sem_evidencia" if not rows else "com_evidencia_limitada"
    return {
        "real_archetypes_with_main": [dict(r) for r in rows],
        "note": ("Arquétipos com esta carta no snapshot 30d da F7 (foto acima); tier só "
                 "existe quando passa os gates (>=20 listas e >=100 jogos). Sem tier = "
                 "dados ainda insuficientes para rotular desempenho.") if rows else
                ("Nenhum arquétipo com esta carta no meta 30d — toda análise aqui é "
                 "TEÓRICA (amostra citada; não é dado de torneio)."),
        "snapshot_verdict": verdict,
    }


# ---------------------------------------------------------------------------
# 6) persistência
# ---------------------------------------------------------------------------

def persist(con, spec, picks):
    slug = re.sub(r"[^a-z0-9]+", "-",
                  (spec["main_card"]["canonical_name"] or "main").lower()).strip("-")
    # BUG-001 (F15+, card t_fd4343fb): o proximo id deriva do MAIOR sufixo
    # existente, nunca de COUNT(*) — contagem nao e sequencia. A revalidacao
    # F8b furou a serie deck-mega-gengar-ex-% (001/004 removidos; restaram
    # 002/003) e o COUNT+1 recalculava o 003 JA existente ->
    # sqlite3.IntegrityError: UNIQUE constraint failed: decks.id (repro 2/2
    # da QA em t_3539dc38 + reproducao independente do CEO em 19/10).
    # Guarda extra: colisao residual (ex.: corrida entre dois builders)
    # incrementa o sufixo em vez de crashar o CLI.
    row = con.execute(
        "SELECT MAX(CAST(substr(id, -3) AS INTEGER)) FROM decks WHERE id LIKE ?",
        (f"deck-{slug}-%",)).fetchone()
    n = 1 + (row[0] if row and row[0] is not None else 0)
    while con.execute("SELECT 1 FROM decks WHERE id=?",
                      (f"deck-{slug}-{n:03d}",)).fetchone() is not None:
        n += 1
    deck_id = f"deck-{slug}-{n:03d}"
    con.execute("""INSERT INTO decks (id, name, format, total_cards, archetype_id, source_id)
        VALUES (?,?,?,?,NULL,?)""", (deck_id, spec["name"], spec["format"],
                                     DECK_SIZE, CORPUS_SOURCE_ID))
    for p in picks:
        con.execute("""INSERT INTO deck_cards (deck_id, card_id, print_id, quantity)
            VALUES (?,?,NULL,?)""", (deck_id, p["card_id"], p["quantity"]))
    con.execute("""INSERT INTO deck_specifications (deck_id, spec_json)
        VALUES (?,?)""", (deck_id, json.dumps(spec, ensure_ascii=False, sort_keys=True)))
    con.commit()
    return deck_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def list_mains(con, days):
    q = """SELECT c.id, c.canonical_name, COUNT(DISTINCT d.id) ndecks
        FROM cards c JOIN deck_cards dc ON dc.card_id=c.id
        JOIN decks d ON d.id=dc.deck_id
        WHERE c.category='pokemon' AND c.stage IN ('basic','stage1','stage2','mega_ex')
          AND d.id NOT LIKE 'deck-%'
        GROUP BY c.id HAVING ndecks >= 3 ORDER BY ndecks DESC"""
    out = []
    for r in con.execute(q):
        c = dict(con.execute("SELECT element, stage, hp, is_ex FROM cards WHERE id=?", (r["id"],)).fetchone())
        out.append({"card_id": r["id"], "name": r["canonical_name"],
                    "normalizable_real_decks": r["ndecks"], **c})
    return {"window_days": days, "supported_mains": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description="F8 deck-builder (validador F3 embutido)")
    ap.add_argument("main_card", nargs="?", help="carta principal (card_id ou nome canônico)")
    ap.add_argument("--card-id", dest="card_id", help=id_or_name_help())
    ap.add_argument("--days", type=int, default=30, help="janela empirica (padrao 30)")
    ap.add_argument("--list-mains", action="store_true", help="cartas principais suportadas")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--json", dest="json_out", action="store_true",
                    help="UX-1: saida JSON estavel para consumidores/agentes "
                         "(padrao sem --json: relatorio humano, uma linha por carta)")
    args = ap.parse_args(argv)

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row

    if args.list_mains:
        print(json.dumps(list_mains(con, args.days), ensure_ascii=False, indent=2))
        return 0

    ident = args.card_id or args.main_card
    if not ident:
        ap.error("informe a carta principal (posicional ou --card-id)")

    maincard = resolve_main(con, ident)
    if maincard is None:
        print(json.dumps({"veredicto": "carta_inexistente", "query": ident,
                          "reason": "nem card_id nem nome canônico resolvem no catálogo"},
                         ensure_ascii=False, indent=2))
        return 2

    picks, total, n_decks = build_list(con, maincard, args.days)

    if total != DECK_SIZE:
        print(json.dumps({"veredicto": "inconsistente",
                          "reason": f"núcleo empírico montou {total}/20; recusado "
                          f"(não persiste, não inventa)",
                          "main_card": maincard["canonical_name"],
                          "empirical_decks": n_decks}, ensure_ascii=False, indent=2))
        return 3

    # validação F3 OBRIGATÓRIA
    deck_payload = {"id": "f8-build", "name": f"build-{maincard['canonical_name']}",
                    "format": "standard",
                    "cards": [{"card_id": p["card_id"], "quantity": p["quantity"]}
                              for p in picks]}
    verdict = V3.validate_deck(deck_payload, catalog_projection(con))
    if verdict["legality"] != "legal":
        print(json.dumps({"veredicto": "ilegal", "violations": verdict["violations"],
                          "main": maincard["canonical_name"]}, ensure_ascii=False, indent=2))
        return 4

    curated_roles = CR.load_card_roles()
    card_lines = CR.deck_lines(con, maincard, picks, curated_roles)
    plan_text, _costs = energy_plan(con, maincard)
    guide_text = user_guide_main(con, maincard, n_decks, picks, curated_roles)
    comp = competitive_analysis(con, maincard, n_decks)

    veredicto = ("valido" if n_decks >= FALLBACK_THRESHOLD else "fallback")
    generated_at = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    spec = {
        "main_card": maincard,
        "name": f"{maincard['canonical_name']} — build F8",
        "format": "standard",
        "generated_at": generated_at,
        "veredicto": veredicto,
        "confidence_level": "medium" if n_decks >= FALLBACK_THRESHOLD else "low",
        "empirical_window_days": args.days,
        "empirical_decks": n_decks,
        "empirical_threshold_fallback": FALLBACK_THRESHOLD,
        "cards": picks,
        "energy_plan": plan_text,
        "how_to_play": guide_text,
        "card_lines": card_lines,
        "competitive_analysis": comp,
        "sources": [
            {"id": CORPUS_SOURCE_ID,
             "role": "corpus de decklists reais (4865 listas de torneio, janela da coleta 2026-09-09..2026-10-18); decks gerados (deck-%) excluídos do núcleo (F8b)"},
            {"id": "pocket.limitlesstcg.com",
             "role": "catálogo canônico (4.317 impressões / 2.319 identidades, coletado 2026-10-18)"},
        ],
        "legal_rules_satisfied": verdict["satisfied_rules"],
    }
    deck_id = persist(con, spec, picks)
    spec["deck_id"] = deck_id
    if not args.json_out:
        # UX-1: saida humana padrao — uma linha por carta (nome+quantidade a
        # esquerda, papel a direita) + bloco "como funciona". Zero card_id
        # cru; ids e origem do papel ficam no modo --json.
        print(CR.human_report(con, maincard, picks, n_decks, deck_id,
                              spec["name"], curated_roles))
        return 0
    print(json.dumps({"veredicto": spec["veredicto"],
                      "deck_id": deck_id,
                      "confidence_level": spec["confidence_level"],
                      "empirical_decks": n_decks,
                      "window_days": args.days,
                      "legality": "legal",
                      "satisfied_rules": verdict["satisfied_rules"],
                      "main_card": maincard["canonical_name"],
                      "cards": picks,
                      "energy_plan": plan_text,
                      "how_to_play": guide_text,
                      "card_lines": card_lines,
                      "competitive_analysis": comp,
                      "sources": spec["sources"]},
                     ensure_ascii=False, indent=2))
    return 0


def id_or_name_help():
    return "card_id do catalogo (sobrescreve o posicional)"


if __name__ == "__main__":
    sys.exit(main())
