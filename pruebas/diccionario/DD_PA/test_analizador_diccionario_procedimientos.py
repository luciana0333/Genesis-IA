import unittest

from app.analizadores.diccionario import verificar_diccionario
from pruebas.diccionario.DD_PA.casos.test_caso1_perfecto import PROCEDIMIENTO as PROC_1, DICCIONARIO as DIC_1
from pruebas.diccionario.DD_PA.casos.test_caso2_parametros_faltantes import PROCEDIMIENTO as PROC_2, DICCIONARIO as DIC_2
from pruebas.diccionario.DD_PA.casos.test_caso3_texto_invalido import PROCEDIMIENTO as PROC_3, DICCIONARIO as DIC_3
from pruebas.diccionario.DD_PA.casos.test_caso4_sin_descripcion_procedimiento import PROCEDIMIENTO as PROC_4, DICCIONARIO as DIC_4
from pruebas.diccionario.DD_PA.casos.test_caso5_sucio import PROCEDIMIENTO as PROC_5, DICCIONARIO as DIC_5


class TestDiccionarioProcedimientos(unittest.TestCase):
    def test_procedimiento_sin_diccionario_detecta_parametros_faltantes(self):
        procedimiento = """
        CREATE PROCEDURE CLICKTOPAY.PA_Cliente_ActualizarCorreo
        (
            @nClienteId INT,
            @cCorreoElectronico VARCHAR(64),
            @cUsuario VARCHAR(4)
        );
        """

        hallazgos = verificar_diccionario(procedimiento, "")
        reglas = [hallazgo.regla for hallazgo in hallazgos]

        self.assertEqual(len(hallazgos), 4)
        self.assertIn("PROCEDIMIENTO_SIN_DESCRIPCION", reglas)
        self.assertEqual(reglas.count("PARAMETRO_FALTANTE"), 3)

    def test_diccionario_sin_go_ignora_comentarios(self):
        procedimiento = """
        CREATE PROCEDURE CLICKTOPAY.PA_Cliente_ActualizarCorreo
        (
            @nClienteId INT,
            @cCorreoElectronico VARCHAR(64),
            @cUsuario VARCHAR(4)
        )
        AS
        BEGIN
            UPDATE CLICKTOPAY.Cliente
            SET cCorreoElectronico = @cCorreoElectronico,
                dFechaActualizacion = GETDATE(),
                cUsuarioActualizacion = @cUsuario
            WHERE nClienteId = @nClienteId
        END
        """
        diccionario = """
        -- EXEC sys.sp_addextendedproperty @level2name='@parametroFalso';
        EXEC sys.sp_addextendedproperty
        @name=N'MS_Description', @value=N'Actualiza el correo del cliente',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_ActualizarCorreo';
        EXEC sys.sp_addextendedproperty
        @name=N'MS_Description', @value=N'Identificador',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_ActualizarCorreo',
        @level2type=N'PARAMETER', @level2name='@nClienteId';
        EXEC sys.sp_addextendedproperty
        @name=N'MS_Description', @value=N'Correo',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_ActualizarCorreo',
        @level2type=N'PARAMETER', @level2name='@cCorreoElectronico';
        EXEC sys.sp_addextendedproperty
        @name=N'MS_Description', @value=N'Usuario',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_ActualizarCorreo',
        @level2type=N'PARAMETER', @level2name='@cUsuario';
        """

        self.assertEqual(verificar_diccionario(procedimiento, diccionario), [])

    def test_casos_historicos(self):
        casos = [
            ("caso_1_perfecto", PROC_1, DIC_1, 0),
            ("caso_2_parametros_faltantes", PROC_2, DIC_2, 2),
            ("caso_3_texto_invalido", PROC_3, DIC_3, 0),
            ("caso_4_sin_descripcion_procedimiento", PROC_4, DIC_4, 1),
            ("caso_5_sucio", PROC_5, DIC_5, 6),
        ]

        for nombre, procedimiento, diccionario, esperado in casos:
            with self.subTest(caso=nombre):
                hallazgos = verificar_diccionario(procedimiento, diccionario)
                self.assertEqual(
                    len(hallazgos),
                    esperado,
                    f"Caso {nombre} devolvio {len(hallazgos)} hallazgos; se esperaban {esperado}."
                )


if __name__ == "__main__":
    unittest.main()
