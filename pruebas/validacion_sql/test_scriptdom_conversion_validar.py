"""Comparación de una columna con un valor de otro tipo: se afirma solo si Genesis conoce el tipo (usuaria, 22 nov.).

En una tabla física Genesis solo ve el prefijo c del nombre; no sabe si de verdad es texto (en FluGenSol_InsPropuesta_SP,
#BienesAsegurados define cNumGarant BIGINT). Ahí la tarjeta pide validar el tipo con la consulta adjunta, comprobada en
SQL Server Express (22 nov.), en lugar de afirmar que SQL Server convierte la columna.
"""
import unittest

from app.analizadores.scriptdom import validar_estructura


def _conversion(sql):
    return [h for h in validar_estructura(sql) if h.regla.startswith("CONVERSION_PREVISIBLE")]


class ConversionSoloSiSeSabe(unittest.TestCase):
    def test_tabla_fisica_pide_validar_con_consulta(self):
        h = _conversion("DECLARE @g BIGINT = 1\nSELECT 1 FROM DBO.GarantDecJur WITH (NOLOCK) WHERE cNumGarant = @g")[0]
        self.assertEqual(h.regla, "CONVERSION_PREVISIBLE_VALIDAR")
        self.assertEqual(h.severidad.value, "bajo")
        self.assertEqual(h.mensaje,
                         "Se identificó la comparación de cNumGarant con @g (BIGINT). Se recomienda validar el tipo de "
                         "dato de la columna con la consulta adjunta: si es de texto, comparar con un valor del mismo "
                         "tipo (ej.: entre comillas o como VARCHAR), ya que SQL Server convertiría la columna en cada "
                         "fila y no podría usar su índice.")
        self.assertIn("TABLE_SCHEMA = 'DBO' AND TABLE_NAME = 'GarantDecJur' AND COLUMN_NAME IN ('cNumGarant')", h.consulta)
        self.assertIn("DATA_TYPE", h.consulta)

    def test_sin_alias_en_delete_update_y_exists_tambien_lleva_la_tabla(self):
        for sql in ("DECLARE @g BIGINT = 1\nDELETE FROM DBO.G WHERE cNumGarant = @g",
                    "DECLARE @g BIGINT = 1\nUPDATE DBO.G SET a = 1 WHERE cNumGarant = @g",
                    "DECLARE @g BIGINT = 1\nIF EXISTS (SELECT 1 FROM DBO.G WITH (NOLOCK) WHERE cNumGarant = @g) SELECT 1"):
            with self.subTest(sql):
                self.assertIn("TABLE_NAME = 'G'", _conversion(sql)[0].consulta)

    def test_columna_ambigua_no_menciona_consulta(self):
        h = _conversion("DECLARE @g BIGINT = 1\nSELECT 1 FROM dbo.A WITH (NOLOCK) INNER JOIN dbo.B WITH (NOLOCK) "
                        "ON A.x = B.x WHERE cNumGarant = @g")[0]
        self.assertEqual(h.regla, "CONVERSION_PREVISIBLE_VALIDAR")
        self.assertNotIn("consulta adjunta", h.mensaje)

    def test_temporal_con_tipo_conocido_se_afirma_o_no_se_observa(self):
        texto = _conversion("CREATE TABLE #B (cNumGarant VARCHAR(10))\nDECLARE @g BIGINT = 1\n"
                            "SELECT 1 FROM #B WHERE cNumGarant = @g")
        self.assertEqual([h.regla for h in texto], ["CONVERSION_PREVISIBLE"])
        self.assertIn("columna de texto", texto[0].mensaje)
        numero = _conversion("CREATE TABLE #B (cNumGarant BIGINT)\nDECLARE @g BIGINT = 1\n"
                             "SELECT 1 FROM #B WHERE cNumGarant = @g")
        self.assertEqual(numero, [])

    def test_varias_con_y_sin_tabla(self):
        h = _conversion("DECLARE @g BIGINT = 1\nSELECT 1 FROM dbo.PersID WITH (NOLOCK) WHERE cPersIDTpo = 1\n"
                        "SELECT 1 FROM dbo.G WITH (NOLOCK) WHERE cNumGarant = @g\n"
                        "SELECT 1 FROM dbo.G WITH (NOLOCK) WHERE cNumGarant = @g")[0]
        self.assertTrue(h.mensaje.startswith(
            "Se identificaron 3 comparaciones de columnas con valores de otro tipo: cPersIDTpo con 1 (número) y "
            "cNumGarant con @g (BIGINT, 2 veces). Se recomienda validar el tipo de dato de estas columnas con la "
            "consulta adjunta"), h.mensaje)


if __name__ == "__main__":
    unittest.main()
