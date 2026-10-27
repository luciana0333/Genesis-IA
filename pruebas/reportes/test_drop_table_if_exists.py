"""DROP TABLE IF EXISTS en lugar de IF OBJECT_ID(...) IS NOT NULL DROP TABLE (Reportes y Negocio)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _drop(verificar, sql):
    return [h for h in verificar(sql) if h.regla == "DROP_TABLE_CON_VALIDACION"]


class TestDropTableIfExists(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        sql = "IF OBJECT_ID('tempdb..#temporal') IS NOT NULL\n    DROP TABLE #temporal;"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _drop(verificar, sql)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "bajo")
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó la validación IF OBJECT_ID('tempdb..#temporal') IS NOT NULL para eliminar la tabla "
                    "temporal #temporal. Se recomienda reemplazarla por DROP TABLE IF EXISTS #temporal, ya que elimina "
                    "la tabla si existe en una sola instrucción y no genera error si la tabla no está creada.",
                )

    def test_otras_formas_de_la_misma_validacion(self):
        casos = (
            "if object_id('tempdb..#Data','U') is not null\nbegin\n  drop table #Data\nend",
            "IF OBJECT_ID(N'tempdb.dbo.#Data') IS NOT NULL DROP TABLE #Data",
            "IF EXISTS (SELECT 1 FROM tempdb..sysobjects WHERE name LIKE '#Data%') DROP TABLE #Data",
            "IF EXISTS (SELECT * FROM tempdb.sys.objects WHERE object_id = OBJECT_ID('tempdb..#Data')) DROP TABLE #Data",
        )
        for sql in casos:
            for verificar in MODULOS:
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    self.assertEqual(len(_drop(verificar, sql)), 1)

    def test_no_se_marca(self):
        casos = (
            "DROP TABLE IF EXISTS #Data;",                                         # ya es lo correcto
            "DROP TABLE #Data;",                                                   # sin validación
            "IF OBJECT_ID('dbo.Cliente') IS NOT NULL DROP TABLE dbo.Cliente",      # tabla física
            "-- IF OBJECT_ID('tempdb..#X') IS NOT NULL DROP TABLE #X",             # comentado
            "IF OBJECT_ID('tempdb..#X') IS NULL CREATE TABLE #X (n INT)",          # otra validación
        )
        for sql in casos:
            for verificar in MODULOS:
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    self.assertEqual(_drop(verificar, sql), [])

    def test_varias_en_una_observacion_con_sus_lineas(self):
        sql = ("IF OBJECT_ID('tempdb..#A') IS NOT NULL DROP TABLE #A\nSELECT 1\n"
               "IF OBJECT_ID('tempdb..#B') IS NOT NULL DROP TABLE #B")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _drop(verificar, sql)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].lineas, [1, 3])
                self.assertTrue(hallazgos[0].mensaje.startswith(
                    "Se identificaron 2 validaciones antes de eliminar tablas temporales, en las líneas 1, 3: "
                    "IF OBJECT_ID('tempdb..#A') IS NOT NULL para la tabla temporal #A; "
                    "IF OBJECT_ID('tempdb..#B') IS NOT NULL para la tabla temporal #B."))


if __name__ == "__main__":
    unittest.main()
