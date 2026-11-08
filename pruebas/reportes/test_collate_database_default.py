"""«Uso de COLLATE DATABASE_DEFAULT»: una sola observación con columnas y tablas, igual en Reportes y Negocio
(texto de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.collate_database_default import QUE_HACER_COLLATE_DATABASE_DEFAULT

MODULOS = (verificar_reporte, verificar_procedimiento_normal)
QUE_TOMA = "que toma la intercalación predeterminada de la base de datos donde se ejecuta la consulta."


def _database_default(sql, verificar=verificar_reporte):
    return [h for h in verificar(sql) if h.regla == "COLLATE_DATABASE_DEFAULT"]


class CollateDatabaseDefaultTest(unittest.TestCase):
    def test_texto_de_la_usuaria_con_columna_y_tabla(self):
        casos = {
            "CREATE TABLE #T (cCod VARCHAR(10) COLLATE DATABASE_DEFAULT)": "la columna cCod de la tabla #T",
            "DECLARE @T TABLE (cCod VARCHAR(10) collate database_default)": "la columna cCod de la tabla @T",
        }
        for sql, sobre in casos.items():
            for verificar in MODULOS:
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    hallazgos = _database_default(sql, verificar)
                    self.assertEqual(len(hallazgos), 1)
                    self.assertEqual(hallazgos[0].severidad.value, "alto")
                    self.assertEqual(
                        hallazgos[0].mensaje,
                        f"Se identificó el uso de COLLATE DATABASE_DEFAULT sobre {sobre}, {QUE_TOMA} "
                        + QUE_HACER_COLLATE_DATABASE_DEFAULT,
                    )

    def test_varias_columnas_en_una_sola_observacion(self):
        sql = ("CREATE TABLE #Tmp (\n nId INT,\n CCTACOD CHAR(18) NOT NULL COLLATE DATABASE_DEFAULT,\n"
               " cReprogCov VARCHAR(5) COLLATE DATABASE_DEFAULT)\n"
               "SELECT 1 FROM dbo.A a WITH(NOLOCK) INNER JOIN dbo.B b WITH(NOLOCK) ON a.cCod = b.cCod "
               "COLLATE DATABASE_DEFAULT")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _database_default(sql, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].lineas, [3, 4, 5])
                self.assertTrue(hallazgos[0].mensaje.startswith(
                    "Se identificó el uso de COLLATE DATABASE_DEFAULT sobre las columnas CCTACOD y cReprogCov de "
                    f"la tabla #Tmp y la columna cCod de la tabla dbo.B, {QUE_TOMA}"))

    def test_sin_columna_reconocible_queda_el_texto_general(self):
        hallazgo = _database_default("SELECT LTRIM(x.c) COLLATE DATABASE_DEFAULT FROM #X x")[0]
        self.assertEqual(hallazgo.mensaje,
                         f"Se identificó el uso de COLLATE DATABASE_DEFAULT, {QUE_TOMA} "
                         + QUE_HACER_COLLATE_DATABASE_DEFAULT)

    def test_en_el_join_tambien_se_observa_el_collate_en_la_condicion(self):
        sql = "SELECT 1 FROM A a WITH(NOLOCK) INNER JOIN B b WITH(NOLOCK) ON a.c COLLATE DATABASE_DEFAULT = b.c"
        reglas = {h.regla for h in verificar_reporte(sql)}
        self.assertTrue({"COLLATE_DATABASE_DEFAULT", "COLLATE_EN_PREDICADO"} <= reglas)

    def test_collate_de_la_empresa_u_openjson_no_se_observa(self):
        for sql in ("CREATE TABLE #T (cCod VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS)",
                    "SELECT x FROM OPENJSON(@cJson) WITH (cCod VARCHAR(10) COLLATE DATABASE_DEFAULT)"):
            for verificar in MODULOS:
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    self.assertEqual(_database_default(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
