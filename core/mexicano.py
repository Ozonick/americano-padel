"""
Lógica completa del modo Mexicano:
  - Armar rondas (random o por ranking)
  - Calcular stats acumuladas
  - Verificar ronda completa
  - Construir el estado completo para el frontend
"""
import random as rnd
from .db import get_db, mex_cfg_get, mex_cfg_set


# ── Consultas ─────────────────────────────────────────────────────────────────

def get_partidos(ronda: int | None = None) -> list:
    with get_db() as con:
        if ronda is not None:
            rows = con.execute(
                "SELECT * FROM mexicano_partidos WHERE ronda=? ORDER BY cancha",
                (ronda,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM mexicano_partidos ORDER BY ronda, cancha"
            ).fetchall()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    """Stats acumuladas de todos los jugadores en el modo mexicano."""
    with get_db() as con:
        partidos = con.execute(
            "SELECT * FROM mexicano_partidos WHERE games_a IS NOT NULL"
        ).fetchall()

    stats: dict = {}
    for p in partidos:
        p = dict(p)
        ga, gb   = p["games_a"] or 0, p["games_b"] or 0
        pts_a    = 3 if ga > gb else 1 if ga == gb else 0
        pts_b    = 3 if gb > ga else 1 if ga == gb else 0

        for j in [p["j1"], p["j2"]]:
            if j not in stats:
                stats[j] = {"gf": 0, "gc": 0, "pts": 0, "pj": 0}
            stats[j]["gf"]  += ga
            stats[j]["gc"]  += gb
            stats[j]["pts"] += pts_a
            stats[j]["pj"]  += 1

        for j in [p["j3"], p["j4"]]:
            if j not in stats:
                stats[j] = {"gf": 0, "gc": 0, "pts": 0, "pj": 0}
            stats[j]["gf"]  += gb
            stats[j]["gc"]  += ga
            stats[j]["pts"] += pts_b
            stats[j]["pj"]  += 1

    return stats


def ronda_completa(ronda: int) -> bool:
    with get_db() as con:
        sin_resultado = con.execute(
            "SELECT COUNT(*) FROM mexicano_partidos "
            "WHERE ronda=? AND games_a IS NULL",
            (ronda,),
        ).fetchone()[0]
    return sin_resultado == 0


# ── Armado de ronda ───────────────────────────────────────────────────────────

def armar_ronda(
    jugadores: list,
    ronda:     int,
    canchas:   int,
    stats:     dict | None = None,
) -> list:
    """
    Arma los partidos de una ronda:
      - Ronda 1: orden aleatorio.
      - Siguientes: jugadores ordenados por pts desc (mexicano clásico).
    Respeta el límite de canchas: max canchas×4 jugadores por ronda,
    el resto descansa.
    """
    jug = [j for j in jugadores if j.strip()]

    if stats and ronda > 1:
        jug = sorted(
            jug,
            key=lambda j: (
                -stats.get(j, {}).get("pts", 0),
                -(stats.get(j, {}).get("gf", 0) - stats.get(j, {}).get("gc", 0)),
            ),
        )
    else:
        rnd.shuffle(jug)

    jugando  = jug[: canchas * 4]
    partidos = []

    for cancha in range(1, canchas + 1):
        i = (cancha - 1) * 4
        if i + 3 >= len(jugando):
            break
        pid = f"mex-{ronda}-{cancha}"
        partidos.append({
            "id":      pid,
            "ronda":   ronda,
            "cancha":  cancha,
            "j1":      jugando[i],
            "j2":      jugando[i + 1],
            "j3":      jugando[i + 2],
            "j4":      jugando[i + 3],
            "games_a": None,
            "games_b": None,
        })

    with get_db() as con:
        for p in partidos:
            con.execute(
                "INSERT OR REPLACE INTO mexicano_partidos "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    p["id"], p["ronda"], p["cancha"],
                    p["j1"], p["j2"], p["j3"], p["j4"],
                    p["games_a"], p["games_b"],
                ),
            )

    return partidos


# ── Estado completo ───────────────────────────────────────────────────────────

def get_state() -> dict:
    with get_db() as con:
        cfg = {
            r["key"]: r["value"]
            for r in con.execute("SELECT * FROM mexicano_config").fetchall()
        }
        jugadores = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM jugadores ORDER BY grupo, orden"
            ).fetchall()
        ]

    ronda_actual = int(cfg.get("ronda_actual", 0))
    rondas_total = int(cfg.get("rondas", 7))
    stats        = get_stats()
    nombres      = [j["nombre"] for j in jugadores]

    ranking = sorted(
        nombres,
        key=lambda j: (
            -stats.get(j, {}).get("pts", 0),
            -(stats.get(j, {}).get("gf", 0) - stats.get(j, {}).get("gc", 0)),
        ),
    )

    return {
        "type":             "mexicano_state",
        "config":           cfg,
        "jugadores":        jugadores,
        "ronda_actual":     ronda_actual,
        "rondas_total":     rondas_total,
        "partidos_actuales": get_partidos(ronda_actual) if ronda_actual > 0 else [],
        "historial":        get_partidos(),
        "stats":            stats,
        "ranking":          ranking,
        "ronda_completa":   ronda_completa(ronda_actual) if ronda_actual > 0 else False,
        "finalizado":       ronda_actual >= rondas_total and ronda_actual > 0,
    }
