"""COLLATE DATABASE_DEFAULT en Reportes: se pide el COLLATE de la empresa."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte


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
                self.assertTrue(hallazgos[0].mensaje.startswith(
                    "Se identificó el uso de COLLATE DATABASE_DEFAULT en la columna cCod, que toma el COLLATE de la base donde se ejecuta."))

    def test_nombra_cada_columna(self):
        sql = ("CREATE TABLE #A (\n nId INT,\n cCod CHAR(1) NOT NULL COLLATE DATABASE_DEFAULT,\n"
               " cNombre NVARCHAR(MAX) COLLATE DATABASE_DEFAULT)")
        hallazgo = _database_default(sql)[0]
        self.assertEqual(hallazgo.lineas, [3, 4])
        self.assertIn("en la columna cCod,", hallazgo.mensaje)
        self.assertIn("en la columna cNombre,", hallazgo.mensaje)
        join = "SELECT 1 FROM A a WITH(NOLOCK) INNER JOIN B b WITH(NOLOCK) ON a.cCod = b.cCod COLLATE DATABASE_DEFAULT"
        self.assertIn("en la columna b.cCod,", _database_default(join)[0].mensaje)

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
