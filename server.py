"""
Super Americano Pádel — Backend
================================
FastAPI + SQLite + WebSockets
Todos los clientes conectados reciben actualizaciones en tiempo real.
"""

import json
import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Configuración ─────────────────────────────────────────────────────────────
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "padel2024")  # cambiá esto
DB_PATH        = Path(os.environ.get("DB_PATH", "torneo.db"))
STATIC_DIR     = Path("static")

# Fixture 6 jugadores (formato canónico)
FIXTURE_6 = [(0,1,2,3),(1,3,2,4),(2,5,3,4),(3,4,5,0),(4,0,5,1),(5,3,0,1),(1,2,0,5)]

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Super Americano Pádel")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── Base de datos ─────────────────────────────────────────────────────────────
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
                id       TEXT PRIMARY KEY,
                games_a  INTEGER,
                games_b  INTEGER,
                fase     TEXT DEFAULT 'prel'
            );
            CREATE TABLE IF NOT EXISTS mexicano_partidos (
                id       TEXT PRIMARY KEY,
                ronda    INTEGER,
                cancha   INTEGER,
                j1       TEXT, j2 TEXT,
                j3       TEXT, j4 TEXT,
                games_a  INTEGER,
                games_b  INTEGER
            );
            CREATE TABLE IF NOT EXISTS mexicano_config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        # Valores por defecto
        defaults = [
            ("canchas",       "3"),
            ("rondas_prel",   "7"),
            ("rondas_final",  "5"),
            ("games_partido", "16"),
            ("tiempo_cancha", "90"),
            ("estado",        "config"),   # config | prel | final
            ("torneo_nombre", "Super Americano"),
        ]
        mex_defaults = [
            ("canchas",       "3"),
            ("rondas",        "7"),
            ("games",         "16"),
            ("ronda_actual",  "0"),
            ("estado",        "idle"),     # idle | jugando | finalizado
        ]
        for key, val in mex_defaults:
            con.execute("INSERT OR IGNORE INTO mexicano_config VALUES (?,?)", (key, val))
        for key, val in defaults:
            con.execute("INSERT OR IGNORE INTO config VALUES (?,?)", (key, val))

@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

def cfg_get(key: str) -> str:
    with get_db() as con:
        row = con.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""

def cfg_set(key: str, value: str):
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (key, value))

# ── Lógica Mexicano ───────────────────────────────────────────────────────────

