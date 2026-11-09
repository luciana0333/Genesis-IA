"""«Tabla temporal llena y sin uso» en Reportes y Negocio (texto de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.temporal_sin_uso import QUE_HACER_TEMPORAL_SIN_USO

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _sin_uso(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "TEMPORAL_SIN_USO"]


class TemporalSinUsoTest(unittest.TestCase):
    def test_solo_la_que_no_se_usa_con_el_texto_de_la_usuaria(self):
        # Caso del libro caja: #MOVS3 solo sirve para llenar #MOVX (se usa); #MOVX no se lee nunca.
        sql = ("CREATE TABLE #MOVS3 (nMovNro INT)\n"
               "INSERT INTO #MOVS3 SELECT 1\n"
               "DELETE FROM #MOVS3 WHERE nMovNro = 0\n"
               "CREATE TABLE #MOVX (nMovNro INT)\n"                                    # 4
               "INSERT INTO #MOVX SELECT T.nMovNro FROM #MOVS3 T\n"
               "DROP TABLE IF EXISTS #MOVS3, #MOVX")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _sin_uso(sql, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
                self.assertEqual(hallazgos[0].linea, 4)
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó que la tabla temporal #MOVX se crea y se llena con información, pero no se utiliza "
                    "posteriormente en el procedimiento. Se recomienda eliminar la tabla temporal #MOVX y las "
                    "consultas que insertan información en ella, debido a que no se utiliza posteriormente y genera "
                    "un consumo innecesario de recursos.",
                )

    def test_varias_en_una_sola_observacion(self):
        sql = ("CREATE TABLE #A (n INT)\nINSERT INTO #A SELECT 1\n"
               "SELECT 2 AS n INTO #B\n"
               "UPDATE X SET X.n = 3 FROM #A X\nCREATE NONCLUSTERED INDEX IX_B ON #B (n)\nTRUNCATE TABLE #B")
        hallazgo = _sin_uso(sql, verificar_reporte)[0]
        self.assertEqual(hallazgo.lineas, [1, 3])
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificaron las siguientes tablas temporales que se crean y se llenan con información, pero no se "
            "utilizan posteriormente en el procedimiento: #A; #B. " + QUE_HACER_TEMPORAL_SIN_USO)

    def test_lo_que_no_se_marca(self):
        for sql in (
            "CREATE TABLE #A (n INT)\nINSERT INTO #A SELECT 1\nSELECT n FROM #A",                       # se lee
            "CREATE TABLE #A (n INT)\nINSERT INTO #A SELECT 1\nIF EXISTS (SELECT 1 FROM #A) PRINT 1",   # EXISTS
            "CREATE TABLE #A (n INT)\nCREATE TABLE #B (n INT)\nINSERT #A SELECT 1\nINSERT #B SELECT 1\n"
            "UPDATE B SET B.n = A.n FROM #B B JOIN #A A ON A.n = B.n\nSELECT n FROM #B",                # origen
            "CREATE TABLE #A (n INT)\nINSERT INTO #A SELECT 1\nEXEC dbo.PA_Usa_A",                      # otro PA
            "CREATE TABLE #A (n INT)\nINSERT INTO #A SELECT 1\n"
            "DECLARE @s NVARCHAR(100) = N'SELECT * FROM #A'\nEXEC sp_executesql @s",                   # dinámico
            "CREATE TABLE #A (n INT)\nSELECT 1",                                                         # no se llena
            "CREATE TABLE #A (n INT)\nINSERT INTO #A SELECT 1\n-- SELECT * FROM #A\nSELECT 1",          # solo comentario
        ):
            for verificar in MODULOS:
                with self.subTest(sql=sql[:50], modulo=verificar.__name__):
                    esperado = 1 if "-- SELECT" in sql else 0
                    self.assertEqual(len(_sin_uso(sql, verificar)), esperado)


if __name__ == "__main__":
    unittest.main()
