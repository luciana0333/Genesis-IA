"""Redacción de las descripciones del diccionario: pasado sin tilde, falta el «que» y nombre vs. descripción."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.descripcion_vs_nombre import contradice
from app.analizadores.ortografia import palabras_mal_escritas


def _exec(valor, proc, parametro=None):
    nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
    return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{valor}', "
            f"@level0type=N'SCHEMA', @level0name=N'Logistica', @level1type=N'PROCEDURE', "
            f"@level1name=N'{proc}'{nivel2}\n")


class PasadoSinTildeTest(unittest.TestCase):
    def test_tras_el_cual_o_que_ya_no_se_exige_la_tilde(self):
        # Pedido de la usuaria (7 nov.): las tildes se pueden omitir en el diccionario.
        for texto in ("Usuario el cual solicito la disponibilidad.", "Usuario que registro la operación.",
                      "Fecha en que se realizo el pago."):
            with self.subTest(texto=texto):
                self.assertEqual(palabras_mal_escritas(texto), [])

    def test_sustantivos_y_que_tipo_de_no_se_observan(self):
        for texto in ("El registro de la operación.", "Indica que tipo de cliente es.", "Código del pago."):
            with self.subTest(texto=texto):
                self.assertEqual(palabras_mal_escritas(texto), [])


class FaltaQueTest(unittest.TestCase):
    def test_procedimiento_y_tabla_sin_que(self):
        self.assertEqual(
            palabras_mal_escritas("Procedimiento almacenado actualiza el estado a observado"),
            [("Procedimiento almacenado actualiza", ["Procedimiento almacenado que actualiza"])],
        )
        self.assertEqual(palabras_mal_escritas("Tabla almacena los créditos"),
                         [("Tabla almacena", ["Tabla que almacena"])])
        self.assertEqual(palabras_mal_escritas("Procedimiento almacenado devuelve el saldo")[0][1],
                         ["Procedimiento almacenado que devuelve"])

    def test_bien_redactadas_no_se_observan(self):
        for texto in ("Tabla de clientes", "Tabla maestra de agencias", "Procedimiento almacenado que actualiza el estado",
                      "Procedimiento almacenado para listar los créditos", "Procedimiento almacenado encargado de registrar",
                      "Procedimiento de consulta de saldos"):
            with self.subTest(texto=texto):
                self.assertEqual(palabras_mal_escritas(texto), [])


class DescripcionVsNombreTest(unittest.TestCase):
    def test_codigo_descrito_como_monto(self):
        self.assertEqual(contradice("@nCodMonedaTotal", "Monto total expresado en la moneda"), ("un monto", "un código"))
        self.assertEqual(contradice("@dFechaRegistro", "Código de registro"), ("un código", "una fecha"))

    def test_coinciden_o_no_es_claro(self):
        for nombre, descripcion in (("@nCodMoneda", "Código de la moneda"), ("@nMontoSolicitado", "Monto solicitado"),
                                    ("@nCotizacionRequerimientoId", "Indica el número de identificación"),
                                    ("@nSaldoCapital", "Monto del saldo"), ("@cUsuario", "Código del usuario")):
            with self.subTest(nombre=nombre):
                self.assertIsNone(contradice(nombre, descripcion))

    def test_en_el_diccionario_de_procedimientos(self):
        proc = "PA_Disponibilidad_Upd_Informacion"
        sql = f"CREATE PROCEDURE Logistica.{proc} (@nCodMonedaTotal INT)"
        dic = (_exec("Procedimiento almacenado que actualiza la información.", proc)
               + _exec("Monto total expresado en la moneda seleccionada.", proc, "@nCodMonedaTotal"))
        hallazgo = [h for h in verificar_diccionario(sql, dic) if h.regla == "DESCRIPCION_NO_COINCIDE_CON_NOMBRE"][0]
        self.assertEqual(hallazgo.severidad.value, "medio")
        self.assertEqual(
            hallazgo.mensaje,
            "La descripción del parámetro @nCodMonedaTotal habla de un monto, pero su nombre indica un código. Se "
            "recomienda revisar la descripción o el nombre del parámetro, ya que deben referirse al mismo dato.",
        )


class OrtografiaConVariosProcedimientosTest(unittest.TestCase):
    def test_cada_descripcion_en_su_vineta_con_su_procedimiento(self):
        a, b = "PA_Uno_Sel_Datos", "PA_Dos_Upd_Datos"
        sql = f"CREATE PROCEDURE Logistica.{a} (@nId INT)\nCREATE PROCEDURE Logistica.{b} (@cMensaje VARCHAR(10))"
        dic = (_exec("Procedimiento almacenado que selecciona los datos.", a)
               + _exec("Indica el número de la cotisacion.", a, "@nId")
               + _exec("Procedimiento almacenado que actualiza los datos.", b)
               + _exec("Mensaje de la ejecusion.", b, "@cMensaje"))
        mensaje = [h for h in verificar_diccionario(sql, dic) if h.regla == "ERROR_ORTOGRAFICO"][0].mensaje
        self.assertIn("Se identificaron 2 palabras mal escritas en el diccionario: 'cotisacion' → 'cotización' y "
                      "'ejecusion' → 'ejecución'.", mensaje)
        self.assertNotIn(" : ", mensaje)

    def test_misma_palabra_en_varios_procedimientos_dice_de_cual_es_cada_parametro(self):
        a, b = "PA_Uno_Sel_Datos", "PA_Dos_Upd_Datos"
        sql = f"CREATE PROCEDURE Logistica.{a} (@nId INT)\nCREATE PROCEDURE Logistica.{b} (@cMensaje VARCHAR(10))"
        dic = (_exec("Procedimiento que consulta la cotisacion.", a)
               + _exec("Número de la cotisacion.", a, "@nId")
               + _exec("Procedimiento que actualiza la cotisacion.", b)
               + _exec("Mensaje de la cotisacion.", b, "@cMensaje"))
        hallazgos = [h for h in verificar_diccionario(sql, dic) if h.regla == "ERROR_ORTOGRAFICO"]
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].lineas, [1, 2, 3, 4])
        # La palabra sale una vez aunque esté en 4 descripciones; sus líneas van en el encabezado.
        self.assertIn("Se identificó una palabra mal escrita en el diccionario: 'cotisacion' → 'cotización'.",
                      hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
