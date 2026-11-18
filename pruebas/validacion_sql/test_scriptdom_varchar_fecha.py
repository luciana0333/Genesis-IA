"""VARCHAR sin tamaño al convertir fechas (usuaria, 18 nov.).

CONVERT(VARCHAR, fecha, 103) siempre da 10 caracteres: no se corta, así que va aparte y en nivel bajo, con el texto
de la usuaria. Los largos de cada formato se midieron en SQL Server con DATETIME, DATETIME2(7), DATETIMEOFFSET(7),
DATE, TIME(7) y SMALLDATETIME: los formatos que pasan de 30 (121, 109…) sí se cortan y siguen en «VARCHAR sin tamaño».
"""

import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura
from app.analizadores.scriptdom_mensajes import LARGO_POR_FORMATO_DE_FECHA

HAY_SCRIPTDOM = LECTOR_SCRIPTDOM.estado().get("disponible", False) and LECTOR_SCRIPTDOM.estado().get("revisor", False)


def _varchar(sql):
    return [h for h in validar_estructura(sql) if h.regla.startswith("VARCHAR_SIN_TAMANO")]


class LargosTest(unittest.TestCase):
    def test_ningun_formato_corto_pasa_de_30(self):
        self.assertTrue(all(largo <= 30 for largo in LARGO_POR_FORMATO_DE_FECHA.values()))
        # Los que sirven también para números (0-3, 126) y los que pasan de 30 no están.
        for estilo in (0, 1, 2, 3, 9, 13, 21, 25, 109, 113, 121, 126, 130, 131):
            self.assertNotIn(estilo, LARGO_POR_FORMATO_DE_FECHA)


@unittest.skipUnless(HAY_SCRIPTDOM, "ScriptDom no está en esta PC (viene con SSMS)")
class VarcharFechaTest(unittest.TestCase):
    def test_un_caso_con_el_texto_de_la_usuaria(self):
        hallazgos = _varchar("SELECT CONVERT(VARCHAR, N.dtRegistro, 103) AS cFecha FROM dbo.NetConciliaciones N")
        self.assertEqual([(h.regla, h.severidad.value) for h in hallazgos], [("VARCHAR_SIN_TAMANO_FECHA", "bajo")])
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificó un caso de CONVERT(VARCHAR, ..., 103) sin especificar el tamaño del tipo de dato. "
            "Se recomienda especificar el tamaño de VARCHAR según el formato de fecha utilizado, por ejemplo, "
            "VARCHAR(10) para el formato 103, a fin de definir explícitamente la longitud del resultado.",
        )

    def test_tres_casos_en_una_frase_y_lineas_aparte(self):
        sql = ("SELECT CONVERT(VARCHAR, N.dtRegistro, 103),\n       CONVERT(VARCHAR, O.dtRegistro, 103),\n"
               "       CONVERT(VARCHAR, P.dtRegistro, 103)\nFROM dbo.A N, dbo.B O, dbo.C P")
        hallazgo = _varchar(sql)[0]
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificaron 3 casos de CONVERT(VARCHAR, ..., 103) sin especificar el tamaño del tipo de dato. "))
        self.assertNotIn("línea", hallazgo.mensaje)  # las líneas van arriba, en la tarjeta
        self.assertEqual(hallazgo.lineas, [1, 2, 3])

    def test_formatos_distintos_se_nombran_una_vez(self):
        sql = "SELECT CONVERT(VARCHAR, GETDATE(), 103), CONVERT(VARCHAR, GETDATE(), 103), CONVERT(NVARCHAR, GETDATE(), 112)"
        self.assertIn("3 casos de CONVERT(VARCHAR, ..., 103) y CONVERT(NVARCHAR, ..., 112) sin especificar",
                      _varchar(sql)[0].mensaje)

    def test_sigue_en_alto_lo_que_si_se_puede_cortar(self):
        for sql in ("SELECT CAST(@cTexto AS VARCHAR)",                  # sin formato
                    "SELECT CONVERT(VARCHAR, @cTexto)",
                    "SELECT CONVERT(VARCHAR, SYSDATETIMEOFFSET(), 121)",  # 121 llega a 34 caracteres
                    "SELECT CONVERT(VARCHAR, @nMonto, 1)",              # formato que también es de números
                    "SELECT CONVERT(VARCHAR, GETDATE(), @nFormato)",    # formato en variable: no se sabe cuál es
                    "DECLARE @c VARCHAR = 'x'"):                        # al declarar
            with self.subTest(sql=sql):
                self.assertEqual([(h.regla, h.severidad.value) for h in _varchar(sql)], [("VARCHAR_SIN_TAMANO", "alto")])

    def test_con_tamano_no_se_marca(self):
        self.assertEqual(_varchar("SELECT CONVERT(VARCHAR(10), GETDATE(), 103), CONVERT(VARCHAR(19), GETDATE(), 120)"), [])


if __name__ == "__main__":
    unittest.main()
