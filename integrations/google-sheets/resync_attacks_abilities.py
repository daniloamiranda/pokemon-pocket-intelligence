#!/usr/bin/env python3
"""F4c etapa 4 v3: re-sync Ataques/Habilidades no Sheets via chunks com
first_cell_location A1 (o wrapper padrao do sync quebra na aba grande).
Protocolo: clear total -> write em chunks -> read back -> assert totais."""
import sys, json, time
sys.path.insert(0, '/workspace/ARCOS/projetos/pokemon-pocket-intelligence/integrations/google-sheets')
import sync

def write_ab(tab, vals, ncols, chunk=800):
    assert sync.tk_execute('GOOGLESHEETS_CLEAR_VALUES', {
        'spreadsheet_id': sync.SPREADSHEET_ID, 'sheet_name': tab,
        'range': f'{tab}!A1:{chr(64+ncols)}2000'}).get('successful')
    for i in range(0, len(vals), chunk):
        part = vals[i:i + chunk]
        r = sync.tk_execute('GOOGLESHEETS_BATCH_UPDATE', {
            'spreadsheet_id': sync.SPREADSHEET_ID, 'sheet_name': tab,
            'values': part, 'valueInputOption': 'RAW', 'first_cell_location': f'A{i+1}'})
        if not r.get('successful'):
            raise RuntimeError(f'{tab} chunk@{i}: {r.get("error")}')
        print(f'  {tab}: chunk {i+1}..{i+len(part)} OK', flush=True)
    d = sync._read(tab, ncols)
    rows = [r for r in (d.get('values') or []) if any(c not in (None, '') for c in r)]
    return rows

atk = json.load(open('/tmp/f4c_atk.json'))   # header + 2183
ab = json.load(open('/tmp/f4c_ab.json'))     # header + 189

t0 = time.time()
rows_a = write_ab('Ataques', atk, 7)
print('Ataques rows=', len(rows_a), 'esperado', len(atk), 'OK' if len(rows_a) == len(atk) else 'FALHA')
rows_h = write_ab('Habilidades', ab, 5)
print('Habilidades rows=', len(rows_h), 'esperado', len(ab), 'OK' if len(rows_h) == len(ab) else 'FALHA')

# auditoria no Sheets tb: job em Sincronizacoes
try:
    sync.log_audit('f4c_resync_dedupe_ataques_habilidades', 'Ataques+Habilidades',
                   len(atk) + len(ab) - 2, 'success' if (len(rows_a) == len(atk) and len(rows_h) == len(ab)) else 'assert_fail',
                   '2026-10-18T20:00:00Z', time.strftime('%Y-%m-%dT%H:%M:%SZ'))
except Exception as e:
    print('audit log opt: ', e)
print(f'elapsed {time.time()-t0:.1f}s')
