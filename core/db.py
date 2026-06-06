"""
Conexión a SQLite, inicialización de tablas y helpers de configuración.
"""
import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path

DB_PATH   = Path(os.environ.get("DB_PATH", "torneo.db"))
STATIC_DIR = Path("static")


def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS jugadores (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                grupo  INTEGER DEFAULT 0,
                orden  INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS resultados (
                id      TEXT PRIMARY KEY,
                games_a INTEGER,
                games_b INTEGER,
                fase    TEXT DEFAULT 'prel'
            );
            CREATE TABLE IF NOT EXISTS mexicano_partidos (
                id      TEXT PRIMARY KEY,
                ronda   INTEGER,
                cancha  INTEGER,
                j1 TEXT, j2 TEXT, j3 TEXT, j4 TEXT,
                games_a INTEGER,
                games_b INTEGER
            );
            CREATE TABLE IF NOT EXISTS mexicano_config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        for key, val in [
            ("canchas",       "3"),
            ("rondas_prel",   "7"),
            ("rondas_final",  "5"),
            ("games_partido", "16"),
            ("tiempo_cancha", "90"),
            ("estado",        "config"),
            ("torneo_nombre", "Super Americano"),
        ]:
            con.execute("INSERT OR IGNORE INTO config VALUES (?,?)", (key, val))

        for key, val in [
            ("canchas",      "3"),
            ("rondas",       "7"),
            ("games",        "16"),
            ("ronda_actual", "0"),
            ("estado",       "idle"),
        ]:
            con.execute("INSERT OR IGNORE INTO mexicano_config VALUES (?,?)", (key, val))


@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ── Config helpers ────────────────────────────────────────────────────────────

def cfg_get(key: str) -> str:
    with get_db() as con:
        row = con.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""


def cfg_set(key: str, value: str):
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (key, value))


def mex_cfg_get(key: str) -> str:
    with get_db() as con:
        row = con.execute(
            "SELECT value FROM mexicano_config WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else ""


def mex_cfg_set(key: str, value: str):
    with get_db() as con:
        con.execute(
            "INSERT OR REPLACE INTO mexicano_config VALUES (?,?)", (key, value)
        )
