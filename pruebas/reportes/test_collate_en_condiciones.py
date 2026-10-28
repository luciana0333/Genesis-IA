"""COLLATE en WHERE o JOIN (Reportes y Negocio), también después de una subconsulta."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _reglas(verificar, sql):
    return [h.regla for h in verificar(sql) if h.regla == "COLLATE_EN_PREDICADO"]


class CollateEnCondicionesTest(unittest.TestCase):
    def _en_los_dos(self, sql, esperado):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__, sql=sql):
                self.assertEqual(_reglas(verificar, sql), esperado)

    def test_where_y_join(self):
        self._en_los_dos("SELECT 1 FROM A a WITH(NOLOCK) WHERE a.c COLLATE SQL_Latin1_General_CP1_CI_AS = @c",
                         ["COLLATE_EN_PREDICADO"])
        self._en_los_dos("SELECT 1 FROM A a WITH(NOLOCK) INNER JOIN B b WITH(NOLOCK) "
                         "ON a.c COLLATE DATABASE_DEFAULT = b.c", ["COLLATE_EN_PREDICADO"])

    def test_despues_de_una_subconsulta(self):
        self._en_los_dos("SELECT 1 FROM A a WITH(NOLOCK) WHERE a.n IN (SELECT n FROM B WITH(NOLOCK)) "
                         "AND a.c COLLATE SQL_Latin1_General_CP1_CI_AS = @c", ["COLLATE_EN_PREDICADO"])
        self._en_los_dos("SELECT 1 FROM A a WITH(NOLOCK) INNER JOIN B b WITH(NOLOCK) ON a.n = b.n "
                         "AND b.t IN (SELECT t FROM C WITH(NOLOCK)) "
                         "AND a.c COLLATE SQL_Latin1_General_CP1_CI_AS = b.c", ["COLLATE_EN_PREDICADO"])

    def test_fuera_de_condiciones_no_se_observa(self):
        for sql in (
            "CREATE TABLE #X (c VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AS)",
            "SELECT 1 FROM A WITH(NOLOCK) WHERE n = 1\nCREATE TABLE #X (c VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AS)",
            "SELECT c COLLATE SQL_Latin1_General_CP1_CI_AS AS c FROM A WITH(NOLOCK)",
            "SELECT 1 FROM A a WITH(NOLOCK) WHERE a.c IN (SELECT c COLLATE SQL_Latin1_General_CP1_CI_AS FROM B WITH(NOLOCK))",
        ):
            self._en_los_dos(sql, [])


if __name__ == "__main__":
    unittest.main()
