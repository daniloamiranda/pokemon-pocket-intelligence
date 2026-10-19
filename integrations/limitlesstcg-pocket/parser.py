"""Parser HTML de paginas do pocket.limitlesstcg.com.

Entrada: HTML das paginas de listagem de conjunto (display=compact) e ficha de carta.
Saida: dicts puros (sem dependencias externas) para o loader do SQLite.

Formato sondado em 18/10/2026:
- bloco por carta: <div class="card-classic"> ... <div class="card-set-info">SET #N</div>
- card-text-name: nome + link /cards/{set}/{num}
- card-text-title: nome - Elemento - NNN HP (elemento/HP ausentes em trainer)
- card-text-type: Pokemon|Trainer + - Basic/Stage N/Item/Tool/Supporter/Stadium + Evolves from link
- card-text-ability: Ability: Nome / efeito
- card-text-attack: ptcg-symbol custo + Nome [x|+] / efeito
- card-text-wrr: Weakness: X <br> Retreat: N
- card-text-mega-rule / ex-symbol rule: regras especiais
- card-prints-versions: tabela de versoes (set #num + raridade em simbolos)
- imagem: limitlesstcg.nyc3.../pocket/{SET}/{SET}_{NNN}_EN_SM.webp
"""
from __future__ import annotations

import re
from html import unescape

ELEMENT_MAP = {
    "Grass": "grass", "Fire": "fire", "Water": "water", "Lightning": "lightning",
    "Psychic": "psychic", "Fighting": "fighting", "Darkness": "darkness",
    "Metal": "metal", "Dragon": "dragon", "Colorless": "colorless",
}
WEAKNESS_VALID = {k for k in ELEMENT_MAP if k != "Dragon"}
COST_SYMBOLS = {"G": "grass", "R": "fire", "W": "water", "L": "lightning",
                "P": "psychic", "F": "fighting", "D": "darkness", "M": "metal",
                "N": "dragon", "C": "colorless"}

CARD_RE = re.compile(
    r'<div class="card-classic">(.*?)<div class="card-set-info">([A-Z0-9-]*[ab]?)\s*#([0-9]+)</div>',
    re.S)
NAME_RE = re.compile(r'<span class="card-text-name"><a href="/cards/[^"]+">(.*?)</a></span>')
TITLE_RE = re.compile(r'<p class="card-text-title">(.*?)</p>', re.S)
TYPE_RE = re.compile(r'<p class="card-text-type">(.*?)</p>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
MONTHS = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
          "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
          "December": 12}


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s)


# F13+: comentarios HTML (ex.: bloco GTM '<!-- Google tag (gtag.js) -->') nunca
# fazem parte de nome/dado extraido; o '(' dentro deles contaminava o fallback
# <title> e fossilizou 'Promo-A – ... <!-- Google tag' no catalogo (INSERT OR
# IGNORE = primeiro dono eterno, mesma classe do F7c).
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
SOURCE_SUFFIX_RE = re.compile(r"\s*[–—-]\s*Limitless TCG Pocket Database\s*$")


def strip_html_comments(s: str) -> str:
    return HTML_COMMENT_RE.sub("", s)


def clean_expansion_name(s: str) -> str:
    """Nome de conjunto: sem comentarios HTML e sem sufixo de fonte."""
    return SOURCE_SUFFIX_RE.sub("", clean(strip_html_comments(s))).strip()


def clean(s: str) -> str:
    return " ".join(unescape(strip_tags(s)).split())


def rarity_from_symbols(s: str) -> str | None:
    """◊ = carta normal (contagem de diamantes), ☆ = carta rara extra (2-star etc)."""
    s = s.strip()
    if not s:
        return None
    stars = s.count("☆")
    diamonds = s.count("◊")
    if stars and not diamonds:
        return f"star{stars}"
    if diamonds:
        return f"diamond{diamonds}"
    return None


def parse_set_page(html: str, set_code: str) -> list[dict]:
    """Extrai entradas compactas por carta da pagina do conjunto."""
    cards = []
    for m in CARD_RE.finditer(html):
        block, s_set, s_num = m.group(1), m.group(2), m.group(3)
        entry = {"set": s_set, "number": s_num, "source_page": f"/cards/{s_set}/{s_num}"}
        nm = NAME_RE.search(block)
        if nm:
            entry["name"] = clean(nm.group(1))
        img = re.search(r"pocket/([A-Z0-9ab]+)/\1_(\d+)_EN[^\"']*\.webp", block)
        if img:
            entry["image_url"] = (
                f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/"
                f"{img.group(1)}/{img.group(1)}_{img.group(2)}_EN_SM.webp")
        cards.append(entry)
    return cards


