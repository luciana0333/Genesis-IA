"""En Diccionarios se pega solo la firma del procedimiento o función (usuaria, 23 nov.).

Caso real: «ALTER PROCEDURE DBO.PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral( @dFechaInicio DATETIME, … )» sin
el AS. El validador decía «Fin de archivo inesperado»: falso positivo, porque solo se valida la firma.
"""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM
from app.analizadores.validador_en_modulos import _partes_a_validar, validar_para_modulo

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")

FIRMA_REAL = ("ALTER PROCEDURE DBO.PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral(\n"
              "\t@dFechaInicio DATETIME,\n\t@dFechaFin DATETIME,\n\t@cTiendas VARCHAR(1000),\n"
              "\t@nFiltroCreditos INT\n\t)\n")


def _sintaxis(tipo, sql):
    resultado = validar_para_modulo(tipo, sql)
    return [h for h in resultado["hallazgos"] if h.regla == "ERROR_SINTAXIS"]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class FirmaSolaEnDiccionario(unittest.TestCase):
    def test_firmas_correctas_no_se_marcan(self):
        casos = {
            ("procedimiento", "caso real"): FIRMA_REAL,
            ("procedimiento", "sin paréntesis"): "CREATE PROCEDURE dbo.PA_X @a INT, @b VARCHAR(10) = 'AS'",
            ("procedimiento", "sin parámetros"): "CREATE PROC dbo.PA_X",
            ("procedimiento", "con WITH RECOMPILE"): "CREATE PROCEDURE dbo.PA_X @a INT WITH RECOMPILE",
            ("procedimiento", "con comentario al final"): FIRMA_REAL + "-- AS fin\n",
            ("funcion", "escalar"): "CREATE FUNCTION dbo.fn_X (@a INT) RETURNS VARCHAR(10)",
            ("funcion", "de tabla"): "CREATE FUNCTION dbo.fn_X (@a INT) RETURNS TABLE",
            ("funcion", "de tabla con variable"): "CREATE FUNCTION dbo.fn_X (@a INT) RETURNS @t TABLE (c INT)",
            ("funcion", "sin RETURNS"): "CREATE FUNCTION dbo.fn_X (@a INT)",
        }
        for (tipo, nombre), sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_sintaxis(tipo, sql), [])

    def test_errores_de_la_firma_se_siguen_marcando(self):
        casos = {
            "falta una coma": "ALTER PROCEDURE dbo.PA_X(\n\t@a INT\n\t@b INT\n\t)",
            "falta cerrar el paréntesis": "ALTER PROCEDURE dbo.PA_X(\n\t@a INT,\n\t@b INT",
            "tipo con paréntesis abierto": "ALTER PROCEDURE dbo.PA_X(\n\t@a VARCHAR(10,\n\t@b INT\n\t)",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                errores = _sintaxis("procedimiento", sql)
                self.assertTrue(errores)
                # La línea nunca pasa de lo que pegó la usuaria.
                self.assertLessEqual(errores[0].linea, len(sql.splitlines()))

    def test_el_mensaje_habla_de_lo_pegado_y_no_del_cuerpo_agregado(self):
        errores = _sintaxis("procedimiento", "ALTER PROCEDURE dbo.PA_X(\n\t@a INT,\n\t@b INT")
        self.assertIn("sin cerrar un paréntesis", errores[0].mensaje)
        self.assertNotIn("'AS'", errores[0].mensaje)

    def test_varias_firmas_juntas(self):
        firmas = ("CREATE PROCEDURE dbo.PA_A\n(\n\t@a INT\n)\n\n"
                  "CREATE PROCEDURE dbo.PA_B\n(\n\t-- obligatorios\n\t@b INT,\n\t@c VARCHAR(10) OUT\n)\n"
                  "CREATE FUNCTION dbo.fn_C (@d INT) RETURNS TABLE\n")
        self.assertEqual(_sintaxis("procedimiento", firmas), [])

    def test_varias_firmas_con_error_en_la_del_medio(self):
        firmas = ("CREATE PROCEDURE dbo.PA_A\n(\n\t@a INT\n)\n"
                  "CREATE PROCEDURE dbo.PA_B\n(\n\t@b INT\n\t@c INT\n)\n"
                  "CREATE PROCEDURE dbo.PA_C\n(\n\t@d INT\n)\n")
        self.assertEqual([h.linea for h in _sintaxis("procedimiento", firmas)], [8])

    def test_procedimiento_completo_queda_igual(self):
        sql = "CREATE PROCEDURE dbo.PA_X @a INT\nAS\nBEGIN\nSELECT @a\nEND"
        self.assertEqual(_partes_a_validar("procedimiento", sql), [(sql, sql, None)])
        self.assertEqual(_sintaxis("procedimiento", sql), [])

    def test_procedimiento_completo_con_error_se_sigue_marcando(self):
        self.assertTrue(_sintaxis("procedimiento", "CREATE PROCEDURE dbo.PA_X @a INT\nAS\nBEGIN\nSELECT @a\n"))

    def test_otros_modulos_no_cambian(self):
        self.assertTrue(_sintaxis("procedimiento_normal", FIRMA_REAL))
        self.assertTrue(_sintaxis("reporte", FIRMA_REAL))
        self.assertEqual(len(_partes_a_validar("tabla", "CREATE TABLE dbo.T (a INT")), 1)


if __name__ == "__main__":
    unittest.main()
