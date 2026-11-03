"""
Lógica de fixture: generación de partidos, estadísticas y clasificación.
"""
from functools import lru_cache
from itertools import combinations
from math import comb, gcd, lcm

# Puntuación por partido (cada jugador de la pareja): ganar 2 · empatar 1 · perder 0
PTS_GANA   = 2
PTS_EMPATA = 1
PTS_PIERDE = 0

MAX_RONDAS     = 40   # lo que se puede elegir en Configuración
MAX_GRUPO_SUG  = 24   # /api/sugerencia es pública: no calcula secuencias más grandes


def pts_partido(propios: int, rivales: int) -> int:
    """Puntos que suma cada jugador según los games propios vs. los del rival."""
    if propios > rivales:
        return PTS_GANA
    if propios == rivales:
        return PTS_EMPATA
    return PTS_PIERDE


def rondas_parejas(n: int) -> int:
    """Cada cuántas rondas quedan todos con los mismos partidos (juegan 4 por ronda)."""
    return n // gcd(n, 4)


def _largo_secuencia(n: int) -> int:
    """Rondas hasta que todas las parejas jugaron juntas la misma cantidad de veces, con tope."""
    pares = n * (n - 1)
    vuelta = pares // 4 if pares % 4 == 0 else pares // 2
    if vuelta <= MAX_RONDAS:
        return vuelta
    paso = rondas_parejas(n)
    return max(paso, MAX_RONDAS // paso * paso)


def _cuartetos_parejos(jugados: tuple):
    """Los que pueden jugar sin que nadie le saque más de 1 partido a otro."""
    minimo = min(jugados)
    atrasados = [i for i, pj in enumerate(jugados) if pj == minimo]
    if len(atrasados) >= 4:
        return combinations(atrasados, 4)
    resto = [i for i, pj in enumerate(jugados) if pj != minimo]
    return (
        tuple(sorted(atrasados + list(extra)))
        for extra in combinations(resto, 4 - len(atrasados))
    )


@lru_cache(maxsize=None)
def _secuencia(n: int) -> tuple:
    """
    Orden de partidos de un grupo de n jugadores (por posición en el grupo).

    Depende solo de n, así cambiar la cantidad de rondas no mueve las ya jugadas.
    Prioridades, en este orden:
      1. Partidos parejos: nunca más de 1 de diferencia entre jugadores
      2. Compañeros lo más repartidos posible
      3. No repetir un partido idéntico ni el mismo compañero dos rondas seguidas
      4. Rivales lo más repartidos posible
      5. Evitar descansar dos rondas seguidas
    """
    paso  = rondas_parejas(n)
    ancho = max(1, 30000 // (comb(n, 4) * 3))
    vacia = [[0] * n for _ in range(n)]
    # Cada estado: costos (compañeros, repetidos, rivales, descansos), jugados, matrices, descansaron, partidos
    haz = [(0, 0, 0, 0, (0,) * n, vacia, vacia, frozenset(), ())]

    for ronda in range(_largo_secuencia(n)):
        hijos = []
        for e, (c_comp, c_rep, c_riv, c_desc, jugados, comp, riv, descansaron, partidos) in enumerate(haz):
            ultimo = partidos[-1] if partidos else (-1, -1, -1, -1)
            parejas_ultimo = (ultimo[:2], ultimo[2:])
            for cuarteto in _cuartetos_parejos(jugados):
                a, b, c, d = cuarteto
                seguidos = sum(1 for j in descansaron if j not in cuarteto)
                for p, q, r, s in ((a, b, c, d), (a, c, b, d), (a, d, b, c)):
                    repetidos = ((p, q) in parejas_ultimo) + ((r, s) in parejas_ultimo)
                    if comp[p][q] and comp[r][s] and (p, q, r, s) in partidos:
                        repetidos += 1
                    hijos.append((
                        c_comp + 2 * (comp[p][q] + comp[r][s]) + 2,
                        c_rep + repetidos,
                        c_riv + 2 * (riv[p][r] + riv[p][s] + riv[q][r] + riv[q][s]) + 4,
                        c_desc + seguidos,
                        e,
                        (p, q, r, s),
                    ))
        hijos.sort(key=lambda h: h[:4])

        # El torneo puede terminar en cualquier ronda: solo sigue el mejor reparto de
        # compañeros y, cuando quedan todos parejos, también lo mejor en lo demás.
        criterios = 3 if (ronda + 1) % paso == 0 else 1
        hijos = [h for h in hijos if h[:criterios] == hijos[0][:criterios]]

        nuevo, vistos = [], set()
        for c_comp, c_rep, c_riv, c_desc, e, partido in hijos:
            if len(nuevo) >= ancho:
                break
            _, _, _, _, jugados, comp, riv, _, partidos = haz[e]
            p, q, r, s = partido
            comp = [fila[:] for fila in comp]
            riv  = [fila[:] for fila in riv]
            comp[p][q] += 1; comp[q][p] += 1
            comp[r][s] += 1; comp[s][r] += 1
            for x in (p, q):
                for y in (r, s):
                    riv[x][y] += 1; riv[y][x] += 1
            jugados = tuple(pj + (i in partido) for i, pj in enumerate(jugados))

            clave = (jugados, tuple(map(tuple, comp)), tuple(map(tuple, riv)))
            if clave in vistos:
                continue
            vistos.add(clave)
            descansan = frozenset(i for i in range(n) if i not in partido)
            nuevo.append((c_comp, c_rep, c_riv, c_desc, jugados, comp, riv, descansan, partidos + (partido,)))
        haz = nuevo

    return haz[0][-1]


def gen_fixture(grupo: list, rondas: int) -> list:
    """
    Genera el fixture de un grupo: todas las combinaciones de compañeros y rivales
    que entren en esas rondas, con los partidos parejos entre jugadores.
    Si las rondas superan la vuelta completa, la secuencia vuelve a empezar.
    """
    n = len(grupo)
    if n < 4:
        return []

    secuencia = _secuencia(n)
    return [
        tuple(grupo[i] for i in secuencia[r % len(secuencia)])
        for r in range(rondas)
    ]


def gen_fixture_anterior(grupo: list, rondas: int) -> list:
    """
    Fixture de los torneos que ya tenían resultados antes del cambio de combinaciones
    (config fixture_algo = "1"). Los resultados se guardan por número de ronda, así
    que esos torneos tienen que seguir con los mismos partidos hasta el próximo reset.
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


def repartir_grupos(n_jugadores: int, n_canchas: int) -> list:
    """Tamaños de grupo lo más parejos posible, sin armar grupos de menos de 4."""
    n_grupos = max(1, min(n_canchas, n_jugadores // 4))
    base, extra = divmod(n_jugadores, n_grupos)
    return [base + 1 if i < extra else base for i in range(n_grupos)]


def _veces_companeros(n: int, rondas: int) -> tuple:
    """Mínimo y máximo de veces que una pareja jugó junta en esas rondas."""
    secuencia = _secuencia(n)
    veces = {par: 0 for par in combinations(range(n), 2)}
    for r in range(rondas):
        a, b, c, d = secuencia[r % len(secuencia)]
        veces[tuple(sorted((a, b)))] += 1
        veces[tuple(sorted((c, d)))] += 1
    return min(veces.values()), max(veces.values())


def opciones_rondas(tamanos: list, mins_x_ronda: int, mins_finales: int, tiempo_min: int) -> list:
    """
    Cantidades de rondas con las que cada grupo queda con los partidos parejos.
    Llega hasta la vuelta completa y siempre incluye la primera donde todos jugaron
    con todos ("todos": True); si hay muchas, muestra las 5 primeras y esa.
    """
    if not tamanos or max(tamanos) > MAX_GRUPO_SUG:
        return []

    paso = lcm(*(rondas_parejas(n) for n in tamanos))
    tope = max(_largo_secuencia(n) for n in tamanos)
    opciones, hay_todos = [], False
    for rondas in range(paso, MAX_RONDAS + 1, paso):
        veces = [_veces_companeros(n, rondas) for n in tamanos]
        comp_min = min(v[0] for v in veces)
        es_todos = comp_min >= 1 and not hay_todos
        hay_todos = hay_todos or es_todos
        if not es_todos and (len(opciones) >= 5 or rondas > tope):
            continue
        partidos = [rondas * 4 // n for n in tamanos]
        opciones.append({
            "rondas":       rondas,
            "partidos_min": min(partidos),
            "partidos_max": max(partidos),
            "comp_min":     comp_min,
            "comp_max":     max(v[1] for v in veces),
            "todos":        es_todos,
            "minutos":      rondas * mins_x_ronda,
            "entra":        rondas * mins_x_ronda + mins_finales <= tiempo_min,
        })
    return opciones


def calcular_rondas_sugeridas(
    tiempo_min:   int,
    games_partido: int,
    n_jugadores:  int = 18,
    n_canchas:    int = 3,
    tamanos:      list = None,
) -> dict:
    """
    Devuelve las rondas sugeridas: las que dejan a todos con los mismos partidos,
    lo más combinadas posible, dentro del tiempo disponible.
    `tamanos` son los grupos reales; sin ellos se reparte n_jugadores en n_canchas.
    """
    mxp  = round(games_partido * 1.5)   # minutos por partido
    mxr  = mxp + 3                       # minutos por ronda (+ rotación)
    mf   = mxr * 4                       # tiempo reservado para finales
    rxt  = max(3, (tiempo_min - mf) // mxr)

    tamanos = tamanos or repartir_grupos(n_jugadores, n_canchas)
    jugables = sorted({n for n in tamanos if n >= 4})
    opciones = opciones_rondas(jugables, mxr, mf, tiempo_min)

    # La más larga que entre en el tiempo, sin pasarse de "todos con todos"
    hasta_todos = []
    for op in opciones:
        hasta_todos.append(op)
        if op["todos"]:
            break
    entran = [op for op in hasta_todos if op["entra"]]
    if entran:
        rp = entran[-1]["rondas"]
    else:
        rp = opciones[0]["rondas"] if opciones else rxt

    return {
        "rondas_prel":          int(rp),
        "rondas_prel_x_tiempo": int(rxt),
        "rondas_final":         4,
        "mins_x_partido":       mxp,
        "mins_x_ronda":         mxr,
        "mins_finales":         mf,
        "tiempo_total_est":     int(rp * mxr + mf),
        "tamanos":              tamanos,
        "opciones":             opciones,
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

            p1 = pts_partido(ga, gb)
            p2 = pts_partido(gb, ga)
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
