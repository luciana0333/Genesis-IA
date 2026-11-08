"""«Encabezado del procedimiento»: una sola regla en Reportes y Negocio (pedido de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.encabezado import QUE_HACER_ENCABEZADO_INCOMPLETO, QUE_HACER_SIN_ENCABEZADO

MODULOS = (verificar_reporte, verificar_procedimiento_normal)

COMPLETO = """/*****************************************************************************
Nombre del PA  | Logistica.PA_Provision_Sel_OrdenesSicmac
Descripción    | Procedimiento que lista las ordenes del sicmac
Autor          | LMPE
Fecha          | 04/08/2025
------------------------------------------------------------------------------
Control de Cambios
Fecha    | Autor    | Descripción
------------------------------------------------------------------------------
exec LOGISTICA.PA_Provision_Sel_OrdenesSicmac @cOpeCod=N'702401',@nDocTipo=33
*****************************************************************************/
"""
CUERPO = "CREATE PROCEDURE Logistica.PA_Provision_Sel_OrdenesSicmac\n    @cOpeCod VARCHAR(6)\nAS\nBEGIN\n    SELECT 1\nEND"


def _encabezado(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "ENCABEZADO_PROCEDIMIENTO"]


class EncabezadoTest(unittest.TestCase):
    def test_encabezado_completo_no_se_observa(self):
        for sql in (COMPLETO + CUERPO,
                    CUERPO.replace("BEGIN\n", "BEGIN\n" + COMPLETO),  # dentro del BEGIN
                    CUERPO.replace("\nAS\n", "\nAS\n" + COMPLETO)):   # justo después del AS
            for verificar in MODULOS:
                with self.subTest(modulo=verificar.__name__, sql=sql[:40]):
                    self.assertEqual(_encabezado(sql, verificar), [])

    def test_sin_encabezado(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _encabezado(CUERPO, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "bajo")
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó que el procedimiento no cuenta con un encabezado de documentación. "
                    + QUE_HACER_SIN_ENCABEZADO,
                )

    def test_comentario_dentro_del_cuerpo_no_es_encabezado(self):
        sql = CUERPO.replace("    SELECT 1", "    SELECT 1\n    /* Autor | LMPE */")
        self.assertEqual(len(_encabezado(sql, verificar_reporte)), 1)

    def test_encabezado_incompleto_nombra_solo_lo_que_falta(self):
        incompleto = (COMPLETO.replace("Autor          | LMPE\n", "Autor          |\n")
                      .replace("Control de Cambios\nFecha    | Autor    | Descripción\n", "")
                      .replace("exec LOGISTICA.PA_Provision_Sel_OrdenesSicmac @cOpeCod=N'702401',@nDocTipo=33\n", ""))
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _encabezado(incompleto + CUERPO, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].linea, 1)
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó que el encabezado del procedimiento no indica el autor, el control de cambios ni "
                    "el ejemplo de ejecución (EXEC). " + QUE_HACER_ENCABEZADO_INCOMPLETO,
                )

    def test_acepta_los_nombres_de_cada_equipo(self):
        otro_formato = """/*------------------------------------------------------------------------
PROPOSITO            | Procedimiento que genera el reporte de libro caja
CREADO POR           | RMVC
FECHA CREACION       | 09/04/2024
HISTORIAL DE CAMBIOS | FECHA  RESPONSABLE  MOTIVO
      | 12/06/2024   Y168   Se adecúa para que se considere las contra cuentas correctas.
exec [CONTABILIDAD].PA_AsientoDNHistorico_Sel_LibroCaja @cCodAge=N'03'
------------------------------------------------------------------------*/
"""
        sin_titulo = """/***************************************************************
' Nombre del PA      : dbo.PA_ExamRptas_Ins_Respuestas
' Descripción        : Registra las respuestas de la encuesta
' Autor / Fecha      : LGQL / 21-10-2026
' Fecha       Autor  Descripción
' 21/10/2026  LGQL   Creación del PA.
'         Ejemplo de Ejecucion   :
              EXEC
              dbo.PA_ExamRptas_Ins_Respuestas @cPersCod = '1'
***************************************************************/
"""
        for encabezado in (otro_formato, sin_titulo):
            with self.subTest(encabezado=encabezado[:60]):
                self.assertEqual(_encabezado(encabezado + CUERPO, verificar_reporte), [])

    def test_solo_se_revisan_procedimientos(self):
        self.assertEqual(_encabezado("SELECT 1 FROM dbo.Cliente c WITH (NOLOCK)", verificar_reporte), [])


if __name__ == "__main__":
    unittest.main()
