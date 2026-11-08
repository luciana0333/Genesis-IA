"""«Uso de CREATE OR ALTER» en Reportes y Negocio (texto de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)
TEXTO = (
    "Se identificó el uso de CREATE OR ALTER en la definición del procedimiento. Se recomienda verificar si el "
    "procedimiento ya existe. Si existe, utilizar ALTER PROCEDURE; de lo contrario, utilizar CREATE PROCEDURE. "
    "Evitar el uso de CREATE OR ALTER."
)


def _create_or_alter(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "CREATE_OR_ALTER"]


class CreateOrAlterTest(unittest.TestCase):
    def test_se_observa_con_el_texto_de_la_usuaria(self):
        for sql in ("CREATE OR ALTER PROCEDURE [dbo].[PA_GDD_Cartera_Sel_Saldos]\nAS\nSELECT 1",
                    "create  or\n alter proc dbo.PA_GDD_Cartera_Sel_Saldos AS SELECT 1"):
            for verificar in MODULOS:
                with self.subTest(sql=sql[:30], modulo=verificar.__name__):
                    hallazgos = _create_or_alter(sql, verificar)
                    self.assertEqual(len(hallazgos), 1)
                    self.assertEqual(hallazgos[0].severidad.value, "medio")
                    self.assertEqual(hallazgos[0].linea, 1)
                    self.assertEqual(hallazgos[0].mensaje, TEXTO)

    def test_create_o_alter_solos_no_se_observan(self):
        for sql in ("CREATE PROCEDURE dbo.PA_GDD_Cartera_Sel_Saldos AS SELECT 1",
                    "ALTER PROCEDURE dbo.PA_GDD_Cartera_Sel_Saldos AS SELECT 1",
                    "-- CREATE OR ALTER PROCEDURE dbo.PA_Viejo\nALTER PROCEDURE dbo.PA_GDD_Cartera_Sel_Saldos AS SELECT 1"):
            for verificar in MODULOS:
                with self.subTest(sql=sql[:30], modulo=verificar.__name__):
                    self.assertEqual(_create_or_alter(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
