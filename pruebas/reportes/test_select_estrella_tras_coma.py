"""SELECT * también cuando el * va después de una coma: «SELECT ROW_NUMBER() … AS NRO, * FROM #T» (usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _estrella(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "SELECT_ESTRELLA_PROHIBIDO"]


class SelectEstrellaTrasComaTest(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        sql = ("SELECT A.cPersCod FROM #TMP_COMPENSABLES A INNER JOIN (\n"
               "    SELECT ROW_NUMBER() OVER(PARTITION BY cPersCod ORDER BY CPersCod) AS NRO\n"
               "    ,*\n"
               "    FROM #TMP_COMPENSABLES\n"
               ") B ON A.cPersCod = B.cPersCod AND NRO = 1")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _estrella(sql, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].linea, 3)
                self.assertTrue(hallazgos[0].mensaje.startswith(
                    "Se identificó el uso de SELECT * sobre la tabla temporal #TMP_COMPENSABLES."))

    def test_lo_que_no_es_select_estrella(self):
        for sql in ("SELECT COUNT(*), a FROM #T", "SELECT a, b FROM #T", "SELECT a * 2, b FROM #T"):
            for verificar in MODULOS:
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    self.assertEqual(_estrella(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
