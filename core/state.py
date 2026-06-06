"""
Construye el estado completo del torneo para sincronizar todos los clientes.
"""
from .db      import get_db, cfg_get
from .fixture import gen_fixture, calcular_rondas_sugeridas, calcular_stats, clasificar


def get_full_state() -> dict:
    with get_db() as con:
        config = {
            r["key"]: r["value"]
            for r in con.execute("SELECT key, value FROM config").fetchall()
        }
        jugadores = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM jugadores ORDER BY grupo, orden"
            ).fetchall()
        ]
        resultados = {
            r["id"]: {"ga": r["games_a"], "gb": r["games_b"], "fase": r["fase"]}
            for r in con.execute("SELECT * FROM resultados").fetchall()
        }

    n_canchas   = int(config.get("canchas",       3))
    rondas_prel = int(config.get("rondas_prel",   7))
    rondas_fin  = int(config.get("rondas_final",  5))

    # Agrupar jugadores por su campo "grupo"
    grupos: dict = {}
    for j in jugadores:
        g = j["grupo"]
        grupos.setdefault(g, []).append(j["nombre"])
    grupos_list = [grupos[k] for k in sorted(grupos.keys())]

    # Fixtures
    fixtures_prel  = [gen_fixture(g, rondas_prel) for g in grupos_list]
    fixtures_final = {}
    if grupos_list:
        stats = calcular_stats(grupos_list, fixtures_prel, resultados)
        for copa, jug in clasificar(grupos_list, stats).items():
            fixtures_final[copa] = gen_fixture(jug, rondas_fin)

    # Sugerencia de rondas
    n_jug     = len(jugadores)
    sugerencia = calcular_rondas_sugeridas(
        int(config.get("tiempo_cancha",  90)),
        int(config.get("games_partido",  16)),
        n_jugadores = n_jug if n_jug > 0 else 18,
        n_canchas   = n_canchas,
    )

    return {
        "type":          "state",
        "config":        config,
        "jugadores":     jugadores,
        "grupos":        grupos_list,
        "fixtures_prel": [[list(p) for p in f] for f in fixtures_prel],
        "fixtures_final": {k: [list(p) for p in v] for k, v in fixtures_final.items()},
        "resultados":    resultados,
        "sugerencia":    sugerencia,
    }
