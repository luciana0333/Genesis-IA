"""Tablas: «Uso de VARCHAR(MAX)» en columnas nuevas (título y texto de la usuaria, 11 nov.)."""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla

REGLA = "COLUMNA_VARCHAR_MAX"

# Caso de la usuaria.
_LOG = """CREATE TABLE CONTABILIDAD.LogReprocesoDevengado
(
	nLogReprocesoDevengadoId	INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
	dFechaProceso				DATE NOT NULL DEFAULT ('1900-01-01'),
	cEstado						VARCHAR(20) NOT NULL DEFAULT ('EN PROCESO'),
	cDetalle					VARCHAR(MAX) NOT NULL DEFAULT (''),
	cUltimaActualizacion		VARCHAR(25) NOT NULL DEFAULT ('')
)
GO
"""


def _max(sql, es_dbcmaica=True):
    return [h for h in verificar_tabla(sql, es_dbcmaica) if h.regla == REGLA]


class ColumnaVarcharMaxTest(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        for es_dbcmaica in (True, False):
            with self.subTest(es_dbcmaica=es_dbcmaica):
                hallazgos = _max(_LOG, es_dbcmaica)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
                self.assertEqual(hallazgos[0].linea, 6)
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó que la columna cDetalle de la tabla CONTABILIDAD.LogReprocesoDevengado está "
                    "definida como VARCHAR(MAX). Se recomienda evaluar la asignación de una longitud definida (por "
                    "ejemplo, VARCHAR(500)), reservando VARCHAR(MAX) para campos que almacenen contenido extenso, "
                    "como JSON, XML o HTML.",
                )

    def test_varias_columnas_en_una_observacion(self):
        sql = ("CREATE TABLE dbo.Nota (\n nNotaId INT IDENTITY(1,1) NOT NULL,\n cDetalle VARCHAR(MAX) NOT NULL,\n"
               " cObservacion NVARCHAR(MAX) NOT NULL,\n CONSTRAINT PK_Nota PRIMARY KEY CLUSTERED (nNotaId)\n)")
        hallazgo = _max(sql)[0]
        self.assertEqual(hallazgo.lineas, [3, 4])
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificó que las columnas cDetalle y cObservacion de la tabla dbo.Nota están definidas como "
            "(N)VARCHAR(MAX). Se recomienda evaluar la asignación de una longitud definida en cada una (por ejemplo, "
            "VARCHAR(500)), reservando VARCHAR(MAX)"))

    def test_columna_nueva_en_un_alter(self):
        sql = "ALTER TABLE dbo.Nota ADD cComentario VARCHAR(MAX) NULL"
        self.assertIn("Se identificó que la columna cComentario de la tabla dbo.Nota está definida como VARCHAR(MAX).",
                      _max(sql)[0].mensaje)

    def test_varias_tablas_en_el_script(self):
        otra = ("CREATE TABLE dbo.Nota (\n nNotaId INT IDENTITY(1,1) NOT NULL,\n cObservacion VARCHAR(MAX) NOT NULL,\n"
                " CONSTRAINT PK_Nota PRIMARY KEY CLUSTERED (nNotaId)\n)\nGO\n")
        hallazgos = _max(_LOG + otra)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificaron dos tablas con columnas definidas como (N)VARCHAR(MAX): cDetalle "
            "(CONTABILIDAD.LogReprocesoDevengado); cObservacion (dbo.Nota). Se recomienda evaluar la asignación de "
            "una longitud definida en cada una (por ejemplo, VARCHAR(500)), reservando VARCHAR(MAX) para campos que "
            "almacenen contenido extenso, como JSON, XML o HTML.",
        )

    def test_lo_que_no_se_marca(self):
        for columna in ("cJsonDetalle VARCHAR(MAX) NOT NULL",     # guarda JSON
                        "jDetalle NVARCHAR(MAX) NOT NULL",        # prefijo de JSON
                        "cXmlTrama VARCHAR(MAX) NOT NULL",        # guarda XML
                        "cCuerpoHtml VARCHAR(MAX) NOT NULL",      # guarda HTML
                        "cDetalle VARCHAR(4000) NOT NULL",        # longitud definida
                        "xDatos XML NOT NULL"):                   # tipo XML
            with self.subTest(columna=columna):
                sql = (f"CREATE TABLE dbo.Nota (\n nNotaId INT IDENTITY(1,1) NOT NULL,\n {columna},\n"
                       f" CONSTRAINT PK_Nota PRIMARY KEY CLUSTERED (nNotaId)\n)")
                self.assertEqual(_max(sql), [])


if __name__ == "__main__":
    unittest.main()
