"""Falsos positivos del PA de la usuaria PA_NET_InsertaDataTrxBaseII (11 nov.), en Reportes y Negocio:

- El encabezado en la plantilla en inglés de SSMS (Author / Create date / Description / historial) sí cuenta.
- «-- Create date: 05-09-2012» y «-- Update:» son etiquetas del encabezado, no código comentado.
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)

_ENCABEZADO_SSMS = (
    "-- =====================================================================\n"
    "-- Author:\t\tLFCE\n"                                                    # 2
    "-- Create date: 05-09-2012\n"                                            # 3
    "-- Update:\t\t\n"                                                        # 4
    "-- User Update:\t\n"                                                     # 5
    "-- Description:\tInserta en tablas Datos de las Trx VISA\n"              # 6
    "-- =====================================================================\n"
    "-- AAAA-MM-DD - USER -\tDescripcion del cambio\n"
    "-- 2016-04-29 - KAAY -\tAgrega Registro de Usuario a NETLogConciliacion\n"
    "-- =====================================================================\n"
)
_PA = "ALTER PROCEDURE [dbo].[PA_NET_InsertaDataTrxBaseII] @pCodUsu VARCHAR(10)\nAS\nBEGIN\n    SELECT 1;\nEND"


def _reglas(sql, verificar):
    return {h.regla: h for h in verificar(sql)}


class EncabezadoInglesTest(unittest.TestCase):
    def test_plantilla_de_ssms_solo_le_falta_el_nombre_y_el_exec(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgo = _reglas(_ENCABEZADO_SSMS + _PA, verificar)["ENCABEZADO_PROCEDIMIENTO"]
                self.assertTrue(hallazgo.mensaje.startswith(
                    "Se identificó que el encabezado del procedimiento no indica el nombre del procedimiento ni el "
                    "ejemplo de ejecución (EXEC)."))

    def test_plantilla_de_ssms_completa_no_se_marca(self):
        completo = (_ENCABEZADO_SSMS
                    + "-- EXEC dbo.PA_NET_InsertaDataTrxBaseII @pCodUsu = 'LFCE'\n")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertNotIn("ENCABEZADO_PROCEDIMIENTO", _reglas(completo + _PA, verificar))

    def test_etiquetas_del_encabezado_no_son_codigo_comentado(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertNotIn("CODIGO_SQL_COMENTADO", _reglas(_ENCABEZADO_SSMS + _PA, verificar))

    def test_el_codigo_comentado_real_se_sigue_detectando(self):
        cuerpo = ("ALTER PROCEDURE dbo.PA_X AS\nBEGIN\n"
                  "    --UPDATE dbo.T SET a = 1\n"                     # 3
                  "    -- CREATE TABLE #T (a INT)\n"                   # 4
                  "    /* DELETE FROM dbo.T */\n"                      # 5
                  "    /* Create date: 05-09-2012 */\n"
                  "    SELECT 1;\nEND")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_reglas(cuerpo, verificar)["CODIGO_SQL_COMENTADO"].lineas, [3, 4, 5])


if __name__ == "__main__":
    unittest.main()