def mex_cfg_get(key: str) -> str:
    with get_db() as con:
        row = con.execute("SELECT value FROM mexicano_config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""

def mex_cfg_set(key: str, value: str):
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO mexicano_config VALUES (?,?)", (key, value))

def mex_get_partidos(ronda: int = None):
    with get_db() as con:
        if ronda is not None:
            rows = con.execute(
                "SELECT * FROM mexicano_partidos WHERE ronda=? ORDER BY cancha",
                (ronda,)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM mexicano_partidos ORDER BY ronda, cancha"
            ).fetchall()
        return [dict(r) for r in rows]

def mex_get_stats():
    """Calcula stats acumuladas de todos los jugadores en mexicano."""
    with get_db() as con:
        partidos = con.execute(
            "SELECT * FROM mexicano_partidos WHERE games_a IS NOT NULL"
        ).fetchall()
    stats = {}
    for p in partidos:
        p = dict(p)
        ga, gb = p["games_a"] or 0, p["games_b"] or 0
        pts_a = 3 if ga > gb else 1 if ga == gb else 0
        pts_b = 3 if gb > ga else 1 if ga == gb else 0
        for j in [p["j1"], p["j2"]]:
            if j not in stats: stats[j] = {"gf":0,"gc":0,"pts":0,"pj":0}
            stats[j]["gf"] += ga; stats[j]["gc"] += gb
            stats[j]["pts"] += pts_a; stats[j]["pj"] += 1
        for j in [p["j3"], p["j4"]]:
            if j not in stats: stats[j] = {"gf":0,"gc":0,"pts":0,"pj":0}
            stats[j]["gf"] += gb; stats[j]["gc"] += ga
            stats[j]["pts"] += pts_b; stats[j]["pj"] += 1
    return stats

def mex_armar_ronda(jugadores: list, ronda: int, canchas: int, stats: dict = None):
    """
    Arma los partidos de una ronda del mexicano.
    Ronda 1: parejas random.
    Siguientes: ordenar por pts desc, emparejar 1+2 vs 3+4, etc.
    """
    import random as rnd
    jug = [j for j in jugadores if j.strip()]
    n = len(jug)

    if stats and ronda > 1:
        # Ordenar por puntos, desempate por diferencia de games
        jug = sorted(jug, key=lambda j: (
            -(stats.get(j, {}).get("pts", 0)),
            -(stats.get(j, {}).get("gf", 0) - stats.get(j, {}).get("gc", 0))
        ))
    else:
        rnd.shuffle(jug)

    partidos = []
    cancha = 1
    i = 0
    while i + 3 < n:
        pid = f"mex-{ronda}-{cancha}"
        partidos.append({
            "id": pid, "ronda": ronda, "cancha": cancha,
            "j1": jug[i], "j2": jug[i+1],
            "j3": jug[i+2], "j4": jug[i+3],
            "games_a": None, "games_b": None
        })
        cancha += 1
        i += 4

    with get_db() as con:
        for p in partidos:
            con.execute(
                "INSERT OR REPLACE INTO mexicano_partidos VALUES (?,?,?,?,?,?,?,?,?)",
                (p["id"], p["ronda"], p["cancha"],
                 p["j1"], p["j2"], p["j3"], p["j4"],
                 p["games_a"], p["games_b"])
            )
    return partidos

def mex_ronda_completa(ronda: int) -> bool:
    """Verifica si todos los partidos de una ronda tienen resultado."""
    with get_db() as con:
        sin_resultado = con.execute(
            "SELECT COUNT(*) FROM mexicano_partidos WHERE ronda=? AND games_a IS NULL",
            (ronda,)
        ).fetchone()[0]
    return sin_resultado == 0

def get_mexicano_state() -> dict:
    """Estado completo del modo mexicano."""
    with get_db() as con:
        cfg = {r["key"]: r["value"]
               for r in con.execute("SELECT * FROM mexicano_config").fetchall()}
        jugadores = [dict(r) for r in
                     con.execute("SELECT * FROM jugadores ORDER BY grupo, orden").fetchall()]

    ronda_actual = int(cfg.get("ronda_actual", 0))
    rondas_total = int(cfg.get("rondas", 7))
    stats = mex_get_stats()

    # Partidos de la ronda actual
    partidos_actuales = mex_get_partidos(ronda_actual) if ronda_actual > 0 else []
    # Historial completo
    historial = mex_get_partidos()

    # Ranking
    nombres = [j["nombre"] for j in jugadores]
    ranking = sorted(nombres, key=lambda j: (
        -(stats.get(j, {}).get("pts", 0)),
        -(stats.get(j, {}).get("gf", 0) - stats.get(j, {}).get("gc", 0))
    ))

    return {
        "type": "mexicano_state",
        "config": cfg,
        "jugadores": jugadores,
        "ronda_actual": ronda_actual,
        "rondas_total": rondas_total,
        "partidos_actuales": partidos_actuales,
        "historial": historial,
        "stats": stats,
        "ranking": ranking,
        "ronda_completa": mex_ronda_completa(ronda_actual) if ronda_actual > 0 else False,
        "finalizado": ronda_actual >= rondas_total and ronda_actual > 0,
    }

# ── WebSocket broadcast ───────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self.active -= dead

manager = ConnectionManager()

# ── Helpers fixture ───────────────────────────────────────────────────────────
def gen_fixture(grupo: list, rondas: int) -> list:
    """
    Genera fixture para N jugadores.
    Primero usa todas las combinaciones únicas sin repetir compañero.
    Si rondas > combinaciones únicas, rota desde el principio (válido en americano).
    """
    n = len(grupo)
    # Generar todas las combinaciones posibles sin repetir compañero
    seen, base = set(), []
    if n == 6:
        # Usar fixture canónico primero (mejor balance)
        for a,b,c,d in FIXTURE_6:
            base.append((grupo[a], grupo[b], grupo[c], grupo[d]))
        # Si necesitamos más, agregar combinaciones restantes
        if rondas > len(base):
            seen_pairs = set()
            for a,b,c,d in FIXTURE_6:
                seen_pairs.add(tuple(sorted((a,b))))
                seen_pairs.add(tuple(sorted((c,d))))
            for a in range(n):
                for b in range(a+1,n):
                    for c in range(n):
                        for d in range(c+1,n):
                            if a in (c,d) or b in (c,d): continue
                            pa = tuple(sorted((a,b)))
                            pc = tuple(sorted((c,d)))
                            k = tuple(sorted([pa,pc]))
                            if k not in seen and pa not in seen_pairs and pc not in seen_pairs:
                                seen.add(k)
                                base.append((grupo[a],grupo[b],grupo[c],grupo[d]))
    else:
        for a in range(n):
            for b in range(a+1,n):
                for c in range(n):
                    for d in range(c+1,n):
                        if a in (c,d) or b in (c,d): continue
                        k = tuple(sorted([(min(a,b),max(a,b)),(min(c,d),max(c,d))]))
                        if k not in seen:
                            seen.add(k)
                            base.append((grupo[a],grupo[b],grupo[c],grupo[d]))

    if rondas <= len(base):
        return base[:rondas]

    # Si pedimos más rondas que combinaciones únicas → ciclar desde el principio
    # Esto es válido en americano (se repiten parejas pero no consecutivamente)
    result = []
    for i in range(rondas):
        result.append(base[i % len(base)])
    return result

def calcular_rondas_sugeridas(tiempo_min: int, games_partido: int,
                              n_jugadores: int = 18, n_canchas: int = 3) -> dict:
    mins_x_partido  = round(games_partido * 1.5)
    mins_x_ronda    = mins_x_partido + 3
    mins_finales    = mins_x_ronda * 4
    tiempo_prel     = tiempo_min - mins_finales
    rondas_x_tiempo = max(3, tiempo_prel // mins_x_ronda)
    n_x_grupo = max(4, round(n_jugadores / n_canchas))
    rondas_max_sin_repetir = n_x_grupo - 1
    rondas_prel = min(rondas_x_tiempo, rondas_max_sin_repetir)
    rondas_final = 4
    return {
        "rondas_prel":            int(rondas_prel),
        "rondas_prel_x_tiempo":   int(rondas_x_tiempo),
        "rondas_max_sin_repetir": int(rondas_max_sin_repetir),
        "rondas_final":           rondas_final,
        "mins_x_partido":         mins_x_partido,
        "mins_x_ronda":           mins_x_ronda,
        "tiempo_total_est":       int(rondas_prel * mins_x_ronda + mins_finales),
        "n_x_grupo":              n_x_grupo,
    }

def get_full_state() -> dict:
    """Devuelve todo el estado del torneo para sincronizar clientes."""
    with get_db() as con:
        config = {r["key"]: r["value"]
                  for r in con.execute("SELECT key,value FROM config").fetchall()}
        jugadores = [dict(r) for r in
                     con.execute("SELECT * FROM jugadores ORDER BY grupo, orden").fetchall()]
        resultados = {r["id"]: {"ga": r["games_a"], "gb": r["games_b"], "fase": r["fase"]}
                      for r in con.execute("SELECT * FROM resultados").fetchall()}

    n_canchas   = int(config.get("canchas", 3))
    rondas_prel = int(config.get("rondas_prel", 7))
    rondas_fin  = int(config.get("rondas_final", 5))

    # Agrupar jugadores
    grupos = {}
    for j in jugadores:
        g = j["grupo"]
        if g not in grupos:
            grupos[g] = []
        grupos[g].append(j["nombre"])

    grupos_list = [grupos[k] for k in sorted(grupos.keys())] if grupos else []

    # Fixtures
    fixtures_prel  = [gen_fixture(g, rondas_prel) for g in grupos_list]
    fixtures_final = {}
    if grupos_list:
        # Stats para clasificar
        stats = calcular_stats(grupos_list, fixtures_prel, resultados, "prel")
        clasificados = clasificar(grupos_list, stats)
        for copa, jug in clasificados.items():
            fixtures_final[copa] = gen_fixture(jug, rondas_fin)

    n_jug = len(jugadores)
    sugerencia = calcular_rondas_sugeridas(
        int(config.get("tiempo_cancha", 90)),
        int(config.get("games_partido", 16)),
        n_jugadores=n_jug if n_jug > 0 else 18,
        n_canchas=n_canchas
    )

    return {
        "type":           "state",
        "config":         config,
        "jugadores":      jugadores,
        "grupos":         grupos_list,
        "fixtures_prel":  [[(list(p)) for p in f] for f in fixtures_prel],
        "fixtures_final": {k: [list(p) for p in v] for k,v in fixtures_final.items()},
        "resultados":     resultados,
        "sugerencia":     sugerencia,
    }

def calcular_stats(grupos, fixtures_prel, resultados, fase="prel"):
    stats = {}
    for gi, grupo in enumerate(grupos):
        for j in grupo:
            stats[j] = {"pj":0,"gf":0,"gc":0,"pts":0,"gi":gi}
        for ri, partido in enumerate(fixtures_prel[gi]):
            j1,j2,j3,j4 = partido
            key = f"prel-{gi}-{ri}"
            res = resultados.get(key)
            if not res or res["ga"] is None: continue
            ga, gb = int(res["ga"]), int(res["gb"])
            for j in [j1,j2]:
                if j in stats: stats[j]["gf"]+=ga; stats[j]["gc"]+=gb; stats[j]["pj"]+=1
            for j in [j3,j4]:
                if j in stats: stats[j]["gf"]+=gb; stats[j]["gc"]+=ga; stats[j]["pj"]+=1
            p1 = 3 if ga>gb else 1 if ga==gb else 0
            p2 = 3 if gb>ga else 1 if ga==gb else 0
            for j in [j1,j2]:
                if j in stats: stats[j]["pts"]+=p1
            for j in [j3,j4]:
                if j in stats: stats[j]["pts"]+=p2
    return stats

def clasificar(grupos, stats):
    """Devuelve clasificados por copa: oro=[1°,2° de cada grupo], etc."""
    sorted_grupos = [
        sorted(g, key=lambda j: (-stats.get(j,{}).get("pts",0),
                                  -(stats.get(j,{}).get("gf",0)-stats.get(j,{}).get("gc",0)),
                                  -stats.get(j,{}).get("gf",0)))
        for g in grupos
    ]
    copas = {"oro":[], "plata":[], "bronce":[]}
    for pos_idx, copa in [(slice(0,2),"oro"),(slice(2,4),"plata"),(slice(4,6),"bronce")]:
        for sg in sorted_grupos:
            copas[copa].extend(sg[pos_idx])
    return copas

# ── Rutas ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/state")
async def get_state():
    return JSONResponse(get_full_state())

# Auth
class AuthReq(BaseModel):
    password: str

@app.post("/api/auth")
async def auth(req: AuthReq):
    if req.password == ADMIN_PASSWORD:
        return {"ok": True, "role": "admin"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

# Guardar config
class ConfigReq(BaseModel):
    password: str
    config: dict

@app.post("/api/config")
async def save_config(req: ConfigReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    for k, v in req.config.items():
        if k in ("canchas","rondas_prel","rondas_final","games_partido",
                 "tiempo_cancha","torneo_nombre","estado"):
            cfg_set(k, str(v))
    state = get_full_state()
    await manager.broadcast(state)
    return {"ok": True}

# Guardar jugadores
class JugadoresReq(BaseModel):
    password: str
    jugadores: list   # [{"nombre": str, "grupo": int, "orden": int}]

@app.post("/api/jugadores")
async def save_jugadores(req: JugadoresReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM jugadores")
        for j in req.jugadores:
            con.execute(
                "INSERT INTO jugadores (nombre,grupo,orden) VALUES (?,?,?)",
                (j["nombre"], j.get("grupo",0), j.get("orden",0))
            )
    state = get_full_state()
    await manager.broadcast(state)
    return {"ok": True}

# Guardar resultado
class ResultadoReq(BaseModel):
    password: str
    id: str
    games_a: int
    games_b: int
    fase: str = "prel"

@app.post("/api/resultado")
async def save_resultado(req: ResultadoReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute(
            "INSERT OR REPLACE INTO resultados VALUES (?,?,?,?)",
            (req.id, req.games_a, req.games_b, req.fase)
        )
    state = get_full_state()
    await manager.broadcast(state)
    return {"ok": True}

# Nuevo torneo
class ResetReq(BaseModel):
    password: str

@app.post("/api/reset")
async def reset(req: ResetReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM resultados")
        con.execute("DELETE FROM jugadores")
        con.execute("UPDATE config SET value='config' WHERE key='estado'")
    state = get_full_state()
    await manager.broadcast(state)
    return {"ok": True}

# Shuffle grupos
class ShuffleReq(BaseModel):
    password: str
    nombres: list

@app.post("/api/shuffle")
async def shuffle(req: ShuffleReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    nombres = [n for n in req.nombres if n.strip()]
    random.shuffle(nombres)
    n_canchas = int(cfg_get("canchas") or 3)
    tam = max(4, round(len(nombres) / n_canchas))
    jugadores = []
    for i, nombre in enumerate(nombres):
        jugadores.append({"nombre": nombre, "grupo": i // tam, "orden": i % tam})
    with get_db() as con:
        con.execute("DELETE FROM jugadores")
        for j in jugadores:
            con.execute(
                "INSERT INTO jugadores (nombre,grupo,orden) VALUES (?,?,?)",
                (j["nombre"], j["grupo"], j["orden"])
            )
    state = get_full_state()
    await manager.broadcast(state)
    return {"ok": True, "jugadores": jugadores}

# Sugerencia de rondas
@app.get("/api/sugerencia")
async def sugerencia(tiempo: int = 90, games: int = 16, jugadores: int = 18, canchas: int = 3):
    return calcular_rondas_sugeridas(tiempo, games, jugadores, canchas)

# WebSocket
# ── Rutas Mexicano ────────────────────────────────────────────────────────────

@app.get("/api/mexicano/state")
async def get_mex_state():
    return JSONResponse(get_mexicano_state())

class MexConfigReq(BaseModel):
    password: str
    canchas: int = 3
    rondas: int = 7
    games: int = 16

@app.post("/api/mexicano/config")
async def mex_config(req: MexConfigReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    mex_cfg_set("canchas", str(req.canchas))
    mex_cfg_set("rondas",  str(req.rondas))
    mex_cfg_set("games",   str(req.games))
    state = get_mexicano_state()
    await manager.broadcast(state)
    return {"ok": True}

class MexIniciarReq(BaseModel):
    password: str

@app.post("/api/mexicano/iniciar")
async def mex_iniciar(req: MexIniciarReq):
    """Inicia el torneo mexicano: arma la ronda 1 random."""
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        jugadores = [r["nombre"] for r in
                     con.execute("SELECT nombre FROM jugadores ORDER BY grupo, orden").fetchall()]
    if len(jugadores) < 4:
        raise HTTPException(status_code=400, detail="Se necesitan al menos 4 jugadores")
    # Limpiar partidos anteriores
    with get_db() as con:
        con.execute("DELETE FROM mexicano_partidos")
    mex_cfg_set("ronda_actual", "1")
    mex_cfg_set("estado", "jugando")
    mex_armar_ronda(jugadores, 1, int(mex_cfg_get("canchas")))
    state = get_mexicano_state()
    await manager.broadcast(state)
    return {"ok": True}

class MexResultadoReq(BaseModel):
    password: str
    id: str
    games_a: int
    games_b: int

@app.post("/api/mexicano/resultado")
async def mex_resultado(req: MexResultadoReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute(
            "UPDATE mexicano_partidos SET games_a=?, games_b=? WHERE id=?",
            (req.games_a, req.games_b, req.id)
        )
    state = get_mexicano_state()
    await manager.broadcast(state)
    return {"ok": True}

class MexSiguienteReq(BaseModel):
    password: str

@app.post("/api/mexicano/siguiente")
async def mex_siguiente(req: MexSiguienteReq):
    """Avanza a la siguiente ronda si la actual está completa."""
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    ronda_actual = int(mex_cfg_get("ronda_actual"))
    rondas_total = int(mex_cfg_get("rondas"))
    if not mex_ronda_completa(ronda_actual):
        raise HTTPException(status_code=400, detail="Faltan resultados en la ronda actual")
    if ronda_actual >= rondas_total:
        mex_cfg_set("estado", "finalizado")
        state = get_mexicano_state()
        await manager.broadcast(state)
        return {"ok": True, "finalizado": True}
    nueva_ronda = ronda_actual + 1
    mex_cfg_set("ronda_actual", str(nueva_ronda))
    with get_db() as con:
        jugadores = [r["nombre"] for r in
                     con.execute("SELECT nombre FROM jugadores ORDER BY grupo, orden").fetchall()]
    stats = mex_get_stats()
    mex_armar_ronda(jugadores, nueva_ronda, int(mex_cfg_get("canchas")), stats)
    state = get_mexicano_state()
    await manager.broadcast(state)
    return {"ok": True, "ronda": nueva_ronda}

class MexResetReq(BaseModel):
    password: str

@app.post("/api/mexicano/reset")
async def mex_reset(req: MexResetReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM mexicano_partidos")
    mex_cfg_set("ronda_actual", "0")
    mex_cfg_set("estado", "idle")
    state = get_mexicano_state()
    await manager.broadcast(state)
    return {"ok": True}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_text(json.dumps(get_full_state()))
        while True:
            await ws.receive_text()   # keep-alive (ping)
    except WebSocketDisconnect:
        manager.disconnect(ws)

# ── Arranque ──────────────────────────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)