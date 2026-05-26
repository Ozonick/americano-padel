"""
Super Americano Pádel — Backend
================================
FastAPI + SQLite + WebSockets
"""

import asyncio
import json
import os
import random
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "padel2024")
DB_PATH        = Path(os.environ.get("DB_PATH", "torneo.db"))
STATIC_DIR     = Path("static")

FIXTURE_6 = [(0,1,2,3),(1,3,2,4),(2,5,3,4),(3,4,5,0),(4,0,5,1),(5,3,0,1),(1,2,0,5)]

app = FastAPI(title="Super Americano Pádel")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS jugadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL, grupo INTEGER DEFAULT 0, orden INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS resultados (
                id TEXT PRIMARY KEY, games_a INTEGER, games_b INTEGER, fase TEXT DEFAULT 'prel'
            );
            CREATE TABLE IF NOT EXISTS mexicano_partidos (
                id TEXT PRIMARY KEY, ronda INTEGER, cancha INTEGER,
                j1 TEXT, j2 TEXT, j3 TEXT, j4 TEXT, games_a INTEGER, games_b INTEGER
            );
            CREATE TABLE IF NOT EXISTS mexicano_config (key TEXT PRIMARY KEY, value TEXT);
        """)
        for key, val in [("canchas","3"),("rondas_prel","7"),("rondas_final","5"),
                         ("games_partido","16"),("tiempo_cancha","90"),
                         ("estado","config"),("torneo_nombre","Super Americano")]:
            con.execute("INSERT OR IGNORE INTO config VALUES (?,?)", (key, val))
        for key, val in [("canchas","3"),("rondas","7"),("games","16"),
                         ("ronda_actual","0"),("estado","idle")]:
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

def cfg_get(key):
    with get_db() as con:
        r = con.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return r["value"] if r else ""

def cfg_set(key, value):
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (key, value))

def mex_cfg_get(key):
    with get_db() as con:
        r = con.execute("SELECT value FROM mexicano_config WHERE key=?", (key,)).fetchone()
        return r["value"] if r else ""

def mex_cfg_set(key, value):
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO mexicano_config VALUES (?,?)", (key, value))

def mex_get_partidos(ronda=None):
    with get_db() as con:
        if ronda is not None:
            rows = con.execute("SELECT * FROM mexicano_partidos WHERE ronda=? ORDER BY cancha",(ronda,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM mexicano_partidos ORDER BY ronda, cancha").fetchall()
        return [dict(r) for r in rows]

def mex_get_stats():
    with get_db() as con:
        partidos = con.execute("SELECT * FROM mexicano_partidos WHERE games_a IS NOT NULL").fetchall()
    stats = {}
    for p in partidos:
        p = dict(p)
        ga, gb = p["games_a"] or 0, p["games_b"] or 0
        pts_a = 3 if ga>gb else 1 if ga==gb else 0
        pts_b = 3 if gb>ga else 1 if ga==gb else 0
        for j in [p["j1"],p["j2"]]:
            if j not in stats: stats[j]={"gf":0,"gc":0,"pts":0,"pj":0}
            stats[j]["gf"]+=ga; stats[j]["gc"]+=gb; stats[j]["pts"]+=pts_a; stats[j]["pj"]+=1
        for j in [p["j3"],p["j4"]]:
            if j not in stats: stats[j]={"gf":0,"gc":0,"pts":0,"pj":0}
            stats[j]["gf"]+=gb; stats[j]["gc"]+=ga; stats[j]["pts"]+=pts_b; stats[j]["pj"]+=1
    return stats

def mex_armar_ronda(jugadores, ronda, canchas, stats=None):
    import random as rnd
    jug = [j for j in jugadores if j.strip()]
    if stats and ronda > 1:
        jug = sorted(jug, key=lambda j: (-(stats.get(j,{}).get("pts",0)),
                                          -(stats.get(j,{}).get("gf",0)-stats.get(j,{}).get("gc",0))))
    else:
        rnd.shuffle(jug)
    jugando = jug[:canchas*4]
    partidos = []
    for cancha in range(1, canchas+1):
        i = (cancha-1)*4
        if i+3 >= len(jugando): break
        pid = f"mex-{ronda}-{cancha}"
        partidos.append({"id":pid,"ronda":ronda,"cancha":cancha,
                         "j1":jugando[i],"j2":jugando[i+1],"j3":jugando[i+2],"j4":jugando[i+3],
                         "games_a":None,"games_b":None})
    with get_db() as con:
        for p in partidos:
            con.execute("INSERT OR REPLACE INTO mexicano_partidos VALUES (?,?,?,?,?,?,?,?,?)",
                       (p["id"],p["ronda"],p["cancha"],p["j1"],p["j2"],p["j3"],p["j4"],p["games_a"],p["games_b"]))
    return partidos

def mex_ronda_completa(ronda):
    with get_db() as con:
        return con.execute("SELECT COUNT(*) FROM mexicano_partidos WHERE ronda=? AND games_a IS NULL",(ronda,)).fetchone()[0] == 0

def get_mexicano_state():
    with get_db() as con:
        cfg = {r["key"]:r["value"] for r in con.execute("SELECT * FROM mexicano_config").fetchall()}
        jugadores = [dict(r) for r in con.execute("SELECT * FROM jugadores ORDER BY grupo,orden").fetchall()]
    ronda_actual = int(cfg.get("ronda_actual",0))
    rondas_total = int(cfg.get("rondas",7))
    stats = mex_get_stats()
    nombres = [j["nombre"] for j in jugadores]
    ranking = sorted(nombres, key=lambda j: (-(stats.get(j,{}).get("pts",0)),
                                              -(stats.get(j,{}).get("gf",0)-stats.get(j,{}).get("gc",0))))
    return {"type":"mexicano_state","config":cfg,"jugadores":jugadores,
            "ronda_actual":ronda_actual,"rondas_total":rondas_total,
            "partidos_actuales":mex_get_partidos(ronda_actual) if ronda_actual>0 else [],
            "historial":mex_get_partidos(),"stats":stats,"ranking":ranking,
            "ronda_completa":mex_ronda_completa(ronda_actual) if ronda_actual>0 else False,
            "finalizado":ronda_actual>=rondas_total and ronda_actual>0}

class ConnectionManager:
    def __init__(self): self.active: Set[WebSocket] = set()
    async def connect(self, ws):
        await ws.accept(); self.active.add(ws)
    def disconnect(self, ws): self.active.discard(ws)
    async def broadcast(self, data):
        msg = json.dumps(data); dead = set()
        for ws in self.active:
            try: await ws.send_text(msg)
            except: dead.add(ws)
        self.active -= dead

manager = ConnectionManager()

def gen_fixture(grupo, rondas):
    from itertools import combinations as _comb
    n = len(grupo)
    if n < 4: return []
    idx = list(range(n))
    companeros, partidos_jugados, resultado = {}, {i:0 for i in idx}, []
    for _ in range(rondas):
        candidatos = []
        for combo in _comb(idx, 4):
            a,b,c,d = combo
            for p1,p2 in [((a,b),(c,d)),((a,c),(b,d)),((a,d),(b,c))]:
                k1,k2 = tuple(sorted(p1)),tuple(sorted(p2))
                rep = (companeros.get(k1,0)+companeros.get(k2,0))*100
                jc = list(combo)
                bal = max(partidos_jugados[j] for j in jc)*10
                desc = sum(partidos_jugados[i] for i in idx if i not in jc)*-5
                candidatos.append((rep+bal+desc, k1, k2, jc))
        if not candidatos: break
        candidatos.sort(key=lambda x: x[0])
        _, p1, p2, jc = candidatos[0]
        resultado.append((grupo[p1[0]],grupo[p1[1]],grupo[p2[0]],grupo[p2[1]]))
        companeros[p1]=companeros.get(p1,0)+1; companeros[p2]=companeros.get(p2,0)+1
        for j in jc: partidos_jugados[j]+=1
    return resultado

def calcular_rondas_sugeridas(tiempo_min, games_partido, n_jugadores=18, n_canchas=3):
    mxp = round(games_partido*1.5); mxr = mxp+3; mf = mxr*4
    rxt = max(3,(tiempo_min-mf)//mxr); nxg = max(4,round(n_jugadores/n_canchas))
    rmax = nxg-1; rp = min(rxt,rmax)
    return {"rondas_prel":int(rp),"rondas_prel_x_tiempo":int(rxr := rxt),
            "rondas_max_sin_repetir":int(rmax),"rondas_final":4,
            "mins_x_partido":mxp,"mins_x_ronda":mxr,
            "tiempo_total_est":int(rp*mxr+mf),"n_x_grupo":nxg}

def get_full_state():
    with get_db() as con:
        config = {r["key"]:r["value"] for r in con.execute("SELECT key,value FROM config").fetchall()}
        jugadores = [dict(r) for r in con.execute("SELECT * FROM jugadores ORDER BY grupo,orden").fetchall()]
        resultados = {r["id"]:{"ga":r["games_a"],"gb":r["games_b"],"fase":r["fase"]}
                      for r in con.execute("SELECT * FROM resultados").fetchall()}
    n_canchas = int(config.get("canchas",3))
    rondas_prel = int(config.get("rondas_prel",7))
    rondas_fin = int(config.get("rondas_final",5))
    grupos = {}
    for j in jugadores:
        g = j["grupo"]
        if g not in grupos: grupos[g]=[]
        grupos[g].append(j["nombre"])
    grupos_list = [grupos[k] for k in sorted(grupos.keys())] if grupos else []
    fixtures_prel = [gen_fixture(g,rondas_prel) for g in grupos_list]
    fixtures_final = {}
    if grupos_list:
        stats = calcular_stats(grupos_list,fixtures_prel,resultados)
        for copa,jug in clasificar(grupos_list,stats).items():
            fixtures_final[copa] = gen_fixture(jug,rondas_fin)
    n_jug = len(jugadores)
    sug = calcular_rondas_sugeridas(int(config.get("tiempo_cancha",90)),
                                     int(config.get("games_partido",16)),
                                     n_jug if n_jug>0 else 18, n_canchas)
    return {"type":"state","config":config,"jugadores":jugadores,"grupos":grupos_list,
            "fixtures_prel":[[list(p) for p in f] for f in fixtures_prel],
            "fixtures_final":{k:[list(p) for p in v] for k,v in fixtures_final.items()},
            "resultados":resultados,"sugerencia":sug}

def calcular_stats(grupos, fixtures_prel, resultados, fase="prel"):
    stats = {}
    for gi,grupo in enumerate(grupos):
        for j in grupo: stats[j]={"pj":0,"gf":0,"gc":0,"pts":0,"gi":gi}
        for ri,partido in enumerate(fixtures_prel[gi]):
            j1,j2,j3,j4 = partido; key=f"prel-{gi}-{ri}"; res=resultados.get(key)
            if not res or res["ga"] is None: continue
            ga,gb = int(res["ga"]),int(res["gb"])
            for j in [j1,j2]:
                if j in stats: stats[j]["gf"]+=ga;stats[j]["gc"]+=gb;stats[j]["pj"]+=1
            for j in [j3,j4]:
                if j in stats: stats[j]["gf"]+=gb;stats[j]["gc"]+=ga;stats[j]["pj"]+=1
            p1=3 if ga>gb else 1 if ga==gb else 0; p2=3 if gb>ga else 1 if ga==gb else 0
            for j in [j1,j2]:
                if j in stats: stats[j]["pts"]+=p1
            for j in [j3,j4]:
                if j in stats: stats[j]["pts"]+=p2
    return stats

def clasificar(grupos, stats):
    sg = [sorted(g,key=lambda j:(-stats.get(j,{}).get("pts",0),
                                  -(stats.get(j,{}).get("gf",0)-stats.get(j,{}).get("gc",0)),
                                  -stats.get(j,{}).get("gf",0))) for g in grupos]
    copas = {"oro":[],"plata":[],"bronce":[]}
    for s,c in [(slice(0,2),"oro"),(slice(2,4),"plata"),(slice(4,6),"bronce")]:
        for g in sg: copas[c].extend(g[s])
    return copas

# ── Rutas ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root(): return FileResponse(STATIC_DIR/"index.html")

@app.get("/api/ping")
async def ping(): return {"ok":True,"ts":__import__("time").time()}

@app.get("/api/state")
async def get_state(): return JSONResponse(get_full_state())

class AuthReq(BaseModel): password: str
@app.post("/api/auth")
async def auth(req: AuthReq):
    if req.password==ADMIN_PASSWORD: return {"ok":True,"role":"admin"}
    raise HTTPException(status_code=401,detail="Contraseña incorrecta")

class ConfigReq(BaseModel): password:str; config:dict
@app.post("/api/config")
async def save_config(req: ConfigReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    for k,v in req.config.items():
        if k in ("canchas","rondas_prel","rondas_final","games_partido","tiempo_cancha","torneo_nombre","estado"):
            cfg_set(k,str(v))
    await manager.broadcast(get_full_state()); return {"ok":True}

class JugadoresReq(BaseModel): password:str; jugadores:list
@app.post("/api/jugadores")
async def save_jugadores(req: JugadoresReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM jugadores")
        for j in req.jugadores:
            con.execute("INSERT INTO jugadores (nombre,grupo,orden) VALUES (?,?,?)",
                       (j["nombre"],j.get("grupo",0),j.get("orden",0)))
    await manager.broadcast(get_full_state()); return {"ok":True}

class ResultadoReq(BaseModel): password:str; id:str; games_a:int; games_b:int; fase:str="prel"
@app.post("/api/resultado")
async def save_resultado(req: ResultadoReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO resultados VALUES (?,?,?,?)",(req.id,req.games_a,req.games_b,req.fase))
    await manager.broadcast(get_full_state()); return {"ok":True}

class ResetReq(BaseModel): password:str
@app.post("/api/reset")
async def reset(req: ResetReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("DELETE FROM resultados"); con.execute("DELETE FROM jugadores")
        con.execute("UPDATE config SET value='config' WHERE key='estado'")
    await manager.broadcast(get_full_state()); return {"ok":True}

class ShuffleReq(BaseModel): password:str; nombres:list
@app.post("/api/shuffle")
async def shuffle(req: ShuffleReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    nombres=[n for n in req.nombres if n.strip()]; random.shuffle(nombres)
    nc=int(cfg_get("canchas") or 3); tam=max(4,round(len(nombres)/nc))
    jug=[{"nombre":n,"grupo":i//tam,"orden":i%tam} for i,n in enumerate(nombres)]
    with get_db() as con:
        con.execute("DELETE FROM jugadores")
        for j in jug: con.execute("INSERT INTO jugadores (nombre,grupo,orden) VALUES (?,?,?)",(j["nombre"],j["grupo"],j["orden"]))
    await manager.broadcast(get_full_state()); return {"ok":True,"jugadores":jug}

@app.get("/api/sugerencia")
async def sugerencia(tiempo:int=90,games:int=16,jugadores:int=18,canchas:int=3):
    return calcular_rondas_sugeridas(tiempo,games,jugadores,canchas)

# Mexicano
class MexConfigReq(BaseModel): password:str; canchas:int=3; rondas:int=7; games:int=16
@app.post("/api/mexicano/config")
async def mex_config(req: MexConfigReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    mex_cfg_set("canchas",str(req.canchas)); mex_cfg_set("rondas",str(req.rondas)); mex_cfg_set("games",str(req.games))
    await manager.broadcast(get_mexicano_state()); return {"ok":True}

@app.get("/api/mexicano/state")
async def get_mex_state(): return JSONResponse(get_mexicano_state())

class MexIniciarReq(BaseModel): password:str
@app.post("/api/mexicano/iniciar")
async def mex_iniciar(req: MexIniciarReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as con:
        jug=[r["nombre"] for r in con.execute("SELECT nombre FROM jugadores ORDER BY grupo,orden").fetchall()]
    if len(jug)<4: raise HTTPException(status_code=400,detail="Se necesitan al menos 4 jugadores")
    with get_db() as con: con.execute("DELETE FROM mexicano_partidos")
    mex_cfg_set("ronda_actual","1"); mex_cfg_set("estado","jugando")
    mex_armar_ronda(jug,1,int(mex_cfg_get("canchas")))
    await manager.broadcast(get_mexicano_state()); return {"ok":True}

class MexResultadoReq(BaseModel): password:str; id:str; games_a:int; games_b:int
@app.post("/api/mexicano/resultado")
async def mex_resultado(req: MexResultadoReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as con:
        con.execute("UPDATE mexicano_partidos SET games_a=?,games_b=? WHERE id=?",(req.games_a,req.games_b,req.id))
    await manager.broadcast(get_mexicano_state()); return {"ok":True}

class MexSiguienteReq(BaseModel): password:str
@app.post("/api/mexicano/siguiente")
async def mex_siguiente(req: MexSiguienteReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    ra=int(mex_cfg_get("ronda_actual")); rt=int(mex_cfg_get("rondas"))
    if not mex_ronda_completa(ra): raise HTTPException(status_code=400,detail="Faltan resultados en la ronda actual")
    if ra>=rt:
        mex_cfg_set("estado","finalizado"); await manager.broadcast(get_mexicano_state()); return {"ok":True,"finalizado":True}
    nr=ra+1; mex_cfg_set("ronda_actual",str(nr))
    with get_db() as con:
        jug=[r["nombre"] for r in con.execute("SELECT nombre FROM jugadores ORDER BY grupo,orden").fetchall()]
    mex_armar_ronda(jug,nr,int(mex_cfg_get("canchas")),mex_get_stats())
    await manager.broadcast(get_mexicano_state()); return {"ok":True,"ronda":nr}

class MexResetReq(BaseModel): password:str
@app.post("/api/mexicano/reset")
async def mex_reset(req: MexResetReq):
    if req.password!=ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as con: con.execute("DELETE FROM mexicano_partidos")
    mex_cfg_set("ronda_actual","0"); mex_cfg_set("estado","idle")
    await manager.broadcast(get_mexicano_state()); return {"ok":True}

# ── WebSocket con keepalive activo ────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_text(json.dumps(get_full_state()))
        while True:
            try:
                # Timeout de 20s — si no llega nada mandamos ping para mantener vivo
                data = await asyncio.wait_for(ws.receive_text(), timeout=20.0)
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Mandar ping propio al cliente para mantener la conexión
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