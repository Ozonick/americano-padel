"""
Super Americano Pádel — Servidor
=================================
FastAPI + SQLite + WebSockets.
Este archivo solo contiene rutas y el WebSocket.
Toda la lógica de negocio vive en core/.
"""
import asyncio
import json
import os
import random
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.db      import init_db, get_db, cfg_get, cfg_set, mex_cfg_get, mex_cfg_set
from core.state   import get_full_state
from core.fixture import calcular_rondas_sugeridas
import core.mexicano as mexicano

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "padel2024")
STATIC_DIR     = Path("static")

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Super Americano Pádel")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, data: dict):
        msg  = json.dumps(data)
        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self.active -= dead


manager = ConnectionManager()


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class AuthReq(BaseModel):
    password: str

class ConfigReq(BaseModel):
    password: str
    config:   dict

class JugadoresReq(BaseModel):
    password:  str
    jugadores: list

class ResultadoReq(BaseModel):
    password: str
    id:       str
    games_a:  int
    games_b:  int
    fase:     str = "prel"

class ResetReq(BaseModel):
    password: str

class ShuffleReq(BaseModel):
    password: str
    nombres:  list

class MexConfigReq(BaseModel):
    password: str
    canchas:  int = 3
    rondas:   int = 7
    games:    int = 16

class MexIniciarReq(BaseModel):
    password: str

class MexResultadoReq(BaseModel):
    password: str
    id:       str
    games_a:  int
    games_b:  int

class MexSiguienteReq(BaseModel):
    password: str

class MexResetReq(BaseModel):
    password: str


# ── Rutas generales ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/ping")
async def ping():
    return {"ok": True, "ts": __import__("time").time()}


@app.get("/api/state")
async def get_state():
    return JSONResponse(get_full_state())


@app.post("/api/auth")
async def auth(req: AuthReq):
    if req.password == ADMIN_PASSWORD:
        return {"ok": True, "role": "admin"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")


@app.post("/api/config")
async def save_config(req: ConfigReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    campos_validos = {
        "canchas", "rondas_prel", "rondas_final",
        "games_partido", "tiempo_cancha", "torneo_nombre", "estado",
    }
    for k, v in req.config.items():
        if k in campos_validos:
            cfg_set(k, str(v))
    await manager.broadcast(get_full_state())
    return {"ok": True}


@app.post("/api/jugadores")
async def save_jugadores(req: JugadoresReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM jugadores")
        for j in req.jugadores:
            con.execute(
                "INSERT INTO jugadores (nombre, grupo, orden) VALUES (?,?,?)",
                (j["nombre"], j.get("grupo", 0), j.get("orden", 0)),
            )
    await manager.broadcast(get_full_state())
    return {"ok": True}


@app.post("/api/resultado")
async def save_resultado(req: ResultadoReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute(
            "INSERT OR REPLACE INTO resultados VALUES (?,?,?,?)",
            (req.id, req.games_a, req.games_b, req.fase),
        )
    await manager.broadcast(get_full_state())
    return {"ok": True}


@app.post("/api/reset")
async def reset(req: ResetReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM resultados")
        con.execute("DELETE FROM jugadores")
        con.execute("UPDATE config SET value='config' WHERE key='estado'")
    await manager.broadcast(get_full_state())
    return {"ok": True}


@app.post("/api/shuffle")
async def shuffle(req: ShuffleReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    nombres = [n for n in req.nombres if n.strip()]
    random.shuffle(nombres)
    nc  = int(cfg_get("canchas") or 3)
    tam = max(4, round(len(nombres) / nc))
    jug = [
        {"nombre": n, "grupo": i // tam, "orden": i % tam}
        for i, n in enumerate(nombres)
    ]
    with get_db() as con:
        con.execute("DELETE FROM jugadores")
        for j in jug:
            con.execute(
                "INSERT INTO jugadores (nombre, grupo, orden) VALUES (?,?,?)",
                (j["nombre"], j["grupo"], j["orden"]),
            )
    await manager.broadcast(get_full_state())
    return {"ok": True, "jugadores": jug}


@app.get("/api/sugerencia")
async def sugerencia(
    tiempo:    int = 90,
    games:     int = 16,
    jugadores: int = 18,
    canchas:   int = 3,
):
    return calcular_rondas_sugeridas(tiempo, games, jugadores, canchas)


# ── Rutas Mexicano ────────────────────────────────────────────────────────────

@app.get("/api/mexicano/state")
async def get_mex_state():
    return JSONResponse(mexicano.get_state())


@app.post("/api/mexicano/config")
async def mex_config(req: MexConfigReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    mex_cfg_set("canchas", str(req.canchas))
    mex_cfg_set("rondas",  str(req.rondas))
    mex_cfg_set("games",   str(req.games))
    await manager.broadcast(mexicano.get_state())
    return {"ok": True}


@app.post("/api/mexicano/iniciar")
async def mex_iniciar(req: MexIniciarReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        jug = [
            r["nombre"]
            for r in con.execute(
                "SELECT nombre FROM jugadores ORDER BY grupo, orden"
            ).fetchall()
        ]
    if len(jug) < 4:
        raise HTTPException(status_code=400, detail="Se necesitan al menos 4 jugadores")
    with get_db() as con:
        con.execute("DELETE FROM mexicano_partidos")
    mex_cfg_set("ronda_actual", "1")
    mex_cfg_set("estado",       "jugando")
    mexicano.armar_ronda(jug, 1, int(mex_cfg_get("canchas")))
    await manager.broadcast(mexicano.get_state())
    return {"ok": True}


@app.post("/api/mexicano/resultado")
async def mex_resultado(req: MexResultadoReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute(
            "UPDATE mexicano_partidos SET games_a=?, games_b=? WHERE id=?",
            (req.games_a, req.games_b, req.id),
        )
    await manager.broadcast(mexicano.get_state())
    return {"ok": True}


@app.post("/api/mexicano/siguiente")
async def mex_siguiente(req: MexSiguienteReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    ra = int(mex_cfg_get("ronda_actual"))
    rt = int(mex_cfg_get("rondas"))
    if not mexicano.ronda_completa(ra):
        raise HTTPException(status_code=400, detail="Faltan resultados en la ronda actual")
    if ra >= rt:
        mex_cfg_set("estado", "finalizado")
        await manager.broadcast(mexicano.get_state())
        return {"ok": True, "finalizado": True}
    nr = ra + 1
    mex_cfg_set("ronda_actual", str(nr))
    with get_db() as con:
        jug = [
            r["nombre"]
            for r in con.execute(
                "SELECT nombre FROM jugadores ORDER BY grupo, orden"
            ).fetchall()
        ]
    mexicano.armar_ronda(jug, nr, int(mex_cfg_get("canchas")), mexicano.get_stats())
    await manager.broadcast(mexicano.get_state())
    return {"ok": True, "ronda": nr}


@app.post("/api/mexicano/reset")
async def mex_reset(req: MexResetReq):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM mexicano_partidos")
    mex_cfg_set("ronda_actual", "0")
    mex_cfg_set("estado",       "idle")
    await manager.broadcast(mexicano.get_state())
    return {"ok": True}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_text(json.dumps(get_full_state()))
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=20.0)
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                try:
                    await ws.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ── Arranque ──────────────────────────────────────────────────────────────────

init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
