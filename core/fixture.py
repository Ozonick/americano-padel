"""
Lógica de fixture: generación de partidos, estadísticas y clasificación.
"""
from itertools import combinations


def gen_fixture(grupo: list, rondas: int) -> list:
    """
    Genera el fixture para un grupo balanceando dos criterios:
      1. Minimizar repetición de compañeros (peso 100×)
      2. Que descansen los que más partidos jugaron (balance de participación)

    Con 6 jugadores y 7 rondas: diferencia máxima de 1 partido entre jugadores.
    Cuando se agotan las combinaciones únicas, repite las menos usadas.
    """
    n = len(grupo)
    if n < 4:
        return []

    idx = list(range(n))
    companeros:       dict = {}
    partidos_jugados: dict = {i: 0 for i in idx}
    resultado:        list = []

    for _ in range(rondas):
        candidatos = []
        for combo in combinations(idx, 4):
            a, b, c, d = combo
            for p1, p2 in [((a, b), (c, d)), ((a, c), (b, d)), ((a, d), (b, c))]:
                k1 = tuple(sorted(p1))
                k2 = tuple(sorted(p2))
                rep   = (companeros.get(k1, 0) + companeros.get(k2, 0)) * 100
                jc    = list(combo)
                bal   = max(partidos_jugados[j] for j in jc) * 10
                desc  = sum(partidos_jugados[i] for i in idx if i not in jc) * -5
                candidatos.append((rep + bal + desc, k1, k2, jc))

        if not candidatos:
            break

        candidatos.sort(key=lambda x: x[0])
        _, p1, p2, jc = candidatos[0]

        resultado.append((
            grupo[p1[0]], grupo[p1[1]],
            grupo[p2[0]], grupo[p2[1]],
        ))
        companeros[p1] = companeros.get(p1, 0) + 1
        companeros[p2] = companeros.get(p2, 0) + 1
        for j in jc:
            partidos_jugados[j] += 1

    return resultado


def calcular_rondas_sugeridas(
    tiempo_min:   int,
    games_partido: int,
    n_jugadores:  int = 18,
    n_canchas:    int = 3,
) -> dict:
    """
    Devuelve la cantidad de rondas sugeridas según tiempo disponible
    y el máximo sin repetir compañero.
    """
    mxp  = round(games_partido * 1.5)   # minutos por partido
    mxr  = mxp + 3                       # minutos por ronda (+ rotación)
    mf   = mxr * 4                       # tiempo reservado para finales
    rxt  = max(3, (tiempo_min - mf) // mxr)
    nxg  = max(4, round(n_jugadores / n_canchas))
    rmax = nxg - 1
    rp   = min(rxt, rmax)

    return {
        "rondas_prel":            int(rp),
        "rondas_prel_x_tiempo":   int(rxt),
        "rondas_max_sin_repetir": int(rmax),
        "rondas_final":           4,
        "mins_x_partido":         mxp,
        "mins_x_ronda":           mxr,
        "tiempo_total_est":       int(rp * mxr + mf),
        "n_x_grupo":              nxg,
    }


def calcular_stats(
    grupos:       list,
    fixtures_prel: list,
    resultados:   dict,
) -> dict:
    """
    Calcula PJ, GF, GC y PTS para cada jugador a partir de los resultados cargados.
    """
    stats: dict = {}

    for gi, grupo in enumerate(grupos):
        for j in grupo:
            stats[j] = {"pj": 0, "gf": 0, "gc": 0, "pts": 0, "gi": gi}

        for ri, partido in enumerate(fixtures_prel[gi]):
            j1, j2, j3, j4 = partido
            key = f"prel-{gi}-{ri}"
            res = resultados.get(key)
            if not res or res["ga"] is None:
                continue

            ga, gb = int(res["ga"]), int(res["gb"])
            for j in [j1, j2]:
                if j in stats:
                    stats[j]["gf"] += ga
                    stats[j]["gc"] += gb
                    stats[j]["pj"] += 1
            for j in [j3, j4]:
                if j in stats:
                    stats[j]["gf"] += gb
                    stats[j]["gc"] += ga
                    stats[j]["pj"] += 1

            p1 = 3 if ga > gb else 1 if ga == gb else 0
            p2 = 3 if gb > ga else 1 if ga == gb else 0
            for j in [j1, j2]:
                if j in stats:
                    stats[j]["pts"] += p1
            for j in [j3, j4]:
                if j in stats:
                    stats[j]["pts"] += p2

    return stats


def clasificar(grupos: list, stats: dict) -> dict:
    """
    Ordena cada grupo por pts/dif y arma los clasificados por copa:
      oro   → 1° y 2° de cada grupo
      plata → 3° y 4°
      bronce → 5° y 6°
    """
    def sort_key(j):
        s = stats.get(j, {})
        return (
            -s.get("pts", 0),
            -(s.get("gf", 0) - s.get("gc", 0)),
            -s.get("gf", 0),
        )

    grupos_sorted = [sorted(g, key=sort_key) for g in grupos]

    copas: dict = {"oro": [], "plata": [], "bronce": []}
    for slc, copa in [
        (slice(0, 2), "oro"),
        (slice(2, 4), "plata"),
        (slice(4, 6), "bronce"),
    ]:
        for gs in grupos_sorted:
            copas[copa].extend(gs[slc])

    return copas
