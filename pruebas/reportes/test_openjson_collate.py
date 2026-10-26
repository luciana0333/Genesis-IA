"""COLLATE innecesario en el WITH de OPENJSON (Reportes y Procedimientos de negocio)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

CASO_DE_LA_USUARIA = """CREATE PROCEDURE dbo.PA_Tasa_Ins_Versionamiento
    @cJsonTasaVersionamiento NVARCHAR(MAX)
AS
BEGIN
    SELECT nTasaId, cSustento
    from openjson(@cJsonTasaVersionamiento)
    with (
        nTasaId int
        , cSustento varchar(200) collate SQL_Latin1_General_CP1_CI_AS
        , dFechaVigencia date
        , cDepartamentosAplicacion varchar(500) collate SQL_Latin1_General_CP1_CI_AS
        , nMoneda int
    )
END
"""

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _openjson(verificar, sql):
    return [h for h in verificar(sql) if h.regla == "OPENJSON_COLLATE_INNECESARIO"]


class TestCollateEnOpenjson(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _openjson(verificar, CASO_DE_LA_USUARIA)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "bajo")
                self.assertEqual(hallazgos[0].linea, 9)
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó el uso de COLLATE en las columnas cSustento y cDepartamentosAplicacion del bloque "
                    "OPENJSON. Se recomienda retirarlo, ya que las columnas definidas en el WITH de OPENJSON toman por "
                    "defecto el COLLATE de la base de datos y no es necesario indicarlo.",
                )

    def test_una_sola_columna(self):
        sql = "SELECT c FROM OPENJSON(@j) WITH (c VARCHAR(10) COLLATE Modern_Spanish_CI_AS '$.c', n INT)"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _openjson(verificar, sql)
                self.assertEqual(len(hallazgos), 1)
                self.assertIn("en la columna c del bloque OPENJSON", hallazgos[0].mensaje)

    def test_sin_collate_no_se_observa(self):
        sql = CASO_DE_LA_USUARIA.replace(" collate SQL_Latin1_General_CP1_CI_AS", "")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_openjson(verificar, sql), [])

    def test_collate_distinto_dentro_de_openjson_no_se_observa_dos_veces(self):
        sql = CASO_DE_LA_USUARIA.replace("collate SQL_Latin1_General_CP1_CI_AS", "collate Modern_Spanish_CI_AS", 1)
        reglas = [h.regla for h in verificar_procedimiento_normal(sql)]
        self.assertIn("OPENJSON_COLLATE_INNECESARIO", reglas)
        self.assertNotIn("COLLATE_DISTINTO_AL_ESTANDAR", reglas)

    def test_collate_en_una_temporal_no_es_esta_regla(self):
        sql = ("CREATE TABLE #T (cNombre VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS);\n"
               "SELECT t.cNombre FROM #T t;")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_openjson(verificar, sql), [])

    def test_openjson_sin_with_no_se_observa(self):
        sql = "SELECT [key], [value] FROM OPENJSON(@j) WHERE [value] COLLATE SQL_Latin1_General_CP1_CI_AS = 'x'"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_openjson(verificar, sql), [])


if __name__ == "__main__":
    unittest.main()
