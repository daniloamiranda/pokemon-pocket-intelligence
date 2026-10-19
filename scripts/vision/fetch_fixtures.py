#!/usr/bin/env python3
"""F6b - fetch_fixtures: baixa as fixtures de visao do CDN do Limitless.

As imagens de carta sao artes de terceiros (TPC/DeNA servidas pelo CDN limitlesstcg)
e NAO sao versionadas no repositorio (docs/ATTRIBUTION.md: nao redistribuir arte).
Este script baixa as fixtures sob demanda para tests/vision/ a partir das URLs
canonicas do catalogo (padrao {SET}_{NNN:03d}_EN_SM.webp, idempotente - pula o
download se o arquivo ja existe e e valido).

Uso:
    python3 scripts/vision/fetch_fixtures.py                # baixa tudo que falta
    python3 scripts/vision/fetch_fixtures.py --only bad     # so fixtures_bad/
    python3 scripts/vision/fetch_fixtures.py --list         # lista sem baixar

Nota: as fixtures_bad sao geradas LOCALMENTE (trunc/corrupt/copy) a partir das boas,
reproduzindo o pipeline usado nas F6/F6b.fixture satisfeita e verificada por
tamanho > 0 e assinatura webp (RIFF....WEBP).
"""
import argparse
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DB_DEFAULT = REPO / 'data' / 'pocket.sqlite'
CDN = 'https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/{set}/{set}_{num:03d}_EN_SM.webp'

# fixtures reais: nome do arquivo no disco -> (set_code, number) no catalogo
GOOD = [
    ('A1_001.webp', 'A1', 1), ('A1_122.webp', 'A1', 122), ('A1_123.webp', 'A1', 123),
    ('A1a_001.webp', 'A1a', 1), ('A2_001.webp', 'A2', 1), ('A3_001.webp', 'A3', 1),
    ('A4_001.webp', 'A4', 1), ('B1_001.webp', 'B1', 1), ('B2_001.webp', 'B2', 1),
    ('B2b_039.webp', 'B2b', 39), ('B4_001.webp', 'B4', 1),
    ('B4b_021.webp', 'B4b', 21), ('B4b_141.webp', 'B4b', 141), ('B4b_429.webp', 'B4b', 429),
]
# fixtures degradadas: geradas localmente a partir das boas (ver degradar())
BAD_RECIPE = {
    'A1_001_corrupt.webp': ('A1_001.webp', 'corrupt'),
    'A1_001_trunc.webp': ('A1_001.webp', 'trunc'),
    'B4b_141_corrupt.webp': ('B4b_141.webp', 'corrupt'),
    'B4b_141_lying_name.webp': ('B4b_141.webp', 'copy'),   # nome de arquivo mentiroso
    'B4b_141_trunc.webp': ('B4b_141.webp', 'trunc'),
}


def url_for(set_code, number):
    return CDN.format(set=set_code, num=int(number))


def list_targets():
    print('# fixture                    -> URL')
    for fname, setc, num in GOOD:
        dst = REPO / 'tests' / 'vision' / 'fixtures' / fname
        print('%-28s -> %s %s' % (fname, url_for(setc, num),
                                  '(ok no disco)' if dst.is_file() and dst.stat().st_size > 0 else '(falta)'))
    print('# fixtures_bad: geradas LOCALMENTE (trunc/corrupt/copy) a partir das boas;'
          ' rodar este script primeiro e depois degradar()')


def degrade(src: Path, dst: Path, kind: str):
    """Reproduz as fixtures degradadas usadas nos testes F6/F6b."""
    data = src.read_bytes()
    if kind == 'copy':
        dst.write_bytes(data)
    elif kind == 'trunc':
        dst.write_bytes(data[: len(data) // 3])
    elif kind == 'corrupt':
        b = bytearray(data)
        # corrompe a metade final (rodape/numero) preservando o cabecalho decodificavel
        mid = len(b) // 2
        for i in range(mid, len(b)):
            b[i] = b[i] ^ 0xFF
        dst.write_bytes(bytes(b))


def db_image_url(db_path, set_code, number):
    db = sqlite3.connect(db_path)
    try:
        row = db.execute("SELECT image_url FROM card_prints WHERE set_code=? AND number=?",
                         (set_code, str(int(number)))).fetchone()
        return row[0] if row else url_for(set_code, number)
    finally:
        db.close()


def fetch(only=None, db_path=None):
    db_path = str(db_path or DB_DEFAULT)
    fixtures = REPO / 'tests' / 'vision' / 'fixtures'
    fixtures.mkdir(parents=True, exist_ok=True)
    n_ok = n_skip = n_fail = 0
    for fname, setc, num in GOOD:
        if only == 'bad':
            continue
        dst = fixtures / fname
        if dst.is_file() and dst.stat().st_size > 0:
            n_skip += 1
            continue
        url = db_image_url(db_path, setc, num)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = r.read()
            if not (data[:4] == b'RIFF' and data[8:12] == b'WEBP'):
                raise ValueError('conteudo nao parece webp: %d bytes' % len(data))
            dst.write_bytes(data)
            n_ok += 1
            print('ok     %-28s <- %s (%d bytes)' % (fname, url, len(data)))
        except Exception as e:  # noqa: BLE001
            n_fail += 1
            print('FALHA  %-28s <- %s : %s' % (fname, url, e), file=sys.stderr)
    # fixtures_bad derivadas
    bad = REPO / 'tests' / 'vision' / 'fixtures_bad'
    bad.mkdir(parents=True, exist_ok=True)
    for fname, (src_name, kind) in BAD_RECIPE.items():
        dst = bad / fname
        if dst.is_file() and dst.stat().st_size > 0:
            n_skip += 1
            continue
        src = fixtures / src_name
        if not src.is_file():
            print('FALHA  %-28s (fonte %s ausente - rode as boas primeiro)' % (fname, src_name),
                  file=sys.stderr)
            n_fail += 1
            continue
        degrade(src, dst, kind)
        n_ok += 1
        print('ok     %-28s (gerada: %s)' % (fname, kind))
    print('resumo: baixadas=%d, ja_em_disco=%d, falhas=%d' % (n_ok, n_skip, n_fail))
    return 0 if n_fail == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description='baixa fixtures de visao do CDN Limitless')
    ap.add_argument('--only', choices=['good', 'bad'], help='subconjunto a processar')
    ap.add_argument('--list', action='store_true', help='lista alvos e URLs, nao baixa')
    ap.add_argument('--catalog', default=str(DB_DEFAULT))
    args = ap.parse_args(argv)
    if args.list:
        list_targets()
        return 0
    return fetch(args.only, args.catalog)


if __name__ == '__main__':
    sys.exit(main())
