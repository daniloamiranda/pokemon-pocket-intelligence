"""F7 · Pipeline de metagame: raw Limitless -> estatistica -> snapshot/tiers no SQLite.

Regras documentadas (SKILL.md e docs/META.md — fonte desta implementacao):
- Taxonomia de arquetipo: `deck.id`/`deck.name` atribuidos pela propria Limitless
  (standings). Nenhum agrupamento inventado pelo projeto.
- Escopo padrao do snapshot: torneios publicos, formato STANDARD, com decklists
  obrigatorias e ao menos uma fase SWISS, players >= MIN_PLAYERS (8).
  NOEX/CUSTOM ficam fora (declarado no scope do snapshot). `format=null` no
  /details (organizador nao declarou) e ACEITO como standard — regra medida
  (139/200 torneios null em 19/10/2026); so declaracao explicita NOEX/CUSTOM exclui.
- share_pct  = listas do arquetipo / listas totais da janela (POPULARIDADE).
- win_rate_pct = wins/(wins+losses+ties) somando records dos players do arquetipo
  (DESEMPENHO). Popularidade nunca e apresentada como desempenho.
- consistencia = % dos torneios em que o arquetipo apareceu (>= 1 lista) em que seu
  melhor player terminou com wins > losses.
- matchups: jogos reais do /pairings; espelho (mesmo arquetipo) e jogos sem vencedor
  (empate/double loss/bye) ficam fora da taxa; confidence por amostra.
- Tiers (só para quem passa nos gates de amostra; regra F7 v1, janela do snapshot):
    gates: MIN_DECKS=20 listas e MIN_MATCHES=100 jogos
    S >= 55.0 | A >= 52.0 | B >= 49.0 | C >= 45.0 | D < 45.0
  Sem gates -> tier '' + basis 'sem_evidencia: ...' (amostra citada). F nunca emitido
  por regra (reservado a falha de integridade de dados comprovada).
- Snapshots sao APEND-ONLY por janela: mesma janela recalculada e substituida
  (novo collected_at); janelas diferentes coexistem. Raw nunca e apagado.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "pocket.sqlite"
DEFAULT_RAW = ROOT / "data" / "meta" / "raw"
SOURCE_ID = "play.limitlesstcg.com"
FINISHED_GRACE_H = 6  # torneio com inicio < 6h no passado pode estar em andamento
WATCH_CARDS = [s.strip() for s in os.environ.get("META_WATCH_CARDS", "Gengar").split(",")
               if s.strip()]  # cartas-alvo do relatorio (ex.: Mega Gengar ex): fora do snapshot

MIN_PLAYERS = int(os.environ.get("META_MIN_PLAYERS", "8"))
MIN_DECKS = int(os.environ.get("META_MIN_DECKS", "20"))
MIN_MATCHES = int(os.environ.get("META_MIN_MATCHES", "100"))
TIER_BANDS = [("S", 55.0), ("A", 52.0), ("B", 49.0), ("C", 45.0), ("D", None)]
CONFIDENCE_BANDS = [("high", 200), ("medium", 50), ("low", 0)]  # por n de jogos do par


# ---------------------------------------------------------------- utilidades DB
def open_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, timeout=30)
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA journal_mode = WAL;")
    return con


def ensure_source(con: sqlite3.Connection) -> None:
    con.execute(
        "INSERT OR IGNORE INTO sources (id, name, base_url, kind, tier, policy, requires_key, notes) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (SOURCE_ID, "Limitless Tournament Platform (Developer API)",
         "https://play.limitlesstcg.com/api", "api", "canonical",
         "Rate limit 50/5min por header; sem chave para este escopo; dados de torneio "
         "publicos; sem redistribuicao de conteudo de terceiros", 0,
         "Fonte-raiz do metagame (F7); agregadores sao validacao cruzada"),
    )
    con.commit()


def build_print_index(con: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, str]]:
    """{(set_code, number): (card_id, print_id)} — join da decklist ao catalogo."""
    idx: dict[tuple[str, str], tuple[str, str]] = {}
    for print_id, card_id, set_code, number in con.execute(
            "SELECT id, card_id, set_code, number FROM card_prints"):
        idx[(set_code, number)] = (card_id, print_id)
    return idx


# ---------------------------------------------------------------- parsing raw
def resolve_decklist(dl: dict, print_index: dict) -> tuple[list[tuple[str, str, int]], int]:
    """Converte {pokemon:[], trainer:[]} em [(card_id, print_id, count)] + n falhas."""
    resolved: list[tuple[str, str, int]] = []
    unresolved = 0
    for group in ("pokemon", "trainer"):
        for e in dl.get(group) or []:
            n = int(e.get("count") or 0)
            key = (e.get("set"), str(e.get("number")))
            hit = print_index.get(key) or print_index.get((key[0], key[1].lstrip("0") or "0"))
            if hit and n:
                resolved.append((hit[0], hit[1], n))
            else:
                unresolved += n
    return resolved, unresolved


def player_archetypes(standings: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """player -> (archetype_id, archetype_name) priorizando decklist presente."""
    arch_of: dict[str, str] = {}
    name_of: dict[str, str] = {}
    for row in standings:
        pid = row.get("player")
        if not pid:
            continue
        d = row.get("deck") or {}
        aid = d.get("id")
        if aid:
            arch_of[pid] = aid
            name_of[aid] = d.get("name") or aid
    return arch_of, name_of


def pairings_to_games(pairings: list[dict], arch_of: dict[str, str]
                      ) -> tuple[list[tuple[str, str, str]], dict[str, int]]:
    """Converte pairings em jogos (arch1, arch2, winner_arch) uteis para matchup.

    Excluidos (contabilizados, nao usados): bye/ausente, espelho, empate (0),
    double loss (-1), jogador sem taxonomia.
    """
    games: list[tuple[str, str, str]] = []
    excl = defaultdict(int)
    for i, m in enumerate(pairings):
        p1, p2 = m.get("player1"), m.get("player2")
        w = m.get("winner")
        if not p1 or not p2:
            excl["bye_ou_walkover"] += 1
            continue
        a1, a2 = arch_of.get(p1), arch_of.get(p2)
        if not a1 or not a2:
            excl["sem_taxonomia"] += 1
            continue
        if a1 == a2:
            excl["espelho"] += 1
            continue
        if w is None:
            excl["sem_vencedor"] += 1
            continue
        ws = str(w)
        if ws == "0":
            excl["empate"] += 1
            continue
        if ws == "-1":
            excl["double_loss"] += 1
            continue
        wa = arch_of.get(ws)
        if wa not in (a1, a2):
            excl["vencedor_fora_do_par"] += 1
            continue
        games.append((a1, a2, wa))
    return games, dict(excl)


# ---------------------------------------------------------------- janela/escopo
def load_window(raw: Path, days: int, end_date: str | None = None, full: bool = False):
    """Carrega torneios e aplica escopo. Retorna (window, eventos, stats_exclusao).

    full=False (default): janela rolante de `days` dias — tendencia temporal pura.
    full=True: SEM corte de janela — ingere todo o raw elegivel (modo --full).
      Existe para reconciliar coleta (35 dias, collect_meta.py) com analise
      (janela rolante menor): torneio elegivel fora da janela rolante NAO e lixo;
      descarta-lo em silencio foi o defeito F7b (41 elegiveis coletados e fora
      do banco, todos anteriores ao window_start do snapshot 30d).
      window.start = data do torneio elegivel mais antigo do raw.

    Exclusoes nomeadas: excl[motivo]=contagem e excl_nominal[motivo]=[tids] —
    nenhum torneio pode ser descartado sem rastro auditavel (regra F7b).
    """
    end = end_date or time.strftime("%Y-%m-%d", time.gmtime())
    start = time.strftime("%Y-%m-%d", time.gmtime(
        time.mktime(time.strptime(end, "%Y-%m-%d")) - (days - 1) * 86400))
    grace_cut = time.time() - FINISHED_GRACE_H * 3600
    excl = defaultdict(int)
    excl_nominal: dict[str, list[str]] = defaultdict(list)

    def _drop(tid: str, motivo: str) -> None:
        excl[motivo] += 1
        excl_nominal[motivo].append(tid)

    events = []
    pages_dir = raw / "pages"
    seen_ids: set[str] = set()
    for ppath in sorted(pages_dir.glob("page_*.json")):
        for t in json.loads(ppath.read_text()):
            tid = t.get("id")
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)
            d = t["date"][:10]
            if not full and (d < start or d > end):
                _drop(tid, "fora_da_janela")
                continue
            tdir = raw / "tournaments" / tid
            det_p, st_p, pr_p = (tdir / "details.json"), (tdir / "standings.json"), (tdir / "pairings.json")
            if not det_p.exists() or not st_p.exists():
                _drop(tid, "raw_incompleto")
                continue
            det = json.loads(det_p.read_text())
            if det.get("_http404"):
                _drop(tid, "details_404")
                continue
            if det.get("format") in ("NOEX", "CUSTOM") or (
                    det.get("format") is not None and det.get("format") != "STANDARD"):
                _drop(tid, "formato_nao_standard")
                continue
            if not det.get("isPublic", True):
                _drop(tid, "nao_publico")
                continue
            if not det.get("decklists", False):
                _drop(tid, "sem_decklists")
                continue
            if not any(ph.get("type") == "SWISS" for ph in det.get("phases") or []):
                _drop(tid, "sem_swiss")
                continue
            if (t.get("players") or 0) < MIN_PLAYERS:
                _drop(tid, "players_minimo")
                continue
            ts = time.mktime(time.strptime(t["date"][:19], "%Y-%m-%dT%H:%M:%S"))
            if ts > grace_cut:
                _drop(tid, "possivelmente_em_andamento")
                continue
            st = json.loads(st_p.read_text())
            if not isinstance(st, list):   # 404 memorizado = dict {"_http404": true}
                _drop(tid, "standings_404")
                continue
            pr: list | dict = {"_http404": True}
            if pr_p.exists():
                pr = json.loads(pr_p.read_text())
            events.append({"tid": tid, "date": d, "name": t.get("name") or det.get("name") or tid,
                           "players": t.get("players"), "details": det,
                           "standings": st, "pairings": pr if isinstance(pr, list) else []})
    if full and events:
        start = min(ev["date"] for ev in events)
    load_excl = {"excl": dict(excl), "excl_nominal": dict(excl_nominal)}
    return {"start": start, "end": end}, events, load_excl


# ---------------------------------------------------------------- estatistica
def compute_stats(window, events, print_index, load_excl=None):
    """Agrega decks/records/jogos por arquetipo na janela."""
    decks_by_arch = defaultdict(int)
    cards_by_arch = defaultdict(lambda: defaultdict(int))   # arch -> card_id -> somas
    arch_names: dict[str, str] = {}
    decklist_count = 0
    bad_lists = 0
    resolved_entries = 0
    unresolved_entries = 0
    rec_w = defaultdict(int); rec_l = defaultdict(int); rec_t = defaultdict(int)
    arch_events = defaultdict(set)                          # arch -> set(tids)
    event_best = defaultdict(dict)                          # tid -> {arch: (wins, losses)}
    card_decks = defaultdict(int)                           # card_id -> n decks com a carta
    card_copies = defaultdict(int)                          # card_id -> copias totais
    match_count = 0
    pair_games = defaultdict(lambda: defaultdict(int))      # (a,b) -> winner -> n

    for ev in events:
        tid = ev["tid"]
        arch_of, name_of = player_archetypes(ev["standings"])
        arch_names.update(name_of)
        for row in ev["standings"]:
            pid = row.get("player")
            if not pid:
                continue
            d = row.get("deck") or {}
            aid = d.get("id")
            rec = row.get("record") or {}
            if aid:
                arch_events[aid].add(tid)
                rec_w[aid] += int(rec.get("wins") or 0)
                rec_l[aid] += int(rec.get("losses") or 0)
                rec_t[aid] += int(rec.get("ties") or 0)
                w, l = int(rec.get("wins") or 0), int(rec.get("losses") or 0)
                cur = event_best[tid].get(aid)
                if cur is None or w > cur[0]:
                    event_best[tid][aid] = (w, l)
            dl = row.get("decklist")
            if not dl:
                continue
            decklist_count += 1
            if not aid:
                continue
            decks_by_arch[aid] += 1
            resolved, unresolved = resolve_decklist(dl, print_index)
            resolved_entries += sum(n for _, _, n in resolved)
            unresolved_entries += unresolved
            total = sum(n for _, _, n in resolved) + unresolved
            if total != 20 or unresolved > 0:
                bad_lists += 1
            for card_id, _print_id, n in resolved:
                cards_by_arch[aid][card_id] += n
                card_copies[card_id] += n
            for card_id in {c for c, _p, _n in resolved}:
                card_decks[card_id] += 1
        games, _excl = pairings_to_games(ev["pairings"], arch_of)
        match_count += len(ev["pairings"]) if isinstance(ev["pairings"], list) else 0
        for a1, a2, wa in games:
            key = (a1, a2) if a1 <= a2 else (a2, a1)
            pair_games[key][wa] += 1

    return {
        "exclusions": load_excl if load_excl is not None else {"excl": {}, "excl_nominal": {}},
        "window": window, "decks_by_arch": decks_by_arch, "cards_by_arch": cards_by_arch,
        "decklist_count": decklist_count, "bad_lists": bad_lists,
        "resolved_entries": resolved_entries, "unresolved_entries": unresolved_entries,
        "rec_w": rec_w, "rec_l": rec_l, "rec_t": rec_t,
        "arch_events": arch_events, "event_best": event_best, "arch_names": arch_names,
        "card_decks": card_decks, "card_copies": card_copies,
        "match_count": match_count, "pair_games": pair_games,
    }


def win_rate(w: int, l: int, t: int) -> float:
    tot = w + l + t
    return round(100.0 * (w + 0.5 * t) / tot, 2) if tot else None


def compute_tiers(stats) -> dict[str, dict]:
    """Regra F7 v1 (documentada): gates de amostra + faixas por win_rate."""
    out = {}
    for arch in set(list(stats["decks_by_arch"]) + list(stats["rec_w"])):
        decks = stats["decks_by_arch"].get(arch, 0)
        w, l, t = stats["rec_w"].get(arch, 0), stats["rec_l"].get(arch, 0), stats["rec_t"].get(arch, 0)
        n_games = w + l + t
        wr = win_rate(w, l, t)
        evs = stats["arch_events"].get(arch, set())
        consist = consistency_pct(stats, arch)
        if decks >= MIN_DECKS and n_games >= MIN_MATCHES and wr is not None:
            tier = next(name for name, floor in TIER_BANDS if floor is None or wr >= floor)
            basis = (f"win_rate {wr}% em {n_games} jogos e {decks} listas "
                     f"(gates ok: >={MIN_DECKS} listas, >={MIN_MATCHES} jogos); regra F7 v1")
        else:
            tier = ""
            basis = (f"sem_evidencia: {decks} listas (gate {MIN_DECKS}) e/ou "
                     f"{n_games} jogos (gate {MIN_MATCHES}) insuficientes para tier")
        out[arch] = {"tier": tier, "basis": basis, "decks": decks, "n_games": n_games,
                     "win_rate_pct": wr, "events": len(evs), "consistency_pct": consist}
    return out


def consistency_pct(stats, arch: str) -> float | None:
    """% dos torneios em que o arquetipo apareceu (>=1 lista) em que seu melhor
    record no torneio teve wins > losses (0.0-100.0; None sem comparecimento)."""
    tids = stats["arch_events"].get(arch) or set()
    if not tids:
        return None
    good = 0
    for tid in tids:
        rec = (stats["event_best"].get(tid) or {}).get(arch)
        if rec and rec[0] > rec[1]:
            good += 1
    return round(100.0 * good / len(tids), 1)


def matchup_confidence(n: int) -> str:
    for name, floor in CONFIDENCE_BANDS:
        if n >= floor:
            return name
    return "low"


# ---------------------------------------------------------------- persistencia
def persist(con: sqlite3.Connection, window, events, stats, tiers, days: int,
            print_index: dict, full: bool = False) -> str:
    snap_id = f"snap-{days}d-{window['end']}" if not full else f"snap-full-{window['end']}"
    scope = (f"public standard Swiss, decklists obrigatorias, players>={MIN_PLAYERS}, "
             f"formato STANDARD (Limitless API; NOEX/CUSTOM fora); "
             + (f"janela {window['start']}..{window['end']}" if not full else
                f"SEM corte de janela (modo full, reconciliacao F7b): todo o raw "
                f"elegivel, dados {window['start']}..{window['end']}"))
    con.execute("BEGIN")
    # torneios + results (upsert idempotente)
    for ev in events:
        con.execute("""INSERT INTO tournaments (id,name,date,format,source_id) VALUES (?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET name=excluded.name, date=excluded.date,
                       format=excluded.format, collected_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
                    (ev["tid"], ev["name"], ev["date"] + "T12:00:00.000Z", "STANDARD", SOURCE_ID))
    # snapshot (janela igual e recriada; janelas distintas coexistem)
    con.execute("DELETE FROM tiers WHERE snapshot_id=?", (snap_id,))
    con.execute("DELETE FROM meta_snapshot_archetypes WHERE snapshot_id=?", (snap_id,))
    con.execute("DELETE FROM meta_snapshots WHERE id=?", (snap_id,))
    con.execute("""INSERT INTO meta_snapshots (id,window_start,window_end,scope,tournament_count,
                   decklist_count,match_count,source_id) VALUES (?,?,?,?,?,?,?,?)""",
                (snap_id, window["start"], window["end"], scope, len(events),
                 stats["decklist_count"], stats["match_count"], SOURCE_ID))
    # arquetipos + snapshot rows + tiers (ANTES de decks/matches/matchups: FK em meta_archetypes)
    for arch, t in sorted(tiers.items()):
        share = round(100.0 * t["decks"] / stats["decklist_count"], 2) if stats["decklist_count"] else None
        core = [c for c, _n in sorted(stats["cards_by_arch"].get(arch, {}).items(),
                                      key=lambda kv: -kv[1])][:8]
        con.execute("""INSERT INTO meta_archetypes (id,name,tier,tier_basis,core_cards,sample_decks,source_id)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET name=excluded.name, tier=excluded.tier,
                       tier_basis=excluded.tier_basis, core_cards=excluded.core_cards,
                       sample_decks=excluded.sample_decks""",
                    (arch, stats["arch_names"].get(arch, arch), t["tier"], t["basis"], json.dumps(core), t["decks"], SOURCE_ID))
        con.execute("""INSERT INTO meta_snapshot_archetypes (snapshot_id,archetype_id,share_pct,
                       win_rate_pct,tier,sample_decks,sample_matches) VALUES (?,?,?,?,?,?,?)""",
                    (snap_id, arch, share, t["win_rate_pct"], t["tier"] or None,
                     t["decks"], t["n_games"]))
        if t["tier"]:
            con.execute("""INSERT INTO tiers (id,snapshot_id,archetype_id,tier,basis,sample_decks,sample_matches)
                           VALUES (?,?,?,?,?,?,?)""",
                        (f"tier-{snap_id}-{arch}", snap_id, arch, t["tier"], t["basis"],
                         t["decks"], t["n_games"]))
    # archetype_cards (nucleo citavel para o deck-builder F8)
    for arch in tiers:
        decks_n = tiers[arch]["decks"]
        if decks_n >= MIN_DECKS:
            for card_id, nsum in stats["cards_by_arch"].get(arch, {}).items():
                # presenca >= 40% dos decks do arquetipo (2 copias -> ~2n somas)
                if nsum >= 0.4 * decks_n:
                    con.execute("""INSERT INTO archetype_cards (archetype_id,card_id) VALUES (?,?)
                                   ON CONFLICT(archetype_id,card_id) DO NOTHING""", (arch, card_id))
    # decks + deck_cards por torneio (id deterministico tournament+player)
    # contrato decks.total_cards = 20 (CHECK): listas ilegíveis/incompletas NAO viram
    # deck (contadas em bad_lists); share/records continuam contando todas as listas
    for ev in events:
        for row in ev["standings"]:
            dl = row.get("decklist")
            if not dl:
                continue
            aid = (row.get("deck") or {}).get("id")
            pid = row.get("player") or ""
            resolved, unresolved = resolve_decklist(dl, print_index)
            total = sum(n for _, _, n in resolved) + unresolved
            if total != 20 or unresolved > 0:
                continue
            deck_id = f"ll-{ev['tid']}-{pid[:80]}"
            placing = row.get("placing")
            con.execute("""INSERT INTO decks (id,name,format,total_cards,archetype_id,source_id)
                           VALUES (?,?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                           archetype_id=excluded.archetype_id""",
                        (deck_id, f"{ev['name']} — {row.get('name') or pid}",
                         "STANDARD", total, aid, SOURCE_ID))
            con.execute("DELETE FROM deck_cards WHERE deck_id=?", (deck_id,))
            for card_id, print_id, n in resolved:
                con.execute("""INSERT INTO deck_cards (deck_id,card_id,print_id,quantity)
                               VALUES (?,?,?,?) ON CONFLICT(deck_id,card_id,print_id)
                               DO UPDATE SET quantity=excluded.quantity""",
                            (deck_id, card_id, print_id, n))
            if placing:
                con.execute("""INSERT INTO tournament_results (tournament_id,placement,deck_id,archetype_id)
                               VALUES (?,?,?,?) ON CONFLICT(tournament_id,placement,deck_id)
                               DO NOTHING""", (ev["tid"], max(placing, 1), deck_id, aid))
    # matches (id deterministico; espelho/bye/empate guardados para auditoria)
    for ev in events:
        arch_of, _n = player_archetypes(ev["standings"])
        for seq, m in enumerate(ev["pairings"]):
            mid = f"{ev['tid']}:{m.get('phase', 1)}:{m.get('round', 0)}:{seq}"
            p1, p2 = m.get("player1") or "", m.get("player2") or ""
            w = m.get("winner")
            ws = "" if w is None else str(w)
            con.execute("""INSERT INTO tournament_matches (id,tournament_id,phase,round,seq,
                           player1,player2,winner,archetype1_id,archetype2_id)
                           VALUES (?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET winner=excluded.winner""",
                        (mid, ev["tid"], m.get("phase", 1), m.get("round", 0), seq, p1, p2, ws,
                         arch_of.get(p1), arch_of.get(p2)))
    # matchups por par (win_rate do lado a do par ordenado; amostra = jogos do par)
    for (a1, a2), winners in sorted(stats["pair_games"].items()):
        n = sum(winners.values())
        if not n:
            continue
        wr1 = round(100.0 * winners.get(a1, 0) / n, 2)
        mu_id = f"mu-{'full' if full else f'{days}d'}-{window['end']}-{a1}--{a2}"
        con.execute("""INSERT INTO matchups (id,archetype_a,archetype_b,win_rate_a_pct,sample_size,
                       window_period,source_id,confidence,sample_matches)
                       VALUES (?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(archetype_a,archetype_b,window_period,source_id)
                       DO UPDATE SET win_rate_a_pct=excluded.win_rate_a_pct,
                       sample_size=excluded.sample_size, confidence=excluded.confidence,
                       sample_matches=excluded.sample_matches""",
                    (mu_id, a1, a2, wr1, n, f"{window['start']}..{window['end']}",
                     SOURCE_ID, matchup_confidence(n), n))
    con.execute(
        "INSERT INTO audit_logs (actor,table_name,record_key,action,before_json,after_json,reason) "
        "VALUES (?,?,?,?,?,?,?)",
        ("F7", "meta_snapshots", snap_id, "insert", None,
         json.dumps({"tournaments": len(events), "decklists": stats["decklist_count"],
                     "match_rows": stats["match_count"],
                     "exclusions": stats.get("exclusions", {}).get("excl", {})}),
         (f"rebuild janela {window['start']}..{window['end']} (apend-only por janela)"
          if not full else
          f"rebuild FULL sem corte de janela {window['start']}..{window['end']} "
          f"(reconciliacao F7b; apend-only por janela)")))
    con.commit()
    return snap_id


