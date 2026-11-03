"""
Pruebas del armado del fixture. Correr desde la raíz del repo:
    python3 -m unittest discover tests
"""
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.db as db
from core.fixture import (
    FIXTURE_ACTUAL, calcular_rondas_sugeridas, gen_fixture, gen_fixture_anterior,
    rondas_parejas, repartir_grupos, _largo_secuencia,
)

TAMANOS = range(4, 17)


def partidos(texto):
    return [tuple(p) for p in texto.split()]


SECUENCIAS_6 = {
    "2": partidos("abcd aebf cedf acbe bdef adcf afbc abde cdef"),
    "3": partidos("abcd acef bedf aebc bdcf afde bfce adbe acdf"),
}


def medir(n, rondas):
    jugadores = list(range(n))
    partidos, companeros, rivales = Counter(), Counter(), Counter()
    for a, b, c, d in gen_fixture(jugadores, rondas):
        partidos.update((a, b, c, d))
        companeros.update((frozenset((a, b)), frozenset((c, d))))
        rivales.update(frozenset((x, y)) for x in (a, b) for y in (c, d))
    pares = [frozenset(p) for p in combinations(jugadores, 2)]
    return (
        [partidos[j] for j in jugadores],
        [companeros[p] for p in pares],
        [rivales[p] for p in pares],
    )


def rondas_balanceadas(n):
    return range(rondas_parejas(n), _largo_secuencia(n) + 1, rondas_parejas(n))


class Partidos(unittest.TestCase):
    def test_todos_juegan_lo_mismo_en_las_rondas_parejas(self):
        for n in TAMANOS:
            for r in rondas_balanceadas(n):
                pj, _, _ = medir(n, r)
                self.assertEqual(min(pj), max(pj), f"{n} jugadores, {r} rondas: {pj}")

    def test_nunca_mas_de_un_partido_de_diferencia(self):
        for n in TAMANOS:
            for r in range(1, _largo_secuencia(n) + 3):
                pj, _, _ = medir(n, r)
                self.assertLessEqual(max(pj) - min(pj), 1, f"{n} jugadores, {r} rondas: {pj}")


