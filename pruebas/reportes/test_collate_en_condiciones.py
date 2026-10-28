"""COLLATE en WHERE o JOIN (Reportes), también después de una subconsulta."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte


def _reglas(sql):
    return [h.regla for h in verificar_reporte(sql) if h.regla == "COLLATE_EN_PREDICADO"]


class CollateEnCondicionesTest(unittest.TestCase):
    def test_where_y_join(self):
        self.assertEqual(_reglas("SELECT 1 FROM A a WITH(NOLOCK) WHERE a.c COLLATE SQL_Latin1_General_CP1_CI_AS = @c"),
                         ["COLLATE_EN_PREDICADO"])
        self.assertEqual(_reglas("SELECT 1 FROM A a WITH(NOLOCK) INNER JOIN B b WITH(NOLOCK) "
                                 "ON a.c COLLATE DATABASE_DEFAULT = b.c"), ["COLLATE_EN_PREDICADO"])

    def test_despues_de_una_subconsulta(self):
        self.assertEqual(_reglas("SELECT 1 FROM A a WITH(NOLOCK) WHERE a.n IN (SELECT n FROM B WITH(NOLOCK)) "
                                 "AND a.c COLLATE SQL_Latin1_General_CP1_CI_AS = @c"), ["COLLATE_EN_PREDICADO"])
        self.assertEqual(_reglas("SELECT 1 FROM A a WITH(NOLOCK) INNER JOIN B b WITH(NOLOCK) ON a.n = b.n "
                                 "AND b.t IN (SELECT t FROM C WITH(NOLOCK)) "
                                 "AND a.c COLLATE SQL_Latin1_General_CP1_CI_AS = b.c"), ["COLLATE_EN_PREDICADO"])

    def test_fuera_de_condiciones_no_se_observa(self):
        for sql in (
            "CREATE TABLE #X (c VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AS)",
            "SELECT 1 FROM A WITH(NOLOCK) WHERE n = 1\nCREATE TABLE #X (c VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AS)",
            "SELECT c COLLATE SQL_Latin1_General_CP1_CI_AS AS c FROM A WITH(NOLOCK)",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(_reglas(sql), [])


if __name__ == "__main__":
    unittest.main()
