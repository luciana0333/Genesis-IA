import unittest

from app.analizadores.diccionario import verificar_diccionario
from app.modelos.hallazgo import Severidad
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
            ("caso_5_sucio", PROC_5, DIC_5, 4),
        ]

        for nombre, procedimiento, diccionario, esperado in casos:
            with self.subTest(caso=nombre):
                hallazgos = verificar_diccionario(procedimiento, diccionario)
                self.assertEqual(
                    len(hallazgos),
                    esperado,
                    f"Caso {nombre} devolvio {len(hallazgos)} hallazgos; se esperaban {esperado}."
                )


class TestSeveridadSegunCreateOAlter(unittest.TestCase):
    """CREATE: lo no documentado es alto. ALTER: solo se pide validar (bajo)."""

    CUERPO = """ PROCEDURE dbo.PA_Cliente_Consultar
    @nClienteId INT,
    @cCodigo VARCHAR(10)
AS
BEGIN
    SELECT 1
END"""

    # Documenta solo @nClienteId, con descripción vacía, y no documenta el procedimiento.
    DICCIONARIO = (
        "EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'', "
        "@level0type = N'SCHEMA', @level0name = N'dbo', "
        "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar', "
        "@level2type = N'PARAMETER', @level2name = N'@nClienteId';"
    )

    def _severidades(self, verbo):
        hallazgos = verificar_diccionario(verbo + self.CUERPO, self.DICCIONARIO)
        return {h.regla: h.severidad for h in hallazgos}

    def test_create_procedure_es_alto(self):
        severidades = self._severidades("CREATE")
        for regla in ("PROCEDIMIENTO_SIN_DESCRIPCION", "PARAMETRO_FALTANTE"):
            with self.subTest(regla=regla):
                self.assertEqual(severidades[regla], Severidad.ALTO)
        # Documentado pero sin descripción es otro caso: medio.
        self.assertEqual(severidades["DESCRIPCION_VACIA"], Severidad.MEDIO)

    def test_parametro_documentado_sin_descripcion_tiene_mensaje_propio(self):
        hallazgos = verificar_diccionario("CREATE" + self.CUERPO, self.DICCIONARIO)
        vacia = next(h for h in hallazgos if h.regla == "DESCRIPCION_VACIA")
        self.assertIn("El parámetro @nClienteId no tiene una descripción", vacia.mensaje)

    def test_procedimiento_documentado_sin_descripcion_no_es_lo_mismo_que_no_documentado(self):
        con_sentencia_vacia = self.DICCIONARIO + (
            "\nEXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'', "
            "@level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar';"
        )
        reglas = {h.regla: h for h in verificar_diccionario("CREATE" + self.CUERPO, con_sentencia_vacia)}
        self.assertNotIn("PROCEDIMIENTO_SIN_DESCRIPCION", reglas)
        self.assertIn("está documentado, pero no tiene una descripción",
                      reglas["DESCRIPCION_PROCEDIMIENTO_VACIA"].mensaje)

    def test_alter_procedure_solo_pide_validar_lo_no_documentado(self):
        hallazgos = verificar_diccionario("ALTER" + self.CUERPO, self.DICCIONARIO)
        reglas = [h.regla for h in hallazgos]
        self.assertNotIn("PROCEDIMIENTO_SIN_DESCRIPCION", reglas)
        self.assertNotIn("PARAMETRO_FALTANTE", reglas)
        validar = [h for h in hallazgos if h.regla == "VALIDAR_DOCUMENTACION_ALTER"]
        self.assertEqual(len(validar), 2)  # el procedimiento y @cCodigo
        self.assertTrue(all(h.severidad == Severidad.BAJO for h in validar))
        self.assertTrue(all("Valide" in h.mensaje for h in validar))

    def test_alter_procedure_revisa_lo_demas_igual_que_create(self):
        hallazgos = {h.regla: h for h in verificar_diccionario("ALTER" + self.CUERPO, self.DICCIONARIO)}
        self.assertEqual(hallazgos["DESCRIPCION_VACIA"].severidad, Severidad.MEDIO)
        mal_esquema = self.DICCIONARIO.replace("@level0name = N'dbo'", "@level0name = N'dbo2'")
        reglas = [h.regla for h in verificar_diccionario("ALTER" + self.CUERPO, mal_esquema)]
        self.assertIn("ESQUEMA_NO_COINCIDE", reglas)

    def test_parametros_se_comparan_sin_distinguir_mayusculas(self):
        diccionario = self.DICCIONARIO.replace("N'@nClienteId'", "N'@NCLIENTEID'")
        faltantes = [
            h.mensaje for h in verificar_diccionario("CREATE" + self.CUERPO, diccionario)
            if h.regla == "PARAMETRO_FALTANTE"
        ]
        self.assertEqual(len(faltantes), 1)
        self.assertIn("@cCodigo", faltantes[0])


class TestOrtografiaProcedimientos(unittest.TestCase):
    def test_detecta_palabras_mal_escritas_en_procedimiento_y_parametro(self):
        procedimiento = "CREATE PROCEDURE dbo.PA_Cliente_Consultar\n    @nClienteId INT\nAS\nBEGIN\n    SELECT 1\nEND"
        diccionario = (
            "EXEC sys.sp_addextendedproperty @name = N'MS_Description', "
            "@value = N'Consulta la informacion del clienet', @level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar';\n"
            "EXEC sys.sp_addextendedproperty @name = N'MS_Description', "
            "@value = N'Identificadodr del cliente', @level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar', "
            "@level2type = N'PARAMETER', @level2name = N'@nClienteId';"
        )
        hallazgos = [h for h in verificar_diccionario(procedimiento, diccionario) if h.regla == "ERROR_ORTOGRAFICO"]
        self.assertEqual(len(hallazgos), 2)
        self.assertIn("del procedimiento dbo.PA_Cliente_Consultar", hallazgos[0].mensaje)
        self.assertIn("'clienet' (¿quiso decir 'cliente'?)", hallazgos[0].mensaje)
        self.assertIn("del parámetro @nClienteId", hallazgos[1].mensaje)
        self.assertIn("'Identificadodr'", hallazgos[1].mensaje)
        self.assertEqual(hallazgos[1].linea, 2)


if __name__ == "__main__":
    unittest.main()