class Combinaciones(unittest.TestCase):
    def test_companeros_repartidos(self):
        for n in TAMANOS:
            for r in rondas_balanceadas(n):
                _, comp, _ = medir(n, r)
                self.assertLessEqual(max(comp) - min(comp), 1, f"{n} jugadores, {r} rondas")

    def test_companeros_repartidos_en_cualquier_ronda(self):
        # Hasta donde todos pueden seguir sin repetir, aunque no queden parejos en partidos
        for n in (6, 7, 8):
            for r in range(1, n * (n - 1) // 4 + 1):
                _, comp, _ = medir(n, r)
                self.assertEqual(max(comp), 1, f"{n} jugadores, {r} rondas")

    def test_sin_partido_identico_ni_companero_seguido(self):
        for n in TAMANOS:
            fx = gen_fixture(list(range(n)), _largo_secuencia(n))
            self.assertEqual(len(set(fx)), len(fx), f"{n} jugadores")
            for x, y in zip(fx, fx[1:]):
                self.assertFalse({x[:2], x[2:]} & {y[:2], y[2:]}, f"{n} jugadores: {x} y {y}")

    def test_seis_jugadores(self):
        # rondas: (compañeros min-max, rivales min-max, juntos en cancha min-max)
        esperado = {
            3:  ((0, 1), (0, 2), (1, 2)),
            6:  ((0, 1), (1, 2), (2, 3)),
            9:  ((1, 2), (2, 3), (3, 4)),
            12: ((1, 2), (3, 4), (4, 6)),
        }
        for r, (rango_comp, rango_riv, rango_juntos) in esperado.items():
            _, comp, riv = medir(6, r)
            juntos = [c + v for c, v in zip(comp, riv)]
            self.assertEqual((min(comp), max(comp)), rango_comp, f"compañeros en {r} rondas")
            self.assertEqual((min(riv), max(riv)), rango_riv, f"rivales en {r} rondas")
            self.assertEqual((min(juntos), max(juntos)), rango_juntos, f"juntos en {r} rondas")

    def test_el_companero_repetido_no_es_de_los_rivales_de_tres_veces(self):
        # El caso real: Guillermo y chevi coincidían en 5 de los 6 partidos de Guillermo
        _, comp, riv = medir(6, 9)
        for c, v in zip(comp, riv):
            self.assertLessEqual(c + v, 4)

    def test_seis_jugadores_no_descansan_dos_rondas_seguidas(self):
        fx = gen_fixture(list(range(6)), 9)
        for x, y in zip(fx, fx[1:]):
            self.assertEqual(set(x) | set(y), set(range(6)), f"{x} y {y}")

    def test_vuelta_completa_todas_las_parejas_por_igual(self):
        for n, veces in [(4, 1), (5, 1), (6, 2), (7, 2), (8, 1), (9, 1)]:
            _, comp, _ = medir(n, _largo_secuencia(n))
            self.assertEqual(set(comp), {veces}, f"{n} jugadores")


class Estabilidad(unittest.TestCase):
    def test_cambiar_las_rondas_no_mueve_las_jugadas(self):
        for n in TAMANOS:
            grupo = [f"J{i}" for i in range(n)]
            self.assertEqual(gen_fixture(grupo, 12)[:6], gen_fixture(grupo, 6))

    def test_mas_rondas_que_la_vuelta_completa(self):
        grupo = list("abcde")
        self.assertEqual(gen_fixture(grupo, 7)[5:], gen_fixture(grupo, 2))
        self.assertEqual(gen_fixture(list("abc"), 5), [])

    def test_la_secuencia_no_cambia_sin_querer(self):
        # Si esto falla cambió el fixture: los resultados de un torneo en curso
        # quedarían en otros partidos. Un cambio a propósito necesita otro fixture_algo.
        for version, esperada in SECUENCIAS_6.items():
            self.assertEqual(gen_fixture(list("abcdef"), 9, version), esperada, f"versión {version}")
        self.assertEqual(gen_fixture(list("abcdef"), 9), SECUENCIAS_6[FIXTURE_ACTUAL])

    def test_version_1_es_el_fixture_anterior(self):
        grupo = list("abcdef")
        self.assertEqual(gen_fixture(grupo, 7, "1"), gen_fixture_anterior(grupo, 7))


class Sugerencia(unittest.TestCase):
    def test_opciones_seis_jugadores(self):
        s = calcular_rondas_sugeridas(600, 8, 18, 3, [6, 6, 6])
        self.assertEqual([op["rondas"] for op in s["opciones"]], [3, 6, 9, 12, 15])
        self.assertEqual([op["partidos_max"] for op in s["opciones"]], [2, 4, 6, 8, 10])
        self.assertEqual([op["rondas"] for op in s["opciones"] if op["todos"]], [9])
        self.assertEqual(s["rondas_prel"], 9)

    def test_sugerida_respeta_el_tiempo(self):
        # 8 games: 15 min por ronda, 60 de finales. 6 rondas = 150 min, 9 rondas = 195 min
        self.assertEqual(calcular_rondas_sugeridas(180, 8, 18, 3)["rondas_prel"], 6)
        # Si no entra ninguna sugiere la más corta
        self.assertEqual(calcular_rondas_sugeridas(90, 16, 18, 3)["rondas_prel"], 3)

    def test_todos_con_todos_llega_aunque_haya_muchas_opciones(self):
        rondas = [op["rondas"] for op in calcular_rondas_sugeridas(90, 8, 8, 1)["opciones"]]
        self.assertEqual(rondas, [2, 4, 6, 8, 10, 14])

    def test_grupos_de_distinto_tamano(self):
        s = calcular_rondas_sugeridas(600, 8, 17, 3, [6, 6, 5])
        self.assertEqual([op["rondas"] for op in s["opciones"]], [15])
        self.assertEqual((s["opciones"][0]["partidos_min"], s["opciones"][0]["partidos_max"]), (10, 12))

    def test_sin_combinacion_posible(self):
        self.assertEqual(calcular_rondas_sugeridas(90, 8, 18, 3, [5, 6, 7])["opciones"], [])

    def test_grupo_enorme_no_calcula(self):
        self.assertEqual(calcular_rondas_sugeridas(90, 8, 100000, 1)["opciones"], [])


class Grupos(unittest.TestCase):
    def test_repartir(self):
        casos = {
            (18, 3): [6, 6, 6], (19, 3): [7, 6, 6], (17, 3): [6, 6, 5], (16, 3): [6, 5, 5],
            (10, 3): [5, 5], (3, 3): [3], (12, 0): [12],
        }
        for (jugadores, canchas), tamanos in casos.items():
            self.assertEqual(repartir_grupos(jugadores, canchas), tamanos)


class TorneoEnCurso(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.dir.name) / "prueba.db"

    def tearDown(self):
        db.DB_PATH = self.original
        self.dir.cleanup()

    def algo(self):
        with sqlite3.connect(db.DB_PATH) as con:
            return con.execute("SELECT value FROM config WHERE key='fixture_algo'").fetchone()[0]

    def preparar(self, version, con_resultados):
        db.init_db()
        with sqlite3.connect(db.DB_PATH) as con:
            if version is None:
                con.execute("DELETE FROM config WHERE key='fixture_algo'")
            else:
                con.execute("UPDATE config SET value=? WHERE key='fixture_algo'", (version,))
            if con_resultados:
                con.execute("INSERT INTO resultados VALUES ('prel-0-0', 9, 7, 'prel')")

    def test_base_nueva_usa_el_fixture_actual(self):
        db.init_db()
        self.assertEqual(self.algo(), FIXTURE_ACTUAL)

    def test_resultados_de_antes_de_las_versiones_quedan_en_la_1(self):
        self.preparar(None, True)
        db.init_db()
        self.assertEqual(self.algo(), "1")

    def test_torneo_con_resultados_conserva_su_version(self):
        for version in ("1", "2"):
            with self.subTest(version=version):
                db.DB_PATH.unlink(missing_ok=True)
                self.preparar(version, True)
                db.init_db()
                # Reiniciar el servidor tampoco lo cambia
                db.init_db()
                self.assertEqual(self.algo(), version)

    def test_sin_resultados_pasa_a_la_version_actual(self):
        for version in (None, "1", "2"):
            with self.subTest(version=version):
                db.DB_PATH.unlink(missing_ok=True)
                self.preparar(version, False)
                db.init_db()
                self.assertEqual(self.algo(), FIXTURE_ACTUAL)

    def test_resultados_de_otros_modos_no_cuentan(self):
        self.preparar("2", False)
        with sqlite3.connect(db.DB_PATH) as con:
            con.execute("INSERT INTO resultados VALUES ('final-oro-0', 1, 0, 'final')")
        db.init_db()
        self.assertEqual(self.algo(), FIXTURE_ACTUAL)


if __name__ == "__main__":
    unittest.main()
