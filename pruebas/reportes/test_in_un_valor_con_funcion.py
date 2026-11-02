"""IN con un solo valor cuando lo comparado es una función (UPPER(c), ISNULL(c, 0)), en Reportes y Negocio.

Antes Negocio no lo marcaba y Reportes ponía un ejemplo con una columna que no estaba en el código
(«WHERE nEstado = 'A'»). Con LEFT(col, 1) IN ('A') la observación de LIKE ya cubre el IN: no se repite.
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

AREAS = {"Reportes": verificar_reporte, "Negocio": verificar_procedimiento_normal}


def _reglas(verificar, sql, regla):
    return [h for h in verificar(sql) if h.regla == regla]


class InConFuncionTest(unittest.TestCase):
    def test_funcion_antes_del_in(self):
        casos = {
            "SELECT a FROM T WITH (NOLOCK) WHERE UPPER(cRhCod) IN ('A')": "UPPER(cRhCod) = 'A'",
            "SELECT a FROM T WITH (NOLOCK) WHERE ISNULL(c.nEstado, 0) NOT IN (2)": "ISNULL(c.nEstado, 0) <> 2",
            "SELECT a FROM T WITH (NOLOCK) WHERE c.cEstado IN ('A')": "c.cEstado = 'A'",
        }
        for area, verificar in AREAS.items():
            for sql, ejemplo in casos.items():
                with self.subTest(area=area, sql=sql):
                    hallazgos = _reglas(verificar, sql, "IN_CON_UN_SOLO_VALOR")
                    self.assertEqual(len(hallazgos), 1)
                    self.assertIn(ejemplo, hallazgos[0].mensaje)
                    self.assertNotIn("nEstado = 'A'", hallazgos[0].mensaje)

    def test_left_in_un_valor_solo_se_observa_como_like(self):
        sql = "SELECT a FROM T WITH (NOLOCK) WHERE LEFT(cRhCod,1) IN ('A') AND nRHEstado = 201"
        for area, verificar in AREAS.items():
            with self.subTest(area=area):
                self.assertEqual(_reglas(verificar, sql, "IN_CON_UN_SOLO_VALOR"), [])
                self.assertEqual(len(_reglas(verificar, sql, "LEFT_REEMPLAZABLE_POR_LIKE")), 1)

    def test_subconsulta_no_es_un_valor(self):
        sql = "SELECT a FROM T WITH (NOLOCK) WHERE x = 1 AND c.n IN (SELECT n FROM U WITH (NOLOCK))"
        for area, verificar in AREAS.items():
            with self.subTest(area=area):
                self.assertEqual(_reglas(verificar, sql, "IN_CON_UN_SOLO_VALOR"), [])


if __name__ == "__main__":
    unittest.main()
