"""Restricción de tabla escrita sin coma después de la última columna (SQL Server la acepta)."""

import unittest

from app.analizadores.analizador_tablas import extraer_columnas_nuevas, verificar_tabla

TASA = """create table dbo.Tasa
(
	nTasaId int identity(1,1)
	, cNombre varchar(200) collate SQL_Latin1_General_CP1_CI_AS not null default ''
	, bEstado bit not null
	constraint PK_Tasa_nTasaId primary key clustered (nTasaId),
	constraint UQ_Tasa_cNombre unique (cNombre)
)"""


class RestriccionSinComaTest(unittest.TestCase):
    def test_la_pk_es_la_de_la_lista_no_la_columna_anterior(self):
        reglas = {h.regla for h in verificar_tabla(TASA, False)}
        for regla in ("PK_NOMBRE_INVALIDO", "PK_SIN_IDENTITY", "PK_NO_NUMERICA", "PK_FALTANTE"):
            self.assertNotIn(regla, reglas)

    def test_la_columna_anterior_queda_sola(self):
        columnas = {c.nombre: c.definicion for c in extraer_columnas_nuevas(TASA)}
        self.assertEqual(list(columnas), ["nTasaId", "cNombre", "bEstado"])
        self.assertNotIn("primary", columnas["bEstado"].lower())

    def test_foreign_key_y_unique_pegados(self):
        sql = ("create table dbo.TasaHistorico (nTasaHistoricoId int identity(1,1), nTasaId int not null\n"
               "constraint FK_TasaHistorico_nTasaId foreign key (nTasaId) references dbo.Tasa (nTasaId),\n"
               "constraint PK_TasaHistorico_nTasaHistoricoId primary key clustered (nTasaHistoricoId))")
        self.assertEqual([c.nombre for c in extraer_columnas_nuevas(sql)], ["nTasaHistoricoId", "nTasaId"])
        self.assertNotIn("PK_FALTANTE", {h.regla for h in verificar_tabla(sql, False)})

    def test_la_pk_de_la_propia_columna_sigue_igual(self):
        bien = "CREATE TABLE dbo.Cliente (nClienteId INT IDENTITY(1,1) NOT NULL PRIMARY KEY CLUSTERED)"
        self.assertNotIn("PK_FALTANTE", {h.regla for h in verificar_tabla(bien, False)})
        mal = "CREATE TABLE dbo.Cliente (nClienteId INT IDENTITY(1,1) NOT NULL, bEstado BIT NOT NULL PRIMARY KEY)"
        self.assertIn("PK_NOMBRE_INVALIDO", {h.regla for h in verificar_tabla(mal, False)})

    def test_default_con_nombre_no_se_separa(self):
        sql = ("CREATE TABLE dbo.Cliente (nClienteId INT IDENTITY(1,1) NOT NULL PRIMARY KEY CLUSTERED, "
               "cNombre VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL CONSTRAINT DF_Cliente_cNombre DEFAULT '')")
        columnas = {c.nombre: c.definicion for c in extraer_columnas_nuevas(sql)}
        self.assertIn("DEFAULT", columnas["cNombre"])

    def test_moratorios_es_una_palabra(self):
        sql = ("CREATE TABLE dbo.Detalle (nDetalleId INT IDENTITY(1,1) NOT NULL PRIMARY KEY CLUSTERED, "
               "nDiasAntesCobrarInteresesMoratorios INT NOT NULL)")
        self.assertNotIn("COLUMNA_NOMBRE_NO_PASCALCASE", {h.regla for h in verificar_tabla(sql, False)})


class PalabraEnOtraFormaTest(unittest.TestCase):
    def test_no_se_parte_si_existe_en_otro_genero_o_numero(self):
        from app.analizadores import analizador_tablas
        # «moratorios» no está en el diccionario, pero «moratoria» sí: no es «mora» + «torios».
        self.assertTrue(analizador_tablas._otra_forma_valida("moratorios"))
        self.assertIsNone(analizador_tablas._corregir_palabras_pegadas("nInteresesMoratorios"))

    def test_las_palabras_pegadas_de_verdad_se_siguen_corrigiendo(self):
        from app.analizadores import analizador_tablas
        self.assertEqual(analizador_tablas._corregir_palabras_pegadas("nMontoaprobado"), "nMontoAprobado")
        self.assertEqual(analizador_tablas._corregir_palabras_pegadas("cCuentaspagadas"), "cCuentasPagadas")


if __name__ == "__main__":
    unittest.main()
