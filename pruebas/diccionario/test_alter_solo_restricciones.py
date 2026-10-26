"""Un ALTER TABLE que solo agrega o quita restricciones (PK, FK, DEFAULT...) no pide diccionario."""

import unittest

from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas


def _reglas(tabla: str, diccionario: str = "") -> list:
    return [h.regla for h in verificar_diccionario_tablas(tabla, diccionario)]


class TestAlterSoloRestricciones(unittest.TestCase):
    def test_caso_de_la_usuaria_pk_de_una_columna_existente(self):
        tabla = """BEGIN TRANSACTION T1
BEGIN TRY

    ALTER TABLE COLOCACIONES.ColocCoordAgeVirtual
    ADD CONSTRAINT PK_ColocCoordAgeVirtual PRIMARY KEY CLUSTERED (nColocCoordAgeVirtualId);

    ALTER TABLE RRHH.CumplimientoMetasPer
    ADD
        nCierreTapp DECIMAL(5,2) NOT NULL DEFAULT 0.00;

    COMMIT TRANSACTION T1
END TRY
BEGIN CATCH
    ROLLBACK TRANSACTION T1
END CATCH
"""
        diccionario = (
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Indica la tasa promedio ponderada.', "
            "@level0type=N'SCHEMA', @level0name=N'RRHH', @level1type=N'TABLE', @level1name=N'CumplimientoMetasPer', "
            "@level2type=N'COLUMN', @level2name=N'nCierreTapp'\n"
        )
        self.assertEqual(_reglas(tabla, diccionario), [])

    def test_solo_restricciones_no_pide_diccionario(self):
        casos = (
            "ALTER TABLE dbo.Cliente ADD CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId);",
            "ALTER TABLE dbo.Cliente ADD CONSTRAINT FK_Cliente_Agencia FOREIGN KEY (nAgenciaId) "
            "REFERENCES dbo.Agencia (nAgenciaId);",
            "ALTER TABLE dbo.Cliente ADD CONSTRAINT DF_Cliente_nEstado DEFAULT 1 FOR nEstado;",
            "ALTER TABLE dbo.Cliente WITH CHECK ADD CONSTRAINT FK_Cliente_Agencia FOREIGN KEY (nAgenciaId) "
            "REFERENCES dbo.Agencia (nAgenciaId);",
            "ALTER TABLE dbo.Cliente DROP CONSTRAINT DF_Cliente_nEstado;",
        )
        for tabla in casos:
            with self.subTest(tabla=tabla):
                self.assertNotIn("ALTER_SIN_DICCIONARIO", _reglas(tabla))

    def test_columnas_nuevas_o_modificadas_si_piden_diccionario(self):
        self.assertIn("COLUMNA_FALTANTE", _reglas("ALTER TABLE dbo.Cliente ADD nMonto INT NOT NULL DEFAULT 0;"))
        self.assertIn("VALIDAR_COLUMNA_MODIFICADA", _reglas("ALTER TABLE dbo.Cliente ALTER COLUMN nMonto BIGINT NOT NULL;"))


if __name__ == "__main__":
    unittest.main()
