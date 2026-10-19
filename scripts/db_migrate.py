#!/usr/bin/env python3
"""F2 · Runner de migração idempotente do SQLite canônico.

Uso:
  python3 scripts/db_migrate.py                 # aplica migrações pendentes
  python3 scripts/db_migrate.py --db PATH       # banco alvo (padrão data/pocket.sqlite)
  python3 scripts/db_migrate.py --status        # mostra estado das migrações

Idempotência: cada migração é registrada em schema_migrations com checksum SHA-256
do SQL; migração já aplicada é pulada (verificado por checksum — divergência falha alto).
PRAGMAs por conexão: foreign_keys=ON, journal_mode=WAL.
"""
import argparse
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "database" / "migrations"
# UNICO caminho default do banco canônico (F4b): data/pocket.sqlite (dado operacional,
# fora do git). database/ é exclusivo de migrations/schemas/backups — o runner NUNCA
# cria banco canônico em caminho concorrente.
DEFAULT_DB = ROOT / "data" / "pocket.sqlite"

SQLITE_CONN = sqlite3.connect  # facilita monkeypatch em testes


def compute_checksum(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


def list_migrations() -> list[tuple[str, Path, str]]:
    """Retorna [(version, path, checksum)] ordenado por version (semântica de prefixo)."""
    items = []
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = re.match(r"^(\d+)_", p.name)
        if not m:
            raise ValueError(f"Nome de migration fora do padrão: {p.name}")
        items.append((m.group(1), p, compute_checksum(p.read_text(encoding="utf-8"))))
    items.sort(key=lambda t: (int(t[0]), t[1].name))
    return items


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def ensure_registry(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            checksum   TEXT NOT NULL
        )
    """)
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT version, checksum FROM schema_migrations").fetchall()
    return {v: c for v, c in rows}


def migrate(db_path: Path = None, dry_run: bool = False) -> int:
    db_path = db_path or DEFAULT_DB
    migrations = list_migrations()
    if not migrations:
        print("Nenhuma migração encontrada em", MIGRATIONS_DIR)
        return 0

    conn = connect(db_path)
    try:
        ensure_registry(conn)
        existing = applied_versions(conn)
        applied = 0
        for version, path, checksum in migrations:
            if version in existing:
                if existing[version] != checksum:
                    raise RuntimeError(
                        f"Migração {version} divergente: checksum em banco difere do arquivo "
                        f"({existing[version]} != {checksum}). Migration é imutável — crie uma nova.")
                if not dry_run:
                    print(f"  [skip] {path.name} — já aplicada (checksum ok)")
                continue
            print(f"  [apply] {path.name} → {db_path}")
            if dry_run:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                conn.executescript(sql)
                # registra a migração no topo do próprio esquema
                conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations(version, name, checksum) VALUES (?,?,?)",
                    (version, path.name, checksum),
                )
            except sqlite3.Error as e:
                conn.rollback()
                raise RuntimeError(f"Falha na migração {version}: {e}") from e
            conn.commit()
            applied += 1
        # pós-condições (critério de aceitação 3)
        fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        wal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        fts_ok = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='cards_fts'"
        ).fetchone()[0] == 1
        conn.execute("SELECT count(*) FROM cards_fts")
        conn.commit()
        print(f"Pós-condições: foreign_keys={fk_on}, journal_mode={wal}, FTS5={'OK' if fts_ok else 'AUSENTE'}")
        if not (fk_on and wal.lower() == "wal" and fts_ok):
            raise RuntimeError("Pós-condições de migração não satisfeitas")
        print(f"OK — {applied} migração(ões) aplicada(s), {len(migrations) - applied} já existente(s).")
        return 0
    finally:
        conn.close()


def status(db_path: Path = None) -> int:
    db_path = db_path or DEFAULT_DB
    if not db_path.exists():
        print("Banco não existe ainda:", db_path)
        return 0
    conn = sqlite3.connect(db_path)
    try:
        ensure_registry(conn)
        existing = {v: c for v, c in conn.execute("SELECT version, checksum FROM schema_migrations").fetchall()}
        for version, path, checksum in list_migrations():
            mark = "APLICADO" if version in existing else "PENDENTE "
            print(f"  [{mark}] {path.name}")
        return 0
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Runner de migração SQLite idempotente")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="Caminho do banco SQLite")
    ap.add_argument("--status", action="store_true", help="Apenas mostra estado")
    ap.add_argument("--dry-run", action="store_true", help="Simula sem gravar")
    args = ap.parse_args()
    if args.status:
        return status(args.db)
    try:
        return migrate(args.db, dry_run=args.dry_run)
    except (RuntimeError, ValueError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
