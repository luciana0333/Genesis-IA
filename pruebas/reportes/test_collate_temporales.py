"""Columna de texto sin COLLATE en tabla temporal: tablas #T y variables @T (Reportes y Negocio)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)
QUE_HACER = (
    "Se recomienda añadir el COLLATE establecido en las columnas de tipo texto de las tablas temporales. "
    "Por favor, revisar y aplicarlo donde corresponda."
)


def _collate(verificar, sql):
    return [h for h in verificar(sql) if h.regla == "TEMPORAL_TEXTO_SIN_COLLATE"]


class CollateTemporalesTest(unittest.TestCase):
    def test_variable_de_tabla_en_los_dos_modulos(self):
        sql = "DECLARE @Control TABLE (\n  nId INT,\n  cControl VARCHAR(100)\n)"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _collate(verificar, sql)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "alto")
                self.assertEqual(
                    hallazgos[0].mensaje,
                    f"La columna de texto cControl de la variable de tabla @Control no define COLLATE. {QUE_HACER}",
                )

    def test_tabla_temporal_y_varias_columnas(self):
        sql = ("CREATE TABLE #Temp (\n  nMonto DECIMAL(10,2),\n  cNombre VARCHAR(50),\n"
               "  cTexto VARCHAR(20) NOT NULL DEFAULT ('a,b')\n)")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgo = _collate(verificar, sql)[0]
                self.assertEqual(hallazgo.lineas, [3, 4])
                self.assertIn("cNombre de la tabla temporal #Temp no define COLLATE", hallazgo.mensaje)
                self.assertIn("cTexto de la tabla temporal #Temp", hallazgo.mensaje)
                self.assertTrue(hallazgo.mensaje.endswith(QUE_HACER))

    def test_con_collate_o_sin_texto_no_se_observa(self):
        sql = ("DECLARE @V AS TABLE (cA VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL, nB INT)\n"
               "CREATE TABLE #T (nC INT, dD DATE)")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_collate(verificar, sql), [])


if __name__ == "__main__":
    unittest.main()
