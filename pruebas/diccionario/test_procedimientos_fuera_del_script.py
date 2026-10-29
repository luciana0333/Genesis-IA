"""Diccionario de varios procedimientos que documenta otros que no están en el script."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.diccionario_nomenclatura import nomenclatura_procedimiento
from app.analizadores.ortografia import sugerencias

PROCS = ("CREATE PROCEDURE GARANTIA.PA_Testimonio_Ins_Comentario (@jData NVARCHAR(MAX), @nMensaje INT OUTPUT)\n"
         "CREATE PROCEDURE GARANTIA.PA_Testimonio_Sel_Validar (@cPersCod VARCHAR(13))")


def _exec(proc, valor, parametro=None):
    nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
    return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{valor}', @level0type=N'SCHEMA', "
            f"@level0name=N'GARANTIA', @level1type=N'PROCEDURE', @level1name=N'{proc}'{nivel2}\n")


DICCIONARIO = (
    _exec("PA_Testimonio_Ins_Comentario", "Procedimiento que registra el comentario.")
    + _exec("PA_Testimonio_Ins_Comentario", "Datos del comentario.", "@jData")
    + _exec("PA_Testimonio_Ins_Comentario", "Resultado de la operación.", "@nMensaje")
    # Otro procedimiento que no está en el script, con un parámetro que el anterior también tiene.
    + _exec("PA_AmpliacionTestimonio_Sel_ValidarSolicitud", "Procedimiento que valida la solicitud.")
    + _exec("PA_AmpliacionTestimonio_Sel_ValidarSolicitud", "Datos de los créditos.", "@jData")
    + _exec("PA_AmpliacionTestimonio_Sel_ValidarSolicitud", "Tipo de ventana.", "@nTipoVentana")
    + _exec("PA_Testimonio_Sel_Validar", "Procedimiento que valida el testimonio.")
    + _exec("PA_Testimonio_Sel_Validar", "Código de persona.", "@cPersCod")
)


class ProcedimientosFueraDelScriptTest(unittest.TestCase):
    def test_se_avisa_una_vez_sin_errores_falsos(self):
        hallazgos = verificar_diccionario(PROCS, DICCIONARIO)
        reglas = {h.regla for h in hallazgos}
        for falsa in ("NOMBRE_NO_COINCIDE", "DOCUMENTACION_DUPLICADA", "PARAMETRO_NO_EXISTE"):
            self.assertNotIn(falsa, reglas)
        fuera = [h for h in hallazgos if h.regla == "PROCEDIMIENTO_FUERA_DEL_SCRIPT"][0]
        self.assertEqual(fuera.severidad.value, "medio")
        self.assertEqual(fuera.lineas, [4, 5, 6])
        self.assertEqual(
            fuera.mensaje,
            "Se identificó documentación del procedimiento PA_AmpliacionTestimonio_Sel_ValidarSolicitud, que no está "
            "en el script de los procedimientos. Se recomienda adjuntar el CREATE PROCEDURE de ese procedimiento para "
            "revisar su documentación, o retirar esas sentencias si no corresponden a este pase.",
        )

    def test_nombre_mal_escrito_sigue_siendo_nombre_que_no_coincide(self):
        diccionario = DICCIONARIO.replace("PA_Testimonio_Sel_Validar'", "PA_Testimonio_Sel_Valida'")
        reglas = {h.regla for h in verificar_diccionario(PROCS, diccionario)}
        self.assertIn("NOMBRE_NO_COINCIDE", reglas)


class SugerenciasConLetraFaltanteTest(unittest.TestCase):
    def test_prefiere_agregar_la_letra_que_falta(self):
        self.assertEqual(sugerencias("vencdos"), ["vencidos"])
        self.assertEqual(sugerencias("Cdigo"), ["Código"])
        self.assertEqual(sugerencias("ususario"), ["usuario"])


class TablaSeparadaEnElNombreTest(unittest.TestCase):
    def test_sugiere_juntar_la_tabla(self):
        regla, mensaje = nomenclatura_procedimiento("PA_Garantia_Testimonio_Upd_EstadoTestimonio")[0]
        self.assertEqual(regla, "PROCEDIMIENTO_TABLA_SEPARADA")
        self.assertIn("(ej.: PA_GarantiaTestimonio_Upd_EstadoTestimonio)", mensaje)

    def test_sin_accion_en_ningun_lado_sigue_igual(self):
        self.assertEqual(nomenclatura_procedimiento("PA_Cliente_Listado_Activos")[0][0], "PROCEDIMIENTO_SIN_ACCION")


if __name__ == "__main__":
    unittest.main()
