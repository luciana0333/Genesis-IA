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
        CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Upd_Correo
        (
            @nClienteId INT,
            @cCorreoElectronico VARCHAR(64),
            @cUsuario VARCHAR(4)
        );
        """

        hallazgos = verificar_diccionario(procedimiento, "")
        reglas = [hallazgo.regla for hallazgo in hallazgos]

        self.assertEqual(len(hallazgos), 2)
        self.assertIn("PROCEDIMIENTO_SIN_DESCRIPCION", reglas)
        # Los tres parámetros van en un solo hallazgo, con sus nombres.
        faltantes = [h for h in hallazgos if h.regla == "PARAMETRO_FALTANTE"]
        self.assertEqual(len(faltantes), 1)
        self.assertIn("Se identificaron 3 parámetros sin documentar", faltantes[0].mensaje)
        for nombre in ("@nClienteId", "@cCorreoElectronico", "@cUsuario"):
            self.assertIn(nombre, faltantes[0].mensaje)
        self.assertIn("Se recomienda añadir los parámetros faltantes", faltantes[0].mensaje)

    def test_diccionario_sin_go_ignora_comentarios(self):
        procedimiento = """
        CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Upd_Correo
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
        @name=N'MS_Description', @value=N'Procedimiento que actualiza el correo del cliente',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_Upd_Correo';
        EXEC sys.sp_addextendedproperty
        @name=N'MS_Description', @value=N'Identificador',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_Upd_Correo',
        @level2type=N'PARAMETER', @level2name='@nClienteId';
        EXEC sys.sp_addextendedproperty
        @name=N'MS_Description', @value=N'Correo',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_Upd_Correo',
        @level2type=N'PARAMETER', @level2name='@cCorreoElectronico';
        EXEC sys.sp_addextendedproperty
        @name=N'MS_Description', @value=N'Usuario',
        @level0type=N'SCHEMA', @level0name='CLICKTOPAY',
        @level1type=N'PROCEDURE', @level1name='PA_Cliente_Upd_Correo',
        @level2type=N'PARAMETER', @level2name='@cUsuario';
        """

        self.assertEqual(verificar_diccionario(procedimiento, diccionario), [])

    def test_casos_historicos(self):
        casos = [
            ("caso_1_perfecto", PROC_1, DIC_1, 0),
            ("caso_2_parametros_faltantes", PROC_2, DIC_2, 1),  # agrupados en un solo hallazgo
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
        self.assertIn("El parámetro @nClienteId figura en el diccionario, pero no cuenta con una descripción",
                      vacia.mensaje)

    def test_procedimiento_documentado_sin_descripcion_no_es_lo_mismo_que_no_documentado(self):
        con_sentencia_vacia = self.DICCIONARIO + (
            "\nEXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'', "
            "@level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar';"
        )
        reglas = {h.regla: h for h in verificar_diccionario("CREATE" + self.CUERPO, con_sentencia_vacia)}
        self.assertNotIn("PROCEDIMIENTO_SIN_DESCRIPCION", reglas)
        self.assertIn("está documentado, pero su descripción se encuentra vacía",
                      reglas["DESCRIPCION_PROCEDIMIENTO_VACIA"].mensaje)

    # En ALTER, lo documentado se actualiza (sp_updateextendedproperty): si se agregara, saldría junto con
    # «se agregan» en la observación unida (ver test_validar_documentacion_unida.py).
    ACTUALIZA = DICCIONARIO.replace("sp_addextendedproperty", "sp_updateextendedproperty")

    def test_alter_procedure_solo_pide_validar_lo_no_documentado(self):
        hallazgos = verificar_diccionario("ALTER" + self.CUERPO, self.ACTUALIZA)
        reglas = [h.regla for h in hallazgos]
        self.assertNotIn("PROCEDIMIENTO_SIN_DESCRIPCION", reglas)
        self.assertNotIn("PARAMETRO_FALTANTE", reglas)
        validar = [h for h in hallazgos if h.regla == "VALIDAR_DOCUMENTACION_ALTER"]
        # El procedimiento y @cCodigo se piden validar en un solo hallazgo.
        self.assertEqual(len(validar), 1)
        self.assertEqual(validar[0].severidad, Severidad.BAJO)
        # Texto de la usuaria (20 nov.): una sola frase con el procedimiento y el parámetro, sin repetir.
        self.assertEqual(
            validar[0].mensaje,
            "Se identificó que el diccionario no incluye la descripción del procedimiento dbo.PA_Cliente_Consultar ni "
            "del parámetro @cCodigo. Se recomienda verificar si estas descripciones ya se encuentran registradas, "
            "considerando que se trata de una modificación del procedimiento (ALTER PROCEDURE).",
        )
        self.assertEqual(validar[0].mensaje[validar[0].inicio_que_hacer:][:13], "Se recomienda")

    def test_alter_desde_3_parametros_en_vinetas(self):
        cuerpo = self.CUERPO.replace("@cCodigo VARCHAR(10)", "@cA VARCHAR(1), @cB VARCHAR(1), @cC VARCHAR(1)")
        diccionario = self.ACTUALIZA + (
            "\nEXEC sys.sp_updateextendedproperty @name = N'MS_Description', @value = N'Procedimiento que consulta', "
            "@level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar';")
        validar = [h for h in verificar_diccionario("ALTER" + cuerpo, diccionario) if h.regla == "VALIDAR_DOCUMENTACION_ALTER"]
        self.assertEqual(
            validar[0].mensaje,
            "Se identificó que el diccionario no incluye la descripción de los siguientes parámetros: @cA; @cB; @cC. "
            "Se recomienda verificar si estas descripciones ya se encuentran registradas, considerando que se "
            "trata de una modificación del procedimiento (ALTER PROCEDURE).",
        )

    def test_alter_solo_el_procedimiento_en_singular(self):
        diccionario = self.ACTUALIZA.replace("N'@nClienteId'", "N'@cCodigo'") + self.ACTUALIZA.replace(
            "N''", "N'Identificador'")
        validar = [h for h in verificar_diccionario("ALTER" + self.CUERPO, diccionario) if h.regla == "VALIDAR_DOCUMENTACION_ALTER"]
        self.assertEqual(
            validar[0].mensaje,
            "Se identificó que el diccionario no incluye la descripción del procedimiento dbo.PA_Cliente_Consultar. "
            "Se recomienda verificar si esta descripción ya se encuentra registrada, considerando que se trata de una "
            "modificación del procedimiento (ALTER PROCEDURE).",
        )

    def test_alter_con_varios_procedimientos_va_en_tabla(self):
        def prop(pa, parametro=None, valor="Procedimiento que consulta"):
            texto = (f"EXEC sys.sp_updateextendedproperty @name=N'MS_Description', @value=N'{valor}', "
                     f"@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'PROCEDURE', @level1name=N'{pa}'")
            return texto + (f", @level2type=N'PARAMETER', @level2name=N'{parametro}';\n" if parametro else ";\n")
        script = ("-- encabezado\nALTER PROCEDURE dbo.PA_Cliente_Sel_Uno\n  @nA INT,\n  @nB INT\nAS\nSELECT 1\nGO\n"
                  "ALTER PROCEDURE dbo.PA_Cliente_Sel_Dos\n  @cX VARCHAR(2),\n  @cY VARCHAR(2)\nAS\nSELECT 2\n")
        diccionario = (prop("PA_Cliente_Sel_Uno", "@nA", "Identificador") + prop("PA_Cliente_Sel_Dos")
                       + prop("PA_Cliente_Sel_Dos", "@cY", "Código"))
        validar = [h for h in verificar_diccionario(script, diccionario) if h.regla == "VALIDAR_DOCUMENTACION_ALTER"]
        self.assertEqual(len(validar), 1)
        self.assertEqual(validar[0].grupos, [
            {"nombre": "dbo.PA_Cliente_Sel_Uno", "tipo": "Procedimiento", "lineas": [2, 4],
             "etiquetas": ["(descripción del procedimiento)", "@nB"]},
            {"nombre": "dbo.PA_Cliente_Sel_Dos", "tipo": "Procedimiento", "lineas": [9], "etiquetas": ["@cX"]},
        ])
        self.assertEqual(validar[0].lineas, [2, 4, 9])
        self.assertEqual(validar[0].seccion, "objeto")
        self.assertTrue(validar[0].mensaje.endswith(
            "Se recomienda verificar si estas descripciones ya se encuentran registradas, considerando que se trata "
            "de una modificación de los procedimientos (ALTER PROCEDURE)."))
        # Con un solo procedimiento por validar, su frase (el «Qué hacer» sigue en su sitio).
        solo_uno = [h for h in verificar_diccionario(script, diccionario + prop("PA_Cliente_Sel_Uno") + prop(
            "PA_Cliente_Sel_Uno", "@nB", "Otro")) if h.regla == "VALIDAR_DOCUMENTACION_ALTER"][0]
        self.assertIsNone(getattr(solo_uno, "grupos", None))
        self.assertEqual(solo_uno.lineas, [9])
        self.assertIn("En el procedimiento", solo_uno.mensaje)
        self.assertEqual(solo_uno.mensaje[solo_uno.inicio_que_hacer:][:13], "Se recomienda")

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
            "@value = N'Procedimiento que consulta la información del clienet', @level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar';\n"
            "EXEC sys.sp_addextendedproperty @name = N'MS_Description', "
            "@value = N'Identificadodr del cliente', @level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'PROCEDURE', @level1name = N'PA_Cliente_Consultar', "
            "@level2type = N'PARAMETER', @level2name = N'@nClienteId';"
        )
        hallazgos = [h for h in verificar_diccionario(procedimiento, diccionario) if h.regla == "ERROR_ORTOGRAFICO"]
        # Las dos descripciones con errores se reportan juntas, en sus líneas.
        self.assertEqual(len(hallazgos), 1)
        mensaje = hallazgos[0].mensaje
        self.assertEqual(hallazgos[0].lineas, [1, 2])  # las líneas van en el encabezado
        self.assertIn("Se identificaron 2 palabras mal escritas en el diccionario: 'clienet' → 'cliente' y "
                      "'Identificadodr' → 'Identificador'.", mensaje)


if __name__ == "__main__":
    unittest.main()
