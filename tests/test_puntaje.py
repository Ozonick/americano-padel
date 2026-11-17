"""
Pruebas de la puntuación americana. Correr desde la raíz del repo:
    python3 -m unittest discover tests
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.db as db
from core import mexicano
from core.fixture import calcular_stats, clasificar


def stats_de(partidos, resultados):
    """Un solo grupo con los jugadores que aparecen en los partidos."""
    grupo = sorted({j for p in partidos for j in p})
    res = {f"prel-0-{i}": {"ga": ga, "gb": gb} for i, (ga, gb) in enumerate(resultados)}
    return grupo, calcular_stats([grupo], [partidos], res)


class Americano(unittest.TestCase):
    def test_cada_jugador_suma_los_games_de_su_pareja(self):
        _, s = stats_de([("ana", "bea", "caro", "dani")], [(9, 7)])
        for j in ("ana", "bea"):
            self.assertEqual((s[j]["pts"], s[j]["pg"], s[j]["pj"]), (9, 1, 1))
        for j in ("caro", "dani"):
            self.assertEqual((s[j]["pts"], s[j]["pg"], s[j]["pj"]), (7, 0, 1))

    def test_se_acumula_partido_a_partido(self):
        partidos = [("a", "b", "c", "d"), ("a", "c", "b", "d"), ("a", "d", "b", "c")]
        _, s = stats_de(partidos, [(9, 7), (3, 13), (8, 8)])
        self.assertEqual(s["a"]["pts"], 9 + 3 + 8)
        self.assertEqual(s["d"]["pts"], 7 + 13 + 8)
        self.assertEqual(s["a"]["pg"], 1)
        self.assertEqual(s["d"]["pg"], 1)

    def test_partidos_sin_resultado_no_suman(self):
        partidos = [("a", "b", "c", "d"), ("a", "c", "b", "d")]
        _, s = stats_de(partidos, [(9, 7)])
        self.assertEqual({j: s[j]["pj"] for j in "abcd"}, {"a": 1, "b": 1, "c": 1, "d": 1})

    def test_perder_ajustado_suma_mas_que_ganar_justo(self):
        # Lo que pidió el usuario: ya no importa solo ganar, cuenta cada game
        partidos = [("a", "b", "c", "d"), ("a", "c", "b", "d")]
        grupo, s = stats_de(partidos, [(16, 0), (7, 9)])
        # a: 16+7=23 · b: 16+9=25 · c: 0+7=7 · d: 0+9=9
        self.assertEqual(clasificar([grupo], s)["oro"], ["b", "a"])

    def test_desempate_por_partidos_ganados_y_despues_diferencia(self):
        stats = {
            "a": {"pts": 20, "pg": 1, "gf": 20, "gc": 12},
            "b": {"pts": 20, "pg": 2, "gf": 20, "gc": 12},
            "c": {"pts": 20, "pg": 1, "gf": 20, "gc": 4},
            "d": {"pts": 21, "pg": 0, "gf": 21, "gc": 27},
        }
        copas = clasificar([list("abcd")], stats)
        self.assertEqual(copas["oro"] + copas["plata"], ["d", "b", "c", "a"])


class Mexicano(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.dir.name) / "prueba.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original
        self.dir.cleanup()

    def test_mismo_puntaje_y_orden(self):
        with sqlite3.connect(db.DB_PATH) as con:
            con.executemany("INSERT INTO jugadores (nombre) VALUES (?)", [(j,) for j in "abcd"])
            con.executemany(
                "INSERT INTO mexicano_partidos VALUES (?,?,?,?,?,?,?,?,?)",
                [("mex-1-1", 1, 1, "a", "b", "c", "d", 9, 7),
                 ("mex-2-1", 2, 1, "a", "c", "b", "d", 5, 11)],
            )
        s = mexicano.get_stats()
        self.assertEqual({j: s[j]["pts"] for j in "abcd"}, {"a": 14, "b": 20, "c": 12, "d": 18})
        self.assertEqual({j: s[j]["pg"] for j in "abcd"}, {"a": 1, "b": 2, "c": 0, "d": 1})
        self.assertEqual(mexicano.get_state()["ranking"], ["b", "d", "a", "c"])
        # La ronda siguiente se arma por ese mismo orden
        ronda = mexicano.armar_ronda(list("abcd"), 3, 1, s)[0]
        self.assertEqual([ronda[k] for k in ("j1", "j2", "j3", "j4")], ["b", "d", "a", "c"])


if __name__ == "__main__":
    unittest.main()
