"""«Uso de COLLATE DATABASE_DEFAULT»: el mismo texto de la usuaria en Reportes y Negocio (8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.collate_temporales import MENSAJE_COLLATE_DATABASE_DEFAULT

TEXTO_USUARIA = (
    "Se identificó el uso de COLLATE DATABASE_DEFAULT, que toma la intercalación predeterminada de la base de datos "
    "donde se ejecuta la consulta. Se recomienda utilizar el COLLATE correspondiente (SQL_Latin1_General_CP1_CI_AS), "
    "para evitar conflictos al comparar o combinar textos entre bases de datos con distintas intercalaciones."
)


def _database_default(sql):
    return [h for h in verificar_reporte(sql) if h.regla == "COLLATE_DATABASE_DEFAULT"]


class CollateDatabaseDefaultTest(unittest.TestCase):
    def test_en_tabla_temporal_y_variable_de_tabla(self):
        for sql in ("CREATE TABLE #T (cCod VARCHAR(10) COLLATE DATABASE_DEFAULT)",
                    "DECLARE @T TABLE (cCod VARCHAR(10) collate database_default)"):
            with self.subTest(sql=sql):
                hallazgos = _database_default(sql)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "alto")
                self.assertEqual(hallazgos[0].mensaje, TEXTO_USUARIA)

    def test_mismo_texto_en_reportes_y_negocio(self):
        self.assertEqual(MENSAJE_COLLATE_DATABASE_DEFAULT, TEXTO_USUARIA)
        sql = ("CREATE TABLE #A (\n nId INT,\n cCod CHAR(1) NOT NULL COLLATE DATABASE_DEFAULT,\n"
               " cNombre NVARCHAR(MAX) COLLATE DATABASE_DEFAULT)")
        for verificar in (verificar_reporte, verificar_procedimiento_normal):
            with self.subTest(modulo=verificar.__name__):
                hallazgo = [h for h in verificar(sql) if h.regla == "COLLATE_DATABASE_DEFAULT"][0]
                self.assertEqual(hallazgo.severidad.value, "alto")
                self.assertEqual(hallazgo.lineas, [3, 4])
                self.assertTrue(hallazgo.mensaje.endswith(TEXTO_USUARIA[TEXTO_USUARIA.index("que toma"):]))

    def test_en_el_join_tambien_se_observa_el_collate_en_la_condicion(self):
        sql = "SELECT 1 FROM A a WITH(NOLOCK) INNER JOIN B b WITH(NOLOCK) ON a.c COLLATE DATABASE_DEFAULT = b.c"
        reglas = {h.regla for h in verificar_reporte(sql)}
        self.assertTrue({"COLLATE_DATABASE_DEFAULT", "COLLATE_EN_PREDICADO"} <= reglas)

    def test_collate_de_la_empresa_u_openjson_no_se_observa(self):
        for sql in ("CREATE TABLE #T (cCod VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS)",
                    "SELECT x FROM OPENJSON(@cJson) WITH (cCod VARCHAR(10) COLLATE DATABASE_DEFAULT)"):
            with self.subTest(sql=sql):
                self.assertEqual(_database_default(sql), [])


if __name__ == "__main__":
    unittest.main()
