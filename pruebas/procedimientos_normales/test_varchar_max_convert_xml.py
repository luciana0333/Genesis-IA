"""VARCHAR(MAX) en un CONVERT/CAST que pasa a texto un XML, JSON o HTML (Reportes y Negocio): se justifica."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

_MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _varchar_max(cuerpo: str, parametros: str = "@nId INT"):
    sql = f"CREATE PROCEDURE dbo.PA_GDD_Calendario_Sel_Datos ({parametros})\nAS\nBEGIN\n{cuerpo}\nEND"
    return {analizar.__name__: [h for h in analizar(sql) if h.regla == "VARCHAR_MAX_PROHIBIDO"] for analizar in _MODULOS}


class TestNoSeObserva(unittest.TestCase):
    def _sin_observaciones(self, cuerpo, parametros="@nId INT"):
        for modulo, casos in _varchar_max(cuerpo, parametros).items():
            with self.subTest(modulo=modulo):
                self.assertEqual(casos, [])

    def test_caso_de_la_usuaria(self):
        self._sin_observaciones(
            "    DECLARE @cXmltCalendario varchar(max) =  CONVERT(VARCHAR(MAX),(@cXml2) )\n\n"
            "    DECLARE @cXmlt varchar(max) =  CONVERT(VARCHAR(MAX),(@Xml) )\n"
            "    SELECT @cXmltCalendario, @cXmlt",
            parametros="@cXml2 XML, @Xml XML")

    def test_variable_declarada_como_xml_aunque_su_nombre_no_lo_diga(self):
        self._sin_observaciones(
            "    DECLARE @xDatos XML = '<a/>'\n    SELECT CAST(@xDatos AS VARCHAR(MAX))")
        self._sin_observaciones("    SELECT CONVERT(NVARCHAR(MAX), @pDoc)", parametros="@pDoc AS XML")

    def test_nombre_con_json_o_html(self):
        self._sin_observaciones("    SELECT CONVERT(VARCHAR(MAX), @cJsonEntrada)", parametros="@cJsonEntrada NVARCHAR(4000)")
        self._sin_observaciones("    SELECT CAST(@cHtmlCuerpo AS NVARCHAR(MAX))", parametros="@cHtmlCuerpo NVARCHAR(4000)")

    def test_prefijo_j_es_json(self):
        # Igual que la regla de prefijos: @jData en (N)VARCHAR(MAX) es un JSON.
        self._sin_observaciones("    SELECT 1", parametros="@jData NVARCHAR(MAX), @jDetalle VARCHAR(MAX)")
        self._sin_observaciones("    DECLARE @jRespuesta NVARCHAR(MAX) = ''\n    SELECT @jRespuesta")

    def test_try_convert_y_parentesis_anidados(self):
        self._sin_observaciones("    SELECT TRY_CONVERT(VARCHAR(MAX), ((@xDoc)))", parametros="@xDoc XML")


class TestSiSeObserva(unittest.TestCase):
    def _una_observacion(self, cuerpo, parametros="@nId INT"):
        for modulo, casos in _varchar_max(cuerpo, parametros).items():
            with self.subTest(modulo=modulo):
                self.assertEqual(len(casos), 1)

    def test_convert_de_un_texto_comun(self):
        self._una_observacion("    SELECT CONVERT(VARCHAR(MAX), @cTexto)", parametros="@cTexto VARCHAR(100)")

    def test_cast_de_una_columna(self):
        self._una_observacion("    SELECT CAST(c.cNombre AS VARCHAR(MAX)) FROM dbo.Cliente c WITH (NOLOCK)")

    def test_variable_xml_fuera_del_convert_no_lo_excusa(self):
        # @xDoc es XML, pero el CONVERT convierte otra variable (texto común).
        self._una_observacion(
            "    DECLARE @xDoc XML\n    SELECT @xDoc, CONVERT(VARCHAR(MAX), @cTexto)",
            parametros="@cTexto VARCHAR(100)")

    def test_palabra_que_empieza_con_j_minuscula_no_es_json(self):
        # «@jerarquia» no es el prefijo j (después de la j viene minúscula).
        self._una_observacion("    DECLARE @jerarquia VARCHAR(MAX) = ''\n    SELECT @jerarquia")

    def test_cuerpo_de_correo_sin_html_sigue_observandose(self):
        self._una_observacion("    SELECT @cCuerpo", parametros="@cCuerpo NVARCHAR(MAX) = '' OUTPUT")

    def test_variable_comun_sigue_observandose(self):
        self._una_observacion("    DECLARE @cTexto VARCHAR(MAX) = 'hola'\n    SELECT @cTexto")


if __name__ == "__main__":
    unittest.main()
