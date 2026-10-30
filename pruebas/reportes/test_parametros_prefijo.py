"""Parámetros sin el prefijo de su tipo (Reportes y Negocio, solo CREATE, bajo)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)
SU_CASO = ("CREATE PROCEDURE DBO.PA_GDD_ProyectoLote_Sel_Cuotas\n(\n    @ProyectoId INT,\n    @LoteId     INT\n)\n"
           "AS\nBEGIN\n    SELECT @ProyectoId, @LoteId\nEND")


def _prefijo(verificar, sql):
    return [h for h in verificar(sql) if h.regla == "PARAMETRO_SIN_PREFIJO_TIPO"]


class ParametrosPrefijoTest(unittest.TestCase):
    def test_su_caso_en_los_dos_modulos(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgo = _prefijo(verificar, SU_CASO)[0]
                self.assertEqual(hallazgo.severidad.value, "bajo")
                self.assertEqual(hallazgo.lineas, [3, 4])
                self.assertIn("@ProyectoId (INT) → @nProyectoId; @LoteId (INT) → @nLoteId", hallazgo.mensaje)

    def test_un_parametro_y_prefijo_equivocado(self):
        sql = "CREATE PROCEDURE dbo.PA_GDD_Cliente_Sel_Datos (@cMonto INT, @nId INT) AS SELECT 1"
        self.assertEqual(
            _prefijo(verificar_reporte, sql)[0].mensaje,
            "Se identificó que el parámetro @cMonto de tipo INT no indica su tipo de dato con el prefijo "
            "correspondiente. Se recomienda nombrarlo @nMonto, ya que el prefijo (c texto, n número, d fecha u hora, "
            "b bit) permite identificar el tipo de dato del parámetro.",
        )

    def test_correctos_y_tipos_sin_prefijo_no_se_observan(self):
        sql = ("CREATE PROCEDURE dbo.PA_GDD_Cliente_Sel_Datos (@nId INT, @cNombre VARCHAR(50) = '', "
               "@nMonto DECIMAL(18, 2) = 0, @dFecha DATE OUTPUT, @bActivo BIT = 1, @jData NVARCHAR(MAX), "
               "@xRespuestas XML, @Guid UNIQUEIDENTIFIER, @Lista dbo.TipoLista READONLY) AS SELECT 1")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_prefijo(verificar, sql), [])

    def test_alter_no_se_revisa(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_prefijo(verificar, SU_CASO.replace("CREATE", "ALTER")), [])


if __name__ == "__main__":
    unittest.main()
