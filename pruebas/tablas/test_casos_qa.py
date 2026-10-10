"""Casos de borde encontrados en la auditoría de QA del módulo de Tablas."""
import unittest

from app.analizadores.analizador_tablas import verificar_tabla

C = "COLLATE SQL_Latin1_General_CP1_CI_AS"
TABLA = f"""CREATE TABLE dbo.Cliente (
    nClienteId INT IDENTITY(1,1) NOT NULL,
    cNombre VARCHAR(100) {C} NOT NULL,
    nMonto DECIMAL(18,2) NOT NULL,
    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)
);"""


def reglas(sql):
    return [(h.regla, h.linea) for h in verificar_tabla(sql)]


class TestTablasQA(unittest.TestCase):
    def test_columna_calculada_no_exige_not_null(self):
        sql = TABLA.replace("    CONSTRAINT", "    nDoble AS (nMonto * 2),\n    CONSTRAINT")
        self.assertEqual(reglas(sql), [])

    def test_text_es_tipo_de_texto(self):
        # TEXT es de texto (COLLATE válido, prefijo c), aunque se reporta como legacy.
        con_collate = TABLA.replace(f"cNombre VARCHAR(100) {C}", f"cNombre TEXT {C}")
        self.assertEqual(reglas(con_collate), [("COLUMNA_TIPO_LEGACY", 3)])
        sin_prefijo = TABLA.replace(f"cNombre VARCHAR(100) {C}", f"Nombre NTEXT {C}")
        self.assertIn("COLUMNA_PREFIJO_TIPO_INVALIDO", {r for r, _ in reglas(sin_prefijo)})

    def test_alter_sin_esquema(self):
        sql = f"ALTER TABLE Cliente ADD cCorreo VARCHAR(64) {C} NOT NULL DEFAULT ('');"
        self.assertEqual(reglas(sql), [("TABLA_SIN_ESQUEMA", 1)])

    def test_varias_tablas_en_un_script(self):
        sql = TABLA + "\nGO\nCREATE TABLE Pais (\n Nombre VARCHAR(10)\n);"
        hallazgos = reglas(sql)
        self.assertIn(("TABLA_SIN_ESQUEMA", 8), hallazgos)
        self.assertIn(("COLUMNA_PREFIJO_TIPO_INVALIDO", 9), hallazgos)
        self.assertFalse(any(linea < 8 for _, linea in hallazgos))

    def test_alter_de_la_misma_tabla_va_con_su_create(self):
        sql = TABLA + "\nALTER TABLE dbo.Cliente ADD CONSTRAINT UQ_Cliente UNIQUE (cNombre);"
        self.assertEqual(reglas(sql), [])

    def test_alter_column_existente_no_revisa_el_nombre(self):
        self.assertEqual(reglas("ALTER TABLE dbo.Cliente ALTER COLUMN Persona VARCHAR(40) NULL;"), [])


    def test_tipos_legacy_no_permitidos(self):
        for tipo, reemplazo in (("TEXT", "VARCHAR(MAX)"), ("NTEXT", "NVARCHAR(MAX)")):
            with self.subTest(tipo=tipo):
                sql = TABLA.replace(f"cNombre VARCHAR(100) {C}", f"cNombre {tipo} {C}")
                hallazgo = next(h for h in verificar_tabla(sql) if h.regla == "COLUMNA_TIPO_LEGACY")
                self.assertIn(f"Usar {reemplazo}", hallazgo.mensaje)
        real = TABLA.replace("nMonto DECIMAL(18,2)", "nMonto REAL")
        self.assertEqual(reglas(real), [("COLUMNA_TIPO_LEGACY", 4)])

    def test_columnas_para_documentos_no_permitidas(self):
        for tipo in ("VARBINARY(MAX)", "IMAGE"):
            with self.subTest(tipo=tipo):
                sql = TABLA.replace("    CONSTRAINT", f"    vArchivo {tipo} NOT NULL,\n    CONSTRAINT")
                hallazgo = next(h for h in verificar_tabla(sql) if h.regla == "COLUMNA_VARBINARY_PROHIBIDA")
                self.assertIn("datos transaccionales", hallazgo.mensaje)

    def test_legacy_agrupados_muestran_su_tipo(self):
        sql = TABLA.replace(f"cNombre VARCHAR(100) {C}", f"cNombre TEXT {C}").replace("nMonto DECIMAL(18,2)", "nMonto REAL")
        hallazgo = next(h for h in verificar_tabla(sql) if h.regla == "COLUMNA_TIPO_LEGACY")
        self.assertIn("cNombre (TEXT → VARCHAR(MAX)); nMonto (REAL → DECIMAL(p, s))", hallazgo.mensaje)


if __name__ == "__main__":
    unittest.main()
