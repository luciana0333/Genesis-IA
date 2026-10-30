"""Variables sin el prefijo de su tipo de dato (Reportes y Negocio): bajo, solo al crear el procedimiento."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

_MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _procedimiento(cuerpo: str, verbo: str = "CREATE") -> str:
    return f"{verbo} PROCEDURE dbo.PA_GDD_Cliente_Sel_Resumen (@nId INT)\nAS\nBEGIN\n{cuerpo}\nEND"


def _observaciones(sql: str, analizar):
    return [h for h in analizar(sql) if h.regla == "VARIABLE_SIN_PREFIJO_TIPO"]


class TestVariablesSinPrefijo(unittest.TestCase):
    def test_varias_variables_en_una_observacion(self):
        sql = _procedimiento("    DECLARE @Total INT = 0, @Nombre VARCHAR(20) = ''\n    SELECT @Total, @Nombre")
        for analizar in _MODULOS:
            with self.subTest(modulo=analizar.__name__):
                hallazgos = _observaciones(sql, analizar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "bajo")
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificaron 2 variables cuyos nombres no incluyen el prefijo correspondiente a su tipo de "
                    "dato: @Total (INT) → @nTotal; @Nombre (VARCHAR(20)) → @cNombre. Renombrar las variables según lo "
                    "indicado, utilizando el prefijo correspondiente a su tipo de dato (c para texto, n para número, "
                    "d para fecha u hora, b para bit y x para XML), a fin de mantener una nomenclatura uniforme y "
                    "facilitar su identificación.",
                )

    def test_una_variable_en_singular(self):
        sql = _procedimiento("    DECLARE @Fecha DATETIME = GETDATE()\n    SELECT @Fecha")
        mensaje = _observaciones(sql, verificar_reporte)[0].mensaje
        self.assertTrue(mensaje.startswith(
            "Se identificó una variable cuyo nombre no incluye el prefijo correspondiente a su tipo de dato: "
            "@Fecha (DATETIME) → @dFecha. Renombrar la variable según lo indicado"))

    def test_xml_empieza_con_x(self):
        sql = _procedimiento("    DECLARE @Datos XML, @xDocumento XML\n    SELECT @Datos, @xDocumento")
        for analizar in _MODULOS:
            with self.subTest(modulo=analizar.__name__):
                mensaje = _observaciones(sql, analizar)[0].mensaje
                self.assertIn("@Datos (XML) → @xDatos", mensaje)
                self.assertNotIn("@xDocumento", mensaje)

    def test_cada_tipo_con_su_letra(self):
        sql = _procedimiento(
            "    DECLARE @Monto DECIMAL(18,2) = ROUND(1.5, 2), @Activo BIT = 1, @Hora TIME, @Codigo CHAR(3)\n"
            "    SELECT @Monto, @Activo, @Hora, @Codigo")
        mensaje = _observaciones(sql, verificar_reporte)[0].mensaje
        for cambio in ("@Monto (DECIMAL(18,2)) → @nMonto", "@Activo (BIT) → @bActivo", "@Hora (TIME) → @dHora",
                       "@Codigo (CHAR(3)) → @cCodigo"):
            self.assertIn(cambio, mensaje)

    def test_prefijo_equivocado_se_reemplaza(self):
        sql = _procedimiento("    DECLARE @pnTipo INT, @cMonto INT\n    SELECT @pnTipo, @cMonto")
        mensaje = _observaciones(sql, verificar_reporte)[0].mensaje
        self.assertIn("@pnTipo (INT) → @nTipo", mensaje)
        self.assertIn("@cMonto (INT) → @nMonto", mensaje)

    def test_bien_nombradas_no_se_observan(self):
        sql = _procedimiento(
            "    DECLARE @nTotal INT = 0, @cNombre VARCHAR(20), @dHoy DATE = GETDATE(), @bActivo BIT, @xDoc XML,\n"
            "            @jDatos NVARCHAR(MAX), @n1 INT\n    SELECT @nTotal, @cNombre, @dHoy, @bActivo, @xDoc, @jDatos, @n1")
        for analizar in _MODULOS:
            with self.subTest(modulo=analizar.__name__):
                self.assertEqual(_observaciones(sql, analizar), [])

    def test_tabla_cursor_y_uniqueidentifier_no_se_revisan(self):
        sql = _procedimiento(
            "    DECLARE @Datos TABLE (Id INT, Nombre VARCHAR(10))\n"
            "    DECLARE @Guid UNIQUEIDENTIFIER, @Cursor CURSOR\n"
            "    DECLARE curClientes CURSOR FOR SELECT 1\n"
            "    SELECT @Guid")
        for analizar in _MODULOS:
            with self.subTest(modulo=analizar.__name__):
                self.assertEqual(_observaciones(sql, analizar), [])

    def test_columnas_de_la_variable_de_tabla_no_cuentan_como_variables(self):
        sql = _procedimiento("    DECLARE @tDatos TABLE (Id INT, Nombre VARCHAR(10)), @Total INT\n    SELECT @Total")
        mensaje = _observaciones(sql, verificar_reporte)[0].mensaje
        self.assertIn("Se identificó una variable", mensaje)
        self.assertIn("@Total (INT) → @nTotal", mensaje)

    def test_case_en_el_valor_inicial_no_corta_la_lista(self):
        sql = _procedimiento(
            "    DECLARE @bFlag BIT = CASE WHEN 1 = 1 THEN 1 ELSE 0 END, @Total INT\n    SELECT @bFlag, @Total")
        self.assertIn("@Total (INT) → @nTotal", _observaciones(sql, verificar_reporte)[0].mensaje)

    def test_varios_declare_juntan_sus_lineas(self):
        sql = _procedimiento("    DECLARE @Total INT\n    SELECT 1\n    DECLARE @Nombre VARCHAR(5)\n    SELECT @Total, @Nombre")
        hallazgos = _observaciones(sql, verificar_reporte)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].lineas, [4, 6])

    def test_alter_no_se_revisa(self):
        sql = _procedimiento("    DECLARE @Total INT = 0\n    SELECT @Total", verbo="ALTER")
        for analizar in _MODULOS:
            with self.subTest(modulo=analizar.__name__):
                self.assertEqual(_observaciones(sql, analizar), [])

    def test_create_or_alter_cuenta_como_create(self):
        sql = _procedimiento("    DECLARE @Total INT = 0\n    SELECT @Total", verbo="CREATE OR ALTER")
        self.assertEqual(len(_observaciones(sql, verificar_reporte)), 1)

    def test_variable_comentada_no_se_revisa(self):
        sql = _procedimiento("    -- DECLARE @Total INT = 0\n    /* DECLARE @Nombre VARCHAR(5) */\n    SELECT 1")
        self.assertEqual(_observaciones(sql, verificar_reporte), [])

    def test_parametros_siguen_en_su_propia_observacion(self):
        sql = ("CREATE PROCEDURE dbo.PA_GDD_Cliente_Sel_Resumen (@pdFechaIni DATE)\nAS\nBEGIN\n"
               "    DECLARE @Total INT\n    SELECT @Total WHERE GETDATE() > @pdFechaIni\nEND")
        reglas = [h.regla for h in verificar_reporte(sql)]
        self.assertIn("PARAMETRO_SIN_PREFIJO_TIPO", reglas)
        self.assertIn("VARIABLE_SIN_PREFIJO_TIPO", reglas)


if __name__ == "__main__":
    unittest.main()
