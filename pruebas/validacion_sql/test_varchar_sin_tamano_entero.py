"""VARCHAR sin tamaño al convertir un número entero (usuaria, 23 nov.).

Caso real PA_LogConciliacionVisaDetSwitchDumpLog_Ins_Grabar: CAST(@NumSecuencia AS VARCHAR) con @NumSecuencia INT.
Un entero no pasa de 20 caracteres (BIGINT con signo), así que nunca se corta a 30: baja a severidad baja. Solo si es
seguro un entero (variable o parámetro INT/BIGINT/SMALLINT/TINYINT, o un entero escrito); si hay duda, sigue en alto.
"""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")


def _varchar(sql):
    return [(h.regla, h.severidad.value) for h in validar_estructura(sql) if h.regla.startswith("VARCHAR_SIN_TAMANO")]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class VarcharSinTamanoEntero(unittest.TestCase):
    def test_enteros_seguros_bajan_a_bajo(self):
        casos = {
            "caso real": "DECLARE @n INT = 1\nSELECT RIGHT('000000' + CAST(@n AS VARCHAR), 6)",
            "parámetro BIGINT con CONVERT": "CREATE PROCEDURE dbo.PA_X @n BIGINT AS SELECT CONVERT(VARCHAR, @n)",
            "TINYINT entre paréntesis a NVARCHAR": "DECLARE @t TINYINT = 1\nSELECT CAST((@t) AS NVARCHAR)",
            "SMALLINT con TRY_CAST": "DECLARE @s SMALLINT = 1\nSELECT TRY_CAST(@s AS VARCHAR)",
            "entero escrito": "SELECT CAST(-15 AS VARCHAR)",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_varchar(sql), [("VARCHAR_SIN_TAMANO_ENTERO", "bajo")])

    def test_si_hay_duda_sigue_en_alto(self):
        casos = {
            "texto": "DECLARE @c VARCHAR(100) = 'x'\nSELECT CAST(@c AS VARCHAR)",
            "decimal": "DECLARE @m DECIMAL(18,2) = 1\nSELECT CAST(@m AS VARCHAR)",
            "columna (tipo desconocido)": "SELECT CAST(a.nId AS VARCHAR) FROM dbo.T a WITH (NOLOCK)",
            "expresión con un entero": "DECLARE @n INT = 1\nSELECT CAST(@n * 2 AS VARCHAR)",
            "al declarar": "DECLARE @v VARCHAR = 'x'",
            "CHAR": "DECLARE @n INT = 1\nSELECT CAST(@n AS CHAR)",
            "variable sin declarar": "SELECT CAST(@zz AS VARCHAR)",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_varchar(sql), [("VARCHAR_SIN_TAMANO", "alto")])

    def test_mensajes(self):
        uno = [h for h in validar_estructura("DECLARE @n INT = 1\nSELECT CAST(@n AS VARCHAR)")
               if h.regla == "VARCHAR_SIN_TAMANO_ENTERO"][0]
        self.assertEqual(uno.mensaje, "Se identificó la conversión de @n (INT) a VARCHAR sin especificar el tamaño. Se "
                                      "recomienda especificar el tamaño, por ejemplo, VARCHAR(11), a fin de definir "
                                      "explícitamente la longitud del resultado.")
        dos = [h for h in validar_estructura("DECLARE @a INT = 1, @b BIGINT = 2\nSELECT CAST(@a AS VARCHAR), "
                                             "CAST(@b AS VARCHAR)") if h.regla == "VARCHAR_SIN_TAMANO_ENTERO"][0]
        self.assertIn("2 conversiones de números enteros a VARCHAR sin especificar el tamaño: @a (INT) y @b (BIGINT)",
                      dos.mensaje)
        self.assertIn("VARCHAR(20)", dos.mensaje)

    def test_entero_y_texto_en_el_mismo_codigo(self):
        sql = "DECLARE @n INT = 1, @c VARCHAR(100) = 'x'\nSELECT CAST(@n AS VARCHAR), CAST(@c AS VARCHAR)"
        self.assertEqual(sorted(_varchar(sql)), [("VARCHAR_SIN_TAMANO", "alto"), ("VARCHAR_SIN_TAMANO_ENTERO", "bajo")])


if __name__ == "__main__":
    unittest.main()
