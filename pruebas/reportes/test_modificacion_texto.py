"""«Modificación de tabla física» en Reportes: «Qué hacer» con el texto de la usuaria (13 nov., política del DBA)."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte

_QUE_HACER = ("Se recomienda gestionar este cambio con el equipo de Proyectos, ya que el área de Gestión de Datos debe "
              "limitarse a realizar consultas de información y no crear ni modificar tablas dentro de las bases de "
              "datos.")


def _modificaciones(sql):
    return [h for h in verificar_reporte(sql) if h.regla == "MODIFICACION_TABLA_FISICA"]


class ModificacionTablaFisicaTextoTest(unittest.TestCase):
    def test_un_caso(self):
        sql = ("ALTER PROCEDURE dbo.PA_GDD_Cobranzas_Sel_Detalle AS\nBEGIN\n"
               " TRUNCATE TABLE DBCMACICABI.dbo.BiCobranzasDetalle;\nEND")
        hallazgo = _modificaciones(sql)[0]
        self.assertEqual(hallazgo.severidad.value, "critico")
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificó que el reporte modifica la tabla DBCMACICABI.dbo.BiCobranzasDetalle con TRUNCATE TABLE. "
            + _QUE_HACER,
        )

    def test_caso_de_la_usuaria_dos_cambios_mismo_que_hacer(self):
        sql = ("ALTER PROCEDURE dbo.PA_GDD_Cobranzas_Sel_Detalle AS\nBEGIN\n"
               " TRUNCATE TABLE DBCMACICABI.dbo.BiCobranzasDetalle;\n"
               " INSERT INTO DBCMACICABI.dbo.BiCobranzasDetalle (a) SELECT 1;\nEND")
        hallazgo = _modificaciones(sql)[0]
        self.assertTrue(hallazgo.mensaje.endswith(_QUE_HACER))
        self.assertNotIn("procedimiento de negocio", hallazgo.mensaje)


if __name__ == "__main__":
    unittest.main()
