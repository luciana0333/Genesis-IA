"""C1 de Tablas: ALTER TABLE ... ADD columna NOT NULL sin DEFAULT falla si la tabla tiene registros."""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla


def _reglas(sql: str):
    return {h.regla: h for h in verificar_tabla(sql)}


class TestNotNullSinDefaultEnAlter(unittest.TestCase):
    def test_not_null_sin_default_es_critico(self):
        hallazgo = _reglas("ALTER TABLE dbo.Cliente ADD nEdad INT NOT NULL")["COLUMNA_NOT_NULL_SIN_DEFAULT_EN_ALTER"]
        self.assertEqual(hallazgo.severidad.value, "critico")
        self.assertIn("el ALTER TABLE fallará si la tabla ya tiene registros", hallazgo.mensaje)
        self.assertIn("nEdad INT NOT NULL CONSTRAINT DF_Cliente_nEdad DEFAULT (0)", hallazgo.mensaje)

    def test_ejemplo_de_default_segun_el_tipo(self):
        mensajes = {
            "cCodigo VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL": "DEFAULT ('')",
            "bActivo BIT NOT NULL": "DEFAULT (0)",
            "dFechaAlta DATETIME NOT NULL": "DEFAULT (GETDATE())",
        }
        for columna, esperado in mensajes.items():
            with self.subTest(columna=columna):
                hallazgo = _reglas(f"ALTER TABLE dbo.Cliente ADD {columna}")["COLUMNA_NOT_NULL_SIN_DEFAULT_EN_ALTER"]
                self.assertIn(esperado, hallazgo.mensaje)

    def test_con_default_o_identity_no_se_marca(self):
        for columna in (
            "nEdad INT NOT NULL DEFAULT (0)",
            "nEdad INT NOT NULL CONSTRAINT DF_Cliente_nEdad DEFAULT (0)",
            "nCorrelativo INT IDENTITY(1,1) NOT NULL",
        ):
            with self.subTest(columna=columna):
                self.assertNotIn("COLUMNA_NOT_NULL_SIN_DEFAULT_EN_ALTER", _reglas(f"ALTER TABLE dbo.Cliente ADD {columna}"))

    def test_null_sigue_pidiendo_evaluar_default(self):
        reglas = _reglas("ALTER TABLE dbo.Cliente ADD nEdad INT NULL")
        self.assertIn("COLUMNA_NULL_EN_ALTER", reglas)
        self.assertNotIn("COLUMNA_NOT_NULL_SIN_DEFAULT_EN_ALTER", reglas)

    def test_en_un_create_no_aplica(self):
        sql = (
            "CREATE TABLE dbo.Cliente (\n nClienteId INT IDENTITY(1,1) NOT NULL,\n nEdad INT NOT NULL,\n"
            " CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)\n)"
        )
        self.assertNotIn("COLUMNA_NOT_NULL_SIN_DEFAULT_EN_ALTER", _reglas(sql))


if __name__ == "__main__":
    unittest.main()
