"""Tablas: «Columna VARCHAR(MAX) en tabla nueva» (texto de la usuaria, 11 nov.)."""

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
                    "Se identificó la columna cDetalle definida como VARCHAR(MAX) en la tabla nueva "
                    "CONTABILIDAD.LogReprocesoDevengado. Se recomienda validar si es posible asignarle una longitud "
                    "definida (ej.: VARCHAR(500)), ya que VARCHAR(MAX) solo se justifica para JSON, XML, HTML o "
                    "textos de gran tamaño.",
                )

    def test_varias_columnas_en_una_observacion(self):
        sql = ("CREATE TABLE dbo.Nota (\n nNotaId INT IDENTITY(1,1) NOT NULL,\n cDetalle VARCHAR(MAX) NOT NULL,\n"
               " cObservacion NVARCHAR(MAX) NOT NULL,\n CONSTRAINT PK_Nota PRIMARY KEY CLUSTERED (nNotaId)\n)")
        hallazgo = _max(sql)[0]
        self.assertEqual(hallazgo.lineas, [3, 4])
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificaron las columnas cDetalle y cObservacion definidas como (N)VARCHAR(MAX) en la tabla nueva "
            "dbo.Nota. Se recomienda validar si es posible asignarles una longitud definida (ej.: VARCHAR(500))"))

    def test_columna_nueva_en_un_alter(self):
        sql = "ALTER TABLE dbo.Nota ADD cComentario VARCHAR(MAX) NULL"
        self.assertIn("Se identificó la columna cComentario definida como VARCHAR(MAX) como columna nueva de la tabla "
                      "dbo.Nota.", _max(sql)[0].mensaje)

    def test_varias_tablas_en_el_script(self):
        otra = ("CREATE TABLE dbo.Nota (\n nNotaId INT IDENTITY(1,1) NOT NULL,\n cObservacion VARCHAR(MAX) NOT NULL,\n"
                " CONSTRAINT PK_Nota PRIMARY KEY CLUSTERED (nNotaId)\n)\nGO\n")
        hallazgos = _max(_LOG + otra)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificaron dos tablas con columnas nuevas (N)VARCHAR(MAX): cDetalle "
            "(CONTABILIDAD.LogReprocesoDevengado); cObservacion (dbo.Nota). Se recomienda validar si es posible "
            "asignarles una longitud definida (ej.: VARCHAR(500)), ya que VARCHAR(MAX) solo se justifica para JSON, "
            "XML, HTML o textos de gran tamaño.",
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
