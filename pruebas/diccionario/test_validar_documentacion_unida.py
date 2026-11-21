"""ALTER: «no se incluyen» y «se agregan» en una sola observación con tabla (opción A de la usuaria, 20 nov.).

Caso real CANALES.PA_ProductoPersona_Sel_ObtenerCuentas: el diccionario no trae la descripción del procedimiento ni
de @cNroTarjeta y @nMoneda, y agrega la de @nTipoConsulta y @cCtaCodOperacion. Antes salían dos tarjetas con el
mismo título; las dos piden verificar qué descripciones ya están registradas.
"""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario

QUE_HACER = ("Incluir en el diccionario las descripciones que no estén registradas y, las que ya existan, "
             "actualizarlas con sp_updateextendedproperty en lugar de agregarlas, ya que de lo contrario la ejecución "
             "del script fallará.")

PA = """ALTER PROCEDURE CANALES.PA_ProductoPersona_Sel_ObtenerCuentas
(
    @cNroTarjeta VARCHAR(16),
    @nMoneda INT,
    @nTipoConsulta INT,
    @cCtaCodOperacion VARCHAR(18)
)
AS
SELECT 1"""


def _add(proc, parametro, esquema="CANALES"):
    return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Descripción del dato', "
            f"@level0type=N'SCHEMA', @level0name=N'{esquema}', @level1type=N'PROCEDURE', @level1name=N'{proc}', "
            f"@level2type=N'PARAMETER', @level2name=N'{parametro}';\n")


def _validar(sql, dic):
    hallazgos = verificar_diccionario(sql, dic)
    # Ya no sale aparte: está dentro de la observación unida.
    assert not [h for h in hallazgos if h.regla == "DOCUMENTACION_EXISTENTE_EN_ALTER"]
    return [h for h in hallazgos if h.regla == "VALIDAR_DOCUMENTACION_ALTER"]


class UnProcedimientoTest(unittest.TestCase):
    DIC = "\n" + _add("PA_ProductoPersona_Sel_ObtenerCuentas", "@nTipoConsulta") + _add(
        "PA_ProductoPersona_Sel_ObtenerCuentas", "@cCtaCodOperacion")

    def test_caso_canales_en_una_sola_observacion(self):
        validar = _validar(PA, self.DIC)
        self.assertEqual(len(validar), 1)
        h = validar[0]
        self.assertEqual(h.severidad.value, "bajo")
        self.assertEqual(
            h.mensaje,
            # Primera oración: texto de la usuaria (20 nov.); el detalle, para el texto copiado (en pantalla, la tabla).
            "Se identificó que el procedimiento está siendo modificado, por lo que se debe verificar si las "
            "descripciones ya están registradas en el diccionario. No se incluyen en el diccionario: (descripción "
            "del procedimiento), @cNroTarjeta, @nMoneda; Se agregan en el diccionario: @nTipoConsulta, "
            "@cCtaCodOperacion. " + QUE_HACER,
        )
        self.assertEqual(h.mensaje[h.inicio_que_hacer:], QUE_HACER)

    def test_tabla_situacion_elementos_y_cada_fila_en_su_cajita(self):
        h = _validar(PA, self.DIC)[0]
        self.assertEqual(h.grupos, [
            {"nombre": "No se incluyen en el diccionario", "tipo": "Situación", "seccion": "objeto",
             "lineas": [1, 3, 4], "etiquetas": ["(descripción del procedimiento)", "@cNroTarjeta", "@nMoneda"]},
            {"nombre": "Se agregan en el diccionario", "tipo": "Situación", "seccion": "diccionario",
             "lineas": [2, 3], "etiquetas": ["@nTipoConsulta", "@cCtaCodOperacion"]},
        ])
        # «Ver en el código» recorre fila por fila: primero el ALTER, luego el diccionario.
        self.assertEqual(h.lineas, [1, 3, 4, 2, 3])
        self.assertEqual(h.seccion, "objeto")

    def test_sin_las_dos_situaciones_no_se_une(self):
        # Solo «no se incluyen»: su frase de siempre.
        solo_faltan = _validar(PA, "")
        self.assertTrue(all(h.mensaje.startswith("Se identificó que el diccionario no incluye") for h in solo_faltan))
        # Solo «se agregan» (lo demás se actualiza): su propia observación.
        actualiza = "".join(_add("PA_ProductoPersona_Sel_ObtenerCuentas", p).replace("sp_add", "sp_update")
                            for p in ("@cNroTarjeta", "@nMoneda"))
        actualiza += ("EXEC sys.sp_updateextendedproperty @name=N'MS_Description', @value=N'Procedimiento que "
                      "obtiene', @level0type=N'SCHEMA', @level0name=N'CANALES', @level1type=N'PROCEDURE', "
                      "@level1name=N'PA_ProductoPersona_Sel_ObtenerCuentas';\n")
        reglas = [h.regla for h in verificar_diccionario(PA, actualiza + self.DIC)]
        self.assertIn("DOCUMENTACION_EXISTENTE_EN_ALTER", reglas)
        self.assertNotIn("VALIDAR_DOCUMENTACION_ALTER", reglas)


class VariosProcedimientosTest(unittest.TestCase):
    def test_procedimiento_situacion_elementos(self):
        sql = (PA + "\nGO\nALTER PROCEDURE CANALES.PA_Tarjeta_Sel_Datos\n(\n    @cNroTarjeta VARCHAR(16),\n"
               "    @nTipo INT\n)\nAS\nSELECT 2")
        dic = (_add("PA_ProductoPersona_Sel_ObtenerCuentas", "@nTipoConsulta")
               + _add("PA_Tarjeta_Sel_Datos", "@nTipo"))
        validar = _validar(sql, dic)
        self.assertEqual(len(validar), 1)
        h = validar[0]
        filas = [(g["nombre"], g.get("situacion"), g["seccion"], g["etiquetas"]) for g in h.grupos]
        self.assertEqual(filas, [
            ("CANALES.PA_ProductoPersona_Sel_ObtenerCuentas", "No se incluyen en el diccionario", "objeto",
             ["(descripción del procedimiento)", "@cNroTarjeta", "@nMoneda", "@cCtaCodOperacion"]),
            ("CANALES.PA_ProductoPersona_Sel_ObtenerCuentas", "Se agregan en el diccionario", "diccionario",
             ["@nTipoConsulta"]),
            ("CANALES.PA_Tarjeta_Sel_Datos", "No se incluyen en el diccionario", "objeto",
             ["(descripción del procedimiento)", "@cNroTarjeta"]),
            ("CANALES.PA_Tarjeta_Sel_Datos", "Se agregan en el diccionario", "diccionario", ["@nTipo"]),
        ])
        self.assertTrue(h.mensaje.startswith(
            "Se identificó que los procedimientos están siendo modificados, por lo que se debe verificar si las "
            "descripciones ya están registradas en el diccionario. CANALES.PA_ProductoPersona_Sel_ObtenerCuentas "
            "(no se incluyen en el diccionario): (descripción del procedimiento), @cNroTarjeta, @nMoneda, "
            "@cCtaCodOperacion; "))
        self.assertTrue(h.mensaje.endswith(QUE_HACER))
        # La descripción del segundo procedimiento apunta a su ALTER.
        self.assertEqual(h.grupos[2]["lineas"][0], 11)


if __name__ == "__main__":
    unittest.main()
