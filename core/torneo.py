"""
Lógica del Torneo de Parejas:
  - 16 parejas fijas, 4 zonas de 4 (A, B, C, D)
  - Fase de zonas: round robin, a 1 set
  - Clasifican las 2 primeras de cada zona
  - Playoffs: cuartos -> semis -> final (cruces 1A-2B, 1C-2D, 1B-2A, 1D-2C)
El estado completo se guarda como JSON en la tabla config (key 'torneo_json').
"""
import json
import random
from itertools import combinations
from .db import get_db

KEY        = "torneo_json"
N_PAREJAS  = 16
N_ZONAS    = 4
X_ZONA     = 4
LETRAS     = "ABCD"


# ── Persistencia ──────────────────────────────────────────────────────────────

def _default() -> dict:
    return {
        "estado":     "config",   # config | zonas | playoffs | finalizado
        "parejas":    [{"j1": "", "j2": ""} for _ in range(N_PAREJAS)],
        "resultados": {},          # id -> {"ga": int, "gb": int}
    }


def _load() -> dict:
    with get_db() as con:
        row = con.execute("SELECT value FROM config WHERE key=?", (KEY,)).fetchone()
    if row:
        try:
            return json.loads(row["value"])
        except Exception:
            pass
    return _default()


def _save(t: dict):
    with get_db() as con:
        con.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (KEY, json.dumps(t)))


# ── Mutaciones ────────────────────────────────────────────────────────────────

def set_parejas(parejas: list, sortear: bool = False):
    """Guarda las 16 parejas. Si sortear=True las mezcla antes de asignar zonas."""
    t = _load()
    limpio = [
        {"j1": str(p.get("j1", "")).strip(), "j2": str(p.get("j2", "")).strip()}
        for p in parejas[:N_PAREJAS]
    ]
    while len(limpio) < N_PAREJAS:
        limpio.append({"j1": "", "j2": ""})
    if sortear:
        random.shuffle(limpio)
    t["parejas"] = limpio
    _save(t)


def iniciar():
    """Pasa a fase de zonas. Requiere las 16 parejas completas."""
    t = _load()
    if any(not p["j1"] or not p["j2"] for p in t["parejas"]):
        raise ValueError("Faltan completar nombres de parejas")
    t["estado"] = "zonas"
    _save(t)


def guardar_resultado(pid: str, ga: int, gb: int):
    """Guarda el resultado de un set. No se permiten empates."""
    if ga == gb:
        raise ValueError("Un set no puede terminar empatado")
    t = _load()
    t["resultados"][pid] = {"ga": int(ga), "gb": int(gb)}
    if pid == "po-f-0":
        t["estado"] = "finalizado"
    _save(t)


def generar_playoffs():
    """Cierra la fase de zonas y arma el bracket. Requiere todas las zonas completas."""
    t = _load()
    state = get_state()
    if not state["zonas_completas"]:
        raise ValueError("Faltan resultados en la fase de zonas")
    t["estado"] = "playoffs"
    _save(t)


def reset():
    _save(_default())


# ── Estado completo ───────────────────────────────────────────────────────────

def _match(res: dict, pid: str, a, b) -> dict:
    r = res.get(pid)
    return {
        "id": pid, "a": a, "b": b,
        "ga": r["ga"] if r else None,
        "gb": r["gb"] if r else None,
    }


def _ganador(m: dict):
    if m["a"] is None or m["b"] is None or m["ga"] is None:
        return None
    return m["a"] if m["ga"] > m["gb"] else m["b"]


def get_state() -> dict:
    t       = _load()
    parejas = t["parejas"]
    res     = t["resultados"]

    # ── Zonas: partidos + tabla ──
    zonas     = []
    completas = True
    for zi in range(N_ZONAS):
        base = zi * X_ZONA
        idxs = list(range(base, base + X_ZONA))

        partidos = []
        stats = {i: {"pg": 0, "pp": 0, "gf": 0, "gc": 0, "pj": 0} for i in idxs}
        for a, b in combinations(idxs, 2):
            pid = f"z{zi}-{a}-{b}"
            m   = _match(res, pid, a, b)
            partidos.append(m)
            if m["ga"] is None:
                completas = False
            else:
                ga, gb = m["ga"], m["gb"]
                stats[a]["gf"] += ga; stats[a]["gc"] += gb; stats[a]["pj"] += 1
                stats[b]["gf"] += gb; stats[b]["gc"] += ga; stats[b]["pj"] += 1
                if ga > gb:
                    stats[a]["pg"] += 1; stats[b]["pp"] += 1
                else:
                    stats[b]["pg"] += 1; stats[a]["pp"] += 1

        tabla = sorted(
            idxs,
            key=lambda i: (
                -stats[i]["pg"],
                -(stats[i]["gf"] - stats[i]["gc"]),
                -stats[i]["gf"],
            ),
        )
        zonas.append({
            "zona":     zi,
            "letra":    LETRAS[zi],
            "partidos": partidos,
            "tabla":    [{"idx": i, **stats[i]} for i in tabla],
        })

    # ── Playoffs (solo si la fase de zonas cerró) ──
    playoffs = None
    campeon  = None
    if t["estado"] in ("playoffs", "finalizado"):
        # clasificados: [1A, 2A, 1B, 2B, 1C, 2C, 1D, 2D]
        cls = []
        for z in zonas:
            cls.append(z["tabla"][0]["idx"])
            cls.append(z["tabla"][1]["idx"])
        a1, a2, b1, b2, c1, c2, d1, d2 = cls

        cuartos_def = [(a1, b2), (c1, d2), (b1, a2), (d1, c2)]
        cuartos = [_match(res, f"po-c-{i}", a, b) for i, (a, b) in enumerate(cuartos_def)]
        semis = [
            _match(res, "po-s-0", _ganador(cuartos[0]), _ganador(cuartos[1])),
            _match(res, "po-s-1", _ganador(cuartos[2]), _ganador(cuartos[3])),
        ]
        final   = [_match(res, "po-f-0", _ganador(semis[0]), _ganador(semis[1]))]
        campeon = _ganador(final[0])

        playoffs = {"cuartos": cuartos, "semis": semis, "final": final}

    return {
        "type":            "torneo_state",
        "estado":          t["estado"],
        "parejas":         parejas,
        "zonas":           zonas,
        "zonas_completas": completas,
        "playoffs":        playoffs,
        "campeon":         campeon,
    }
