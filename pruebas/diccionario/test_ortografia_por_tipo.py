"""Ortografía del diccionario (1 nov.): mensaje corto que dice qué tipo de error es, sin decir dónde está."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.ortografia import mensaje_ortografia_diccionario

_ACCION = ("Se recomienda revisar y corregir las palabras indicadas en el diccionario, a fin de mantener una "
           "documentación clara y correcta.")


def _exec(valor, proc="PA_Cliente_Sel_Datos", parametro=None):
    nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
    return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{valor}', @level0type=N'SCHEMA', "
            f"@level0name=N'dbo', @level1type=N'PROCEDURE', @level1name=N'{proc}'{nivel2}\n")


class MensajePorTipoTest(unittest.TestCase):
    def test_todas_sin_tilde(self):
        self.assertEqual(
            mensaje_ortografia_diccionario([("credito", ["crédito"]), ("Codigo", ["Código"])]),
            "Se identificaron 2 palabras sin tilde en el diccionario: 'credito' → 'crédito' y 'Codigo' → 'Código'.",
        )
        self.assertEqual(mensaje_ortografia_diccionario([("credito", ["crédito"])]),
                         "Se identificó una palabra sin tilde en el diccionario: 'credito' → 'crédito'.")

    def test_todas_mal_escritas_y_sin_sugerencia(self):
        self.assertEqual(
            mensaje_ortografia_diccionario([("clienet", ["cliente"]), ("ROJSH", [])]),
            "Se identificaron 2 palabras mal escritas en el diccionario: 'clienet' → 'cliente' y 'ROJSH' (revisar).",
        )

    def test_redaccion(self):
        self.assertEqual(
            mensaje_ortografia_diccionario([("Tabla almacena", ["Tabla que almacena"])]),
            "Se identificó un error de redacción en el diccionario: 'Tabla almacena' → 'Tabla que almacena'.",
        )

    def test_tipos_mezclados_van_separados(self):
        self.assertEqual(
            mensaje_ortografia_diccionario([
                ("credito", ["crédito"]), ("clienet", ["cliente"]), ("Codigo", ["Código"]),
                ("Procedimiento almacenado actualiza", ["Procedimiento almacenado que actualiza"]),
            ]),
            "Se identificaron 4 errores ortográficos en el diccionario: Sin tilde: 'credito' → 'crédito' y "
            "'Codigo' → 'Código'; Mal escritas: 'clienet' → 'cliente'; Redacción: 'Procedimiento almacenado "
            "actualiza' → 'Procedimiento almacenado que actualiza'.",
        )


class EnLosDosDiccionariosTest(unittest.TestCase):
    def test_procedimientos_cada_palabra_una_vez_con_todas_sus_lineas(self):
        sql = "CREATE PROCEDURE dbo.PA_Cliente_Sel_Datos (@cCodTrx VARCHAR(6), @cPersCod VARCHAR(13))"
        dic = (_exec("Procedimiento que obtiene el credito del cliente")
               + _exec("Codigo de la transaccion", parametro="@cCodTrx")
               + _exec("Codigo de la persona", parametro="@cPersCod"))
        hallazgos = [h for h in verificar_diccionario(sql, dic) if h.regla == "ERROR_ORTOGRAFICO"]
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].lineas, [1, 2, 3])
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificaron 3 palabras sin tilde en el diccionario: 'credito' → 'crédito', 'Codigo' → 'Código' y "
            "'transaccion' → 'transacción'. " + _ACCION,
        )
        self.assertNotIn("@cCodTrx", hallazgos[0].mensaje)  # dónde está lo muestra «Ver en el código»

    def test_tablas_tambien(self):
        tabla = "CREATE TABLE dbo.Credito (nCreditoId INT NOT NULL);"
        dic = ("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Tabla de creditos del clienet', "
               "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Credito';\n"
               "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Codigo del credito', "
               "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Credito', "
               "@level2type=N'COLUMN', @level2name=N'nCreditoId';")
        hallazgos = [h for h in verificar_diccionario_tablas(tabla, dic) if h.regla == "ERROR_ORTOGRAFICO"]
        self.assertEqual(len(hallazgos), 1)
        self.assertTrue(hallazgos[0].mensaje.startswith(
            # «credito» de la columna no se marca: es parte del nombre de la tabla documentada (Credito).
            "Se identificaron 3 errores ortográficos en el diccionario: Sin tilde: 'creditos' → 'créditos' y "
            "'Codigo' → 'Código'; Mal escritas: 'clienet' → 'cliente'."))


if __name__ == "__main__":
    unittest.main()
