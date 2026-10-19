#!/usr/bin/env python3
"""Composio -> Google Sheets v3 sync helper (project pokemon-pocket-intelligence)."""
import os, json, time, datetime, argparse

ENV_PATH = os.environ.get('C3PO_ENV', '/home/hermes/.hermes/profiles/c3po/.env')
SPREADSHEET_ID = '1a8iGqr4w7y-QgCKX6ChGcshYmjKdhdOIeuuvLBkGit0'
CONNECTED_ACCOUNT_ID = 'ca_lOfRvM1J5601'
USER_ID = 'default'
TOOLKIT_VERSION = '20261018_00'
# SDK: composio==0.22.0 in /opt/data/f5_venv; toolkit version pinned.


def _env():
    d = {}
    for line in open(ENV_PATH):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d

_env_cache = _env()

# SDK composio E OPCIONAL: instalado apenas no venv (composio==0.22.0,
# ver docs/TESTING.md). O modulo precisa ser importavel em qualquer
# interprete (ex.: suite de testes no python3 do sistema) — sem o SDK,
# client() falha tarde e com mensagem clara; o import nunca quebra.
try:
    from composio import Composio
    COMPOSIO_OK = True
except ImportError:  # SDK ausente neste interprete (suite sem venv)
    Composio = None
    COMPOSIO_OK = False

_client = None

def client():
    global _client
    if not COMPOSIO_OK:
        raise RuntimeError(
            'SDK composio ausente neste interprete — use o venv '
            '/opt/data/f5_venv (composio==0.22.0); ver docs/TESTING.md')
    if _client is None:
        _client = Composio(api_key=_env_cache['COMPOSIO_API_KEY'])
    return _client

def tk_execute(slug, args):
    return client().tools.execute(
        slug, user_id=USER_ID, connected_account_id=CONNECTED_ACCOUNT_ID,
        version=TOOLKIT_VERSION, arguments=args)

def sheets_api(path, method='GET', body=None):
    res = client().tools.proxy(
        f'https://sheets.googleapis.com/v4{path}',
        method=method, body=body, connected_account_id=CONNECTED_ACCOUNT_ID)
    return res if isinstance(res, dict) else getattr(res, 'data', res)

def get_sheet_names():
    r = tk_execute('GOOGLESHEETS_GET_SHEET_NAMES', {'spreadsheet_id': SPREADSHEET_ID})
    return (r.get('data') or {}).get('sheet_names') or []

def _clear(name, ncols):
    endc = chr(64 + ncols)
    return tk_execute('GOOGLESHEETS_CLEAR_VALUES',
        {'spreadsheet_id': SPREADSHEET_ID, 'sheet_name': name,
         'range': name + '!A1:' + endc + '2000'})

def _write(name, values):
    return tk_execute('GOOGLESHEETS_BATCH_UPDATE',
        {'spreadsheet_id': SPREADSHEET_ID, 'sheet_name': name,
         'values': values, 'valueInputOption': 'RAW'})

def _read(name, ncols):
    endc = chr(64 + ncols)
    return sheets_api('/spreadsheets/%s/values/%s!A1:%s2000' % (SPREADSHEET_ID, name, endc))

def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')

def log_audit(job_id, target_tab, rows_sent, status, t0, t1, error=''):
    values = [['job_id', 'target_tab', 'rows_sent', 'status', 'started_at',
               'finished_at', 'error'],
              [job_id, target_tab, rows_sent, status, t0, t1, error]]
    return sync_tab('Sincronizacoes', values, ncols=7)

def sync_tab(name, values, ncols, retries=3, backoff_s=4.0):
    """Clear + Write + Read back + Assert count. On failure: fila 'pending'.

    Protocolo idempotente: cada ciclo limpa o range alvo reescreve o bloco
    inteiro e confirma por leitura de volta. Em falha de rede o estado anterior
    permanece intacto ate o clear passar; se o clear passar e o write falhar,
    a aba fica temporariamente vazia ate o retry reconstruir (o SQLite segue
    canonico em qualquer caso)."""
    t0 = _now()
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if not _clear(name, ncols).get('successful'):
                raise RuntimeError('CLEAR FAIL')
            if not _write(name, values).get('successful'):
                raise RuntimeError('WRITE FAIL')
            d = _read(name, ncols)
            rows = [row for row in (d.get('values') or [])
                    if any(ch not in (None, '') for ch in row)]
            if len(rows) != len(values):
                raise RuntimeError('ASSERT: %d != expected %d' % (len(rows), len(values)))
            t1 = _now()
            try:
                log_audit(('job_%s' % t0.replace(':', '').replace('-', ''))[:15],
                          name, len(rows), 'success', t0, t1)
            except Exception:
                pass
            return {'rows': len(rows), 'status': 'success', 'job_id': t0}
        except Exception as ex:
            last_err = str(ex)
            if attempt < retries:
                time.sleep(backoff_s * attempt)
    try:
        log_audit(('job_%s' % t0.replace(':', '').replace('-', ''))[:15],
                  name, 0, 'pending', t0, _now(), last_err)
    except Exception:
        pass
    return {'status': 'pending', 'error': last_err, 'job_id': t0,
            'rows': 0, 'target_tab': name}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('tab')
    p.add_argument('--values', required=True)
    p.add_argument('--cols', default='30')
    a = p.parse_args()
    values = json.load(open(a.values)) if os.path.exists(a.values) else json.loads(a.values)
    print(json.dumps(sync_tab(a.tab, values, int(a.cols)), ensure_ascii=False))
