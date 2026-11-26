"""Diccionario de una función que documenta las columnas que devuelve (usuaria, 25 nov., FN_Reprog956_Percibido):
no es «parámetro que no existe» (SQL Server lo acepta); según el estándar solo se documentan la función y sus
parámetros, así que se recomienda retirarla, en bajo."""
import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario

FUNCION = """CREATE FUNCTION Contabilidad.FN_Prueba
(
    @dFecha DATE
)
RETURNS TABLE
AS
RETURN (SELECT CAST('1' AS VARCHAR(18)) AS cCtaCod, CONVERT(VARCHAR(8), @dFecha, 112) AS cDesde)"""


def _dic(*extra):
    base = ["EXEC sp_addextendedproperty N'MS_Description', N'Funcion de prueba que devuelve creditos.', "
            "N'SCHEMA', N'Contabilidad', N'FUNCTION', N'FN_Prueba'",
            "EXEC sp_addextendedproperty N'MS_Description', N'Fecha de proceso.', N'SCHEMA', N'Contabilidad', "
            "N'FUNCTION', N'FN_Prueba', N'PARAMETER', N'@dFecha'"]
    return "\n".join(base + list(extra))


class ColumnasDeFuncion(unittest.TestCase):
    def test_columnas_documentadas_se_recomienda_retirarlas(self):
        hallazgos = verificar_diccionario(FUNCION, _dic(
            "EXEC sp_addextendedproperty N'MS_Description', N'Codigo del credito.', N'SCHEMA', N'Contabilidad', "
            "N'FUNCTION', N'FN_Prueba', N'COLUMN', N'cCtaCod'",
            "EXEC sp_addextendedproperty N'MS_Description', N'Fecha desde.', N'SCHEMA', N'Contabilidad', "
            "N'FUNCTION', N'FN_Prueba', N'COLUMN', N'cDesde'"), "funcion")
        self.assertEqual([h.regla for h in hallazgos], ["DOCUMENTACION_COLUMNAS_FUNCION"])
        self.assertEqual(hallazgos[0].severidad.value.lower(), "bajo")
        self.assertEqual(hallazgos[0].mensaje,
                         "Se identificó documentación de las columnas devueltas por la función (cCtaCod, cDesde). "
                         "Se recomienda retirarla, ya que, según el estándar, solo se documentan la función y sus "
                         "parámetros.")

    def test_solo_funcion_y_parametros_no_se_marca(self):
        self.assertEqual(verificar_diccionario(FUNCION, _dic(), "funcion"), [])

    def test_parametro_inexistente_se_sigue_marcando(self):
        hallazgos = verificar_diccionario(FUNCION, _dic(
            "EXEC sp_addextendedproperty N'MS_Description', N'Otro.', N'SCHEMA', N'Contabilidad', "
            "N'FUNCTION', N'FN_Prueba', N'PARAMETER', N'@nOtro'"), "funcion")
        self.assertIn("PARAMETRO_NO_EXISTE", [h.regla for h in hallazgos])


if __name__ == "__main__":
    unittest.main()
