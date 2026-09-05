import unittest

from app.analizadores.analizador_tablas import verificar_tabla


class TestAnalizadorTablas(unittest.TestCase):
    def test_create_exige_esquema_y_reglas_de_columna(self):
        hallazgos = verificar_tabla("CREATE TABLE Cliente (Id INT);")
        reglas = {hallazgo.regla for hallazgo in hallazgos}

        self.assertEqual(
            reglas,
            {
                "TABLA_SIN_ESQUEMA",
                "COLUMNA_PREFIJO_TIPO_INVALIDO",
                "COLUMNA_SIN_NOT_NULL_NI_DEFAULT",
            },
        )

    def test_create_valida_columnas_completas_fuera_de_dbcmaica(self):
        sql = """
        CREATE TABLE dbo.Cliente (
            nClienteId INT NOT NULL,
            bEstado BIT DEFAULT 1 NOT NULL
        );
        """

        self.assertEqual(verificar_tabla(sql), [])

    def test_alter_add_exige_not_null_o_default_y_collate(self):
        sql = "ALTER TABLE dbo.Cliente ADD Nombre VARCHAR(100);"
        reglas = {hallazgo.regla for hallazgo in verificar_tabla(sql)}

        self.assertEqual(
            reglas,
            {
                "COLUMNA_PREFIJO_TIPO_INVALIDO",
                "COLUMNA_SIN_NOT_NULL_NI_DEFAULT",
                "COLUMNA_SIN_COLLATE",
            },
        )

    def test_alter_con_parentesis_reconoce_not_null_y_default(self):
        sql = """
        ALTER TABLE dbo.Productos (
            ADD cNombre VARCHAR(100) NOT NULL DEFAULT '' COLLATE Latin1_General_CI_AS
        )
        """

        reglas = {hallazgo.regla for hallazgo in verificar_tabla(sql)}
        self.assertNotIn("COLUMNA_SIN_NOT_NULL_NI_DEFAULT", reglas)
        self.assertNotIn("COLUMNA_SIN_COLLATE", reglas)

    def test_dbcmaica_permite_omitir_collate(self):
        sql = "CREATE TABLE DBCMAICA.dbo.Cliente (nId INT NOT NULL);"

        self.assertEqual(verificar_tabla(sql), [])

    def test_opcion_dbcmaica_permite_omitir_collate(self):
        sql = "CREATE TABLE dbo.Cliente (nId INT NOT NULL);"

        self.assertEqual(verificar_tabla(sql, es_dbcmaica=True), [])

    def test_valida_prefijos_de_columnas_por_tipo(self):
        sql = """
        CREATE TABLE dbo.Persona (
            cNombre VARCHAR(100) NOT NULL COLLATE Latin1_General_CI_AS,
            nMonto DECIMAL(12, 2) NOT NULL,
            bActivo BIT NOT NULL,
            dFecha DATETIME NOT NULL
        );
        """

        self.assertEqual(verificar_tabla(sql), [])

    def test_collate_solo_se_exige_en_varchar_y_char(self):
        sql = """
        CREATE TABLE dbo.Persona (
            nId INT NOT NULL,
            nMonto MONEY NOT NULL,
            bActivo BIT NOT NULL,
            dFecha DATETIME NOT NULL,
            cNombre VARCHAR(100) NOT NULL
        );
        """
        reglas = [hallazgo.regla for hallazgo in verificar_tabla(sql)]

        self.assertEqual(reglas.count("COLUMNA_SIN_COLLATE"), 1)

    def test_collate_en_tipo_no_textual_es_invalido(self):
        sql = "CREATE TABLE dbo.Persona (nId INT NOT NULL COLLATE Latin1_General_CI_AS);"
        reglas = [hallazgo.regla for hallazgo in verificar_tabla(sql)]

        self.assertIn("COLLATE_EN_TIPO_NO_TEXTO", reglas)

    def test_detecta_prefijo_incorrecto(self):
        sql = "CREATE TABLE dbo.Persona (Nombre VARCHAR(100) NOT NULL COLLATE Latin1_General_CI_AS);"
        reglas = {hallazgo.regla for hallazgo in verificar_tabla(sql)}

        self.assertIn("COLUMNA_PREFIJO_TIPO_INVALIDO", reglas)

    def test_caso_cliente_detecta_prefijos_n_c_c(self):
        sql = """
        CREATE TABLE CLICKTOPAY.Cliente (
            ClienteId INT PRIMARY KEY IDENTITY(1,1) NOT NULL COLLATE Latin1_General_CI_AS,
            CodPersona VARCHAR(20) NOT NULL COLLATE Latin1_General_CI_AS,
            CorreoElectronico VARCHAR(64) NOT NULL COLLATE Latin1_General_CI_AS
        );
        """

        hallazgos = verificar_tabla(sql)
        prefijos = [
            hallazgo for hallazgo in hallazgos
            if hallazgo.regla == "COLUMNA_PREFIJO_TIPO_INVALIDO"
        ]

        self.assertEqual(len(prefijos), 3)
        self.assertEqual([hallazgo.linea for hallazgo in prefijos], [3, 4, 5])

    def test_detecta_palabra_omitible_en_nombre_de_tabla(self):
        sql = "CREATE TABLE dbo.PersonaDeCliente (nId INT NOT NULL COLLATE Latin1_General_CI_AS);"
        reglas = {hallazgo.regla for hallazgo in verificar_tabla(sql)}

        self.assertIn("TABLA_CON_PALABRA_OMITIBLE", reglas)


if __name__ == "__main__":
    unittest.main()