"""Procedimiento sin esquema: el mismo «Qué hacer» en Reportes y Negocio (texto de la usuaria, 7 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

QUE_HACER = (
    "Se recomienda indicar el esquema correspondiente; de ser dbo, colocarlo explícitamente "
    "(ej.: dbo.PA_OBTIENEDATOS_CALCULODEVENGADO), ya que, si se omite, se utiliza el esquema predeterminado del "
    "usuario, lo que podría ocasionar que el objeto se cree o modifique en un esquema distinto al esperado y generar "
    "búsquedas adicionales al utilizarlo."
)


class ProcedimientoSinEsquemaTest(unittest.TestCase):
    def test_mismo_que_hacer_en_reportes_y_negocio(self):
        sql = "CREATE PROCEDURE PA_OBTIENEDATOS_CALCULODEVENGADO AS SELECT 1"
        for verificar in (verificar_reporte, verificar_procedimiento_normal):
            with self.subTest(modulo=verificar.__name__):
                hallazgo = [h for h in verificar(sql) if h.regla == "PROCEDIMIENTO_SIN_ESQUEMA"][0]
                self.assertTrue(hallazgo.mensaje.endswith(QUE_HACER), hallazgo.mensaje)

    def test_con_esquema_no_se_observa(self):
        sql = "CREATE PROCEDURE dbo.PA_OBTIENEDATOS_CALCULODEVENGADO AS SELECT 1"
        for verificar in (verificar_reporte, verificar_procedimiento_normal):
            with self.subTest(modulo=verificar.__name__):
                self.assertNotIn("PROCEDIMIENTO_SIN_ESQUEMA", {h.regla for h in verificar(sql)})


if __name__ == "__main__":
    unittest.main()