def parse_set_metadata(html: str) -> dict:
    """Nome/data/contagem de cartas do conjunto exibidos no infobox."""
    out: dict = {}
    mi = re.search(
        r'infobox-heading[^>]*>\s*(.*?)\s*</div>\s*<div class="infobox-line">\s*'
        r'([0-9]+)(?:st|nd|rd|th)?\s+([A-Z][a-z]+)\s+([0-9]{4})\s*[•]?\s*([0-9]+)\s*Cards',
        html, re.S)
    if mi:
        out["name"] = re.sub(r"\s*\([A-Z0-9]+\)\s*$", "", clean_expansion_name(mi.group(1)))
        mm = MONTHS.get(mi.group(3))
        if mm:
            out["release_date"] = f"{mi.group(4)}-{mm:02d}-{int(mi.group(2)):02d}"
        out["card_count"] = int(mi.group(5))
    else:
        # F13+: fallback PRESO AO ELEMENTO <title>...</title> (a regex antiga
        # [^(]+ atravessava </title> ate o '(' do comentario GTM; e apos o
        # strip de comentarios, o JS inline 'function gtag(' viraria o novo
        # vazamento — por isso a captura termina no </title> de verdade).
        # Corte no '(' do codigo do conjunto preservado (legado:
        # 'Genetic Apex (A1) – ...' -> 'Genetic Apex').
        tm = re.search(r"<title>(?P<t>[^<]*)</title>", strip_html_comments(html))
        if tm:
            t = tm.group("t")
            cut = t.find("(")
            if cut != -1:
                t = t[:cut]
            if t.strip():
                out["name"] = clean_expansion_name(t)
    return out


def _parse_cost(symbol_text: str) -> list[str]:
    return [COST_SYMBOLS[c] for c in symbol_text if c in COST_SYMBOLS]


def parse_grid_entries(html: str, set_code: str) -> list[dict]:
    """Fallback para paginas de grid (conjuntos promo sem card-set-info)."""
    entries = []
    for m in re.finditer(
            r'href="/cards/([A-Z0-9-]+)/([0-9]+)"><img[^>]*src="([^"]+)"', html):
        s_set, s_num, img_src = m.groups()
        if s_set != set_code:
            continue
        entries.append({"set": s_set, "number": s_num, "source_page": f"/cards/{s_set}/{s_num}",
                        "image_url": img_src})
    return entries


