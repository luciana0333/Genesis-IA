"""Eliminación de temporales con un procedimiento (2 nov., Reportes y Negocio, bajo, texto de la usuaria).

    EXEC DBCMACICA.[dbo].[PA_NET_EliminaTablaTemporal] @pNombreTablaTemporal = 'TEMPDB.dbo.#TempXmlOutCabecera'
    →  DROP TABLE IF EXISTS #TempXmlOutCabecera
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

AREAS = {"Reportes": verificar_reporte, "Negocio": verificar_procedimiento_normal}
ACCION = ("Se recomienda evitar el uso de procedimientos almacenados para la eliminación de tablas temporales y "
          "optar por el uso de DROP TABLE IF EXISTS.")


def _procedimiento(cuerpo: str) -> str:
    return f"CREATE PROCEDURE dbo.PA_GDD_Cliente_Sel_Resumen\nAS\nBEGIN\n{cuerpo}\nEND"


def _reglas(verificar, cuerpo):
    return [h for h in verificar(_procedimiento(cuerpo)) if h.regla == "ELIMINACION_TEMPORAL_CON_PROCEDIMIENTO"]


class EliminacionTemporalConProcedimientoTest(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        cuerpo = (" -- ELIMINA TABLAS TEMPORALES: VA EN TODOS LOS PA\n"
                  " EXEC DBCMACICA.[dbo].[PA_NET_EliminaTablaTemporal] @pNombreTablaTemporal = "
                  "'TEMPDB.dbo.#TempXmlOutCabecera', @pReturn = @bReturn OUTPUT")
        for area, verificar in AREAS.items():
            with self.subTest(area=area):
                hallazgos = _reglas(verificar, cuerpo)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "bajo")
                self.assertEqual(hallazgos[0].linea, 5)
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó el uso del procedimiento DBCMACICA.dbo.PA_NET_EliminaTablaTemporal para eliminar "
                    "la tabla temporal #TempXmlOutCabecera. " + ACCION,
                )

    def test_varias_tablas_en_una_observacion(self):
        cuerpo = (" EXEC DBCMACICA.dbo.PA_NET_EliminaTablaTemporal 'tempdb..#TempA'\n"
                  " EXEC DBCMACICA.dbo.PA_NET_EliminaTablaTemporal 'tempdb..#TempB'\n"
                  " EXEC DBCMACICA.dbo.PA_NET_EliminaTablaTemporal 'tempdb..#TempC'")
        for area, verificar in AREAS.items():
            with self.subTest(area=area):
                hallazgos = _reglas(verificar, cuerpo)
                self.assertEqual(len(hallazgos), 1)
                self.assertIn("las tablas temporales #TempA, #TempB y #TempC.", hallazgos[0].mensaje)
                self.assertEqual(hallazgos[0].lineas, [4, 5, 6])

    def test_no_se_marca(self):
        for cuerpo in (
            # Comentada.
            " -- EXEC DBCMACICA.dbo.PA_NET_EliminaTablaTemporal 'tempdb..#TempA'",
            # La tabla va en una variable: no se sabe si es temporal.
            " EXEC DBCMACICA.dbo.PA_NET_EliminaTablaTemporal @pNombreTablaTemporal = @cTabla",
            # Otro procedimiento.
            " EXEC dbo.PA_Cliente_Sel_Datos 'tempdb..#TempA'",
            # Ya usa DROP TABLE IF EXISTS.
            " DROP TABLE IF EXISTS #TempA",
        ):
            for area, verificar in AREAS.items():
                with self.subTest(area=area, cuerpo=cuerpo):
                    self.assertEqual(_reglas(verificar, cuerpo), [])


if __name__ == "__main__":
    unittest.main()
