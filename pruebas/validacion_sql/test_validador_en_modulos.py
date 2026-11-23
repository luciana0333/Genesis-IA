"""Validador SQL Server dentro de cada módulo (usuaria, 22 nov.: pestañas «Buenas prácticas» y «Validador SQL Server»).

Procedimientos y Reportes llevan todo el validador; Tablas y Diccionarios solo lo crítico (lo que haría fallar el
script). Cada cajita se valida aparte y la observación dice en qué cajita está. Lo que ya dice una buena práctica de la
Caja no se repite.
"""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM
from app.analizadores.validador_en_modulos import validar_para_modulo
from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")

PROCEDIMIENTO = """CREATE PROCEDURE dbo.PA_Cliente_Sel_Resumen
    @nClienteId INT
AS
BEGIN
    DECLARE @nTotal MONEY = 0
    SELECT TOP 1 c.cNombre FROM dbo.Cliente c WITH (NOLOCK) WHERE c.nClienteId = @nClienteId
    SELECT 100 / @nTotal
END"""


def _reglas(resultado):
    return [h.regla for h in resultado["hallazgos"]]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class ValidadorEnModulos(unittest.TestCase):
    def test_procedimientos_y_reportes_llevan_todo_el_validador(self):
        for tipo in ("procedimiento_normal", "reporte"):
            with self.subTest(tipo):
                resultado = validar_para_modulo(tipo, PROCEDIMIENTO)
                self.assertEqual(resultado["alcance"], "completo")
                self.assertIn("TOP_SIN_ORDER_BY", _reglas(resultado))
                self.assertIn("DIVISION_SIN_NULLIF", _reglas(resultado))

    def test_tablas_y_diccionarios_solo_lo_critico(self):
        for tipo in ("tabla_estructura", "tabla", "procedimiento", "funcion"):
            with self.subTest(tipo):
                resultado = validar_para_modulo(tipo, PROCEDIMIENTO)
                self.assertEqual(resultado["alcance"], "estructura")
                self.assertEqual(resultado["hallazgos"], [])

    def test_error_de_sintaxis_sale_en_todos_los_modulos(self):
        roto = "CREATE TABLE dbo.Cliente (nClienteId INT,, cNombre VARCHAR(50))"
        for tipo in ("procedimiento_normal", "reporte", "tabla_estructura", "tabla", "procedimiento", "funcion"):
            with self.subTest(tipo):
                resultado = validar_para_modulo(tipo, roto)
                self.assertEqual(_reglas(resultado), ["ERROR_SINTAXIS"])
                self.assertIsNone(getattr(resultado["hallazgos"][0], "seccion", None))

    def test_cada_cajita_se_valida_aparte_y_dice_su_seccion(self):
        tabla = "CREATE TABLE dbo.Cliente (nClienteId INT, cNombre VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS)"
        indices = "CREATE NONCLUSTERED INDEX IXN_Cliente_cNombre ON dbo.Cliente (cNombre,)"
        resultado = validar_para_modulo("tabla_estructura", tabla, indices=indices)
        self.assertEqual([(h.regla, getattr(h, "seccion", None)) for h in resultado["hallazgos"]],
                         [("ERROR_SINTAXIS", "indices")])

        diccionario = "EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Clientes' ,,"
        resultado = validar_para_modulo("tabla", tabla, diccionario=diccionario)
        self.assertEqual([getattr(h, "seccion", None) for h in resultado["hallazgos"]], ["diccionario"])

    def test_cajitas_que_no_corresponden_no_se_validan(self):
        roto = "SELECT ,, 1"
        # El diccionario no existe en Procedimientos ni los índices en Diccionarios: no se leen.
        self.assertEqual(validar_para_modulo("procedimiento_normal", "SELECT 1", diccionario=roto, indices=roto)["hallazgos"], [])
        self.assertEqual(validar_para_modulo("tabla", "SELECT 1", indices=roto)["hallazgos"], [])

    def test_lo_que_ya_dice_la_caja_no_se_repite(self):
        sql = ("CREATE PROCEDURE dbo.PA_X @pcCod VARCHAR(20) AS\n"
               "DECLARE @s NVARCHAR(500) = 'SELECT * FROM dbo.T WHERE c = ''' + @pcCod + ''''\nEXEC (@s)")
        sin_caja = validar_para_modulo("procedimiento_normal", sql)
        self.assertIn("SQL_DINAMICO_CONCATENA_PARAMETRO", _reglas(sin_caja))
        caja = [Hallazgo(3, OrigenAnalisis.REGLAS_ESTATICAS, Severidad.ALTO, "SQL_DINAMICO_PROHIBIDO", "x")]
        con_caja = validar_para_modulo("procedimiento_normal", sql, buenas_practicas=caja)
        self.assertNotIn("SQL_DINAMICO_CONCATENA_PARAMETRO", _reglas(con_caja))

    def test_con_las_reglas_reales_el_sql_dinamico_sale_una_sola_vez(self):
        from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
        from app.analizadores.analizador_reportes import verificar_reporte
        sql = ("CREATE PROCEDURE dbo.PA_X @pcCod VARCHAR(20) AS\n"
               "DECLARE @s NVARCHAR(500) = 'SELECT * FROM dbo.T WHERE c = ''' + @pcCod + ''''\nEXEC (@s)")
        for tipo, verificar in (("procedimiento_normal", verificar_procedimiento_normal), ("reporte", verificar_reporte)):
            with self.subTest(tipo):
                caja = verificar(sql)
                self.assertIn("SQL_DINAMICO_PROHIBIDO", [h.regla for h in caja])
                self.assertNotIn("SQL_DINAMICO_CONCATENA_PARAMETRO", _reglas(validar_para_modulo(tipo, sql, buenas_practicas=caja)))

    def test_tipo_sin_validador(self):
        self.assertIsNone(validar_para_modulo("otro", PROCEDIMIENTO))


class SinScriptDom(unittest.TestCase):
    def test_avisa_y_no_falla(self):
        import app.analizadores.validador_en_modulos as modulo
        original = modulo.validar_estructura
        modulo.validar_estructura = lambda _sql: None
        try:
            resultado = validar_para_modulo("procedimiento_normal", PROCEDIMIENTO)
        finally:
            modulo.validar_estructura = original
        self.assertFalse(resultado["disponible"])
        self.assertTrue(resultado["motivo"])


if __name__ == "__main__":
    unittest.main()