def parse_card_page(html: str, set_code: str, number: str) -> dict | None:
    """Extrai ficha completa de uma carta. Retorna None se pagina invalida."""
    main = re.search(r'<div class="card-profile">(.*?)<div class="card-prints">', html, re.S)
    block = main.group(1) if main else html

    img = re.search(r'<img[^>]+src="(https://limitlesstcg\.nyc3[^"]+\.webp)"', block)
    image_url = img.group(1) if img else None

    nm = NAME_RE.search(block)
    if not nm:
        return None
    card: dict = {"set": set_code, "number": number, "image_url": image_url}
    card["name"] = unescape(strip_tags(nm.group(1))).strip()

    tit = TITLE_RE.search(block)
    title_txt = clean(tit.group(1)) if tit else ""
    for sym, elem in ELEMENT_MAP.items():
        if f"- {sym}" in title_txt:
            card["element"] = elem
            break
    hm = re.search(r"-\s*([0-9]+) HP", title_txt)
    if hm:
        card["hp"] = int(hm.group(1))

    ty = TYPE_RE.search(block)
    ty_txt = clean(ty.group(1)) if ty else ""
    ev = re.search(r"Evolves from\s*<a href=\"/cards\?q=name:([a-z0-9_]+)\"", block)
    if ev:
        card["evolves_from"] = ev.group(1)
    if "Pokémon" in ty_txt or "Pokemon" in ty_txt:
        card["category"] = "pokemon"
        if "Mega" in ty_txt or "Mega" in card["name"]:
            card["stage"] = "mega_ex"
        elif "Stage 2" in ty_txt:
            card["stage"] = "stage2"
        elif "Stage 1" in ty_txt:
            card["stage"] = "stage1"
        else:
            card["stage"] = "basic"
    elif "Supporter" in ty_txt:
        card["category"] = "trainer_supporter"
    elif "Tool" in ty_txt:
        card["category"] = "pokemon_tool"
    elif "Stadium" in ty_txt:
        card["category"] = "trainer_stadium"
    else:
        card["category"] = "trainer_item"

    wr = re.search(r"Weakness:\s*([A-Za-z]+)", block)
    if wr and wr.group(1) in WEAKNESS_VALID:
        card["weakness_element"] = ELEMENT_MAP[wr.group(1)]
    rt = re.search(r"Retreat:\s*([0-9])", block)
    if rt:
        card["retreat_cost"] = int(rt.group(1))

    attacks = []
    for am in re.finditer(
            r'<div class="card-text-attack">\s*<p class="card-text-attack-info">\s*'
            r'<span class="ptcg-symbol">([^<]*)</span>\s*(.*?)</p>\s*'
            r'<p class="card-text-attack-effect">\s*(.*?)\s*</p>', block, re.S):
        sym_txt, info_txt, eff_txt = am.groups()
        info_clean = clean(info_txt)
        dm = re.search(r"([0-9]+)[x+]?$", info_clean)
        dmg = int(dm.group(1)) if dm else None
        name = re.sub(r"\s*[0-9]+[x+]?$", "", info_clean).strip()
        attacks.append({
            "name": name,
            "energy_cost": _parse_cost(sym_txt),
            "damage": dmg,
            "effect_text": clean(eff_txt) or None,
        })
    card["attacks"] = attacks

    abilities = []
    for abm in re.finditer(
            r'<div class="card-text-ability">\s*<p class="card-text-ability-info">\s*'
            r'(?:Ability:\s*)?([^<]*?)</p>\s*<p class="card-text-ability-effect">\s*(.*?)\s*</p>',
            block, re.S):
        abilities.append({"name": clean(abm.group(1)),
                          "effect_text": clean(abm.group(2)), "kind": "ability"})
    card["abilities"] = abilities

    special = None
    mr = re.search(r'class="card-text-wrr card-text-mega-rule">(.*?)</p>', block, re.S)
    if mr:
        special = clean(mr.group(1))
    else:
        xr = re.search(r'ex-symbol">e</span><span class="copy-only">x</span> rule:([^<]*)', block)
        if xr:
            special = "ex rule: " + clean(xr.group(1))
    card["special_rule"] = special
    card["is_ex"] = 1 if special else 0

    am = re.search(r"Illustrated by\s*<a[^>]*>\s*(.*?)\s*</a>", block, re.S)
    if am:
        card["artist"] = clean(am.group(1))

    versions = []
    vt = re.search(r'<table class="card-prints-versions">(.*?)</table>', html, re.S)
    if vt:
        for row in re.finditer(
                r'<tr(?P<cur>(?:\s+class="current")?)\s*>\s*<td>\s*'
                r'(?:<a\s+(?:[^>]*?href="(?P<href>/cards/[^"]+)")?[^>]*>|<a>)\s*'
                r'(?P<setname>.*?)\s*<span class="prints-table-card-number">#(?P<num>[0-9]+)</span>\s*'
                r'</a>\s*</td>\s*<td>(?P<rar>.*?)</td>', vt.group(1), re.S):
            href = row.group("href")
            if row.group("cur"):
                vset = set_code
            elif not href:
                # F7c: linha de versao SEM href (ex.: promo P-A/P-B servida como <a> nu)
                # e INRESOLVIVEL — cair no fallback set_code atribuia o print da promo
                # ao numero HOMONIMO do proprio set (P-A#46 do Gible virava o print
                # A2a#46 do Gabite = print fantasma). Pular a linha: print errado e
                # pior que print ausente (INSERT OR IGNORE fossiliza o erro).
                continue
            else:
                pm = re.search(r"/cards/([A-Za-z0-9-]+)/", href)
                vset = pm.group(1) if pm else set_code
            versions.append({
                "set": vset,
                "number": row.group("num"),
                "rarity": rarity_from_symbols(strip_tags(row.group("rar"))),
            })
    card["versions"] = versions
    return card