# ---------------------------------------------------------------- report
def report(snap_id, window, events, stats, tiers, name_index: dict | None = None) -> dict:
    ranked = sorted(tiers.items(), key=lambda kv: (-(kv[1]["win_rate_pct"] or 0), -kv[1]["decks"]))
    by_tier: dict[str, list] = defaultdict(list)
    for arch, t in ranked:
        by_tier[t["tier"] or "sem_evidencia"].append({
            "archetype": arch, "share_pct": round(100.0 * t["decks"] / stats["decklist_count"], 2)
            if stats["decklist_count"] else None, "win_rate_pct": t["win_rate_pct"],
            "decks": t["decks"], "games": t["n_games"],
            "consistency_pct": t["consistency_pct"]})
    rep = {
        "snapshot_id": snap_id, "window": window, "scope_filters": {
            "min_players": MIN_PLAYERS, "min_decks_gate": MIN_DECKS, "min_matches_gate": MIN_MATCHES,
            "format": "STANDARD", "decklists": True, "swiss": True},
        "exclusions": stats.get("exclusions", {}),
        "totals": {"tournaments": len(events), "decklists": stats["decklist_count"],
                   "pairing_rows": stats["match_count"], "matchup_games": sum(
                       sum(v.values()) for v in stats["pair_games"].values()),
                   "bad_lists": stats["bad_lists"],
                   "resolved_entries": stats["resolved_entries"],
                   "unresolved_entries": stats["unresolved_entries"]},
        "tier_rule": {"gates": {"min_decks": MIN_DECKS, "min_matches": MIN_MATCHES},
                      "bands": {n: f for n, f in TIER_BANDS},
                      "note": "win_rate = (w+0.5t)/(w+l+t) dos records; share e popularidade, tier e desempenho"},
        "tiers": {k: by_tier[k] for k in ["S", "A", "B", "C", "D", "sem_evidencia"] if k in by_tier},
    }
    # cartas-alvo (ex.: Mega Gengar ex): amostra citada, "sem_evidencia" quando 0
    watch = {}
    for target in WATCH_CARDS:
        hits = {cid: nm for cid, nm in (name_index or {}).items()
                if target.lower() in nm.lower()}
        decks = sum(stats["card_decks"].get(cid, 0) for cid in hits)
        copies = sum(stats["card_copies"].get(cid, 0) for cid in hits)
        watch[target] = {
            "card_ids": sorted(hits), "decks": decks, "copies": copies,
            "verdict": ("sem_evidencia: %d listas / %d copias na janela %s..%s"
                        % (decks, copies, window["start"], window["end"]))
            if decks < MIN_DECKS else "com_amostra",
        }
    rep["watch_cards"] = watch
    return rep


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="F7 meta pipeline: raw -> snapshot/tiers")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--days", type=int, default=30, choices=[7, 14, 30])
    ap.add_argument("--end", type=str, default=None, help="data fim UTC YYYY-MM-DD (default hoje)")
    ap.add_argument("--report", type=Path, default=None, help="caminho do JSON de relatorio")
    ap.add_argument("--full", action="store_true",
                    help="SEM corte de janela: ingere todo o raw elegivel (reconciliacao "
                         "F7b); snapshot snap-full-<data> coexiste com as janelas rolantes")
    args = ap.parse_args()

    global _INDEX
    con = open_db(args.db)
    # banco sem schema (primeira execucao em db novo): aplica migracoes do repo
    has_reg = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table' "
                          "AND name='schema_migrations'").fetchone()[0]
    con.close()
    if not has_reg:
        import subprocess
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "db_migrate.py"),
                            "--db", str(args.db)], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[meta] FALHA na migracao do banco {args.db}: {r.stderr}")
            return 2
        print("[meta] migracoes aplicadas em", args.db, flush=True)
    con = open_db(args.db)
    ensure_source(con)
    _INDEX = [build_print_index(con)]
    name_index = {cid: nm for cid, nm in con.execute("SELECT id, canonical_name FROM cards")}

    window, events, load_excl = load_window(args.raw, args.days, args.end, full=args.full)
    excl = load_excl["excl"]
    print(f"[meta] {'modo FULL (sem corte de janela)' if args.full else 'janela'} "
          f"{window['start']}..{window['end']}: {len(events)} torneios no escopo "
          f"(exclusoes: {excl})", flush=True)
    for motivo, tids in sorted(load_excl["excl_nominal"].items()):
        print(f"[meta] excluidos {motivo} ({len(tids)}): {', '.join(sorted(tids))}", flush=True)
    if not events:
        print("[meta] NENHUM evento no escopo — nada a fazer (raw incompleto?); saindo sem escrita.")
        return 2
    stats = compute_stats(window, events, _INDEX[0], load_excl)
    tiers = compute_tiers(stats)
    snap_id = persist(con, window, events, stats, tiers, args.days, _INDEX[0], full=args.full)
    rep = report(snap_id, window, events, stats, tiers, name_index)
    out = args.report or (ROOT / "data" / "meta" / "reports" / f"{snap_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[meta] snapshot {snap_id}: {rep['totals']}", flush=True)
    for band in ("S", "A", "B", "C", "D", "sem_evidencia"):
        rows = rep["tiers"].get(band) or []
        top = ", ".join(f"{r['archetype']}({r['win_rate_pct']}%/{r['decks']}L)" for r in rows[:5])
        print(f"[meta] {band}: {len(rows)} | {top}", flush=True)
    print(f"[meta] relatorio: {out}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
