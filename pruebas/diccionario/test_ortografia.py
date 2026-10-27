import unittest

from app.analizadores import ortografia
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas


DESCRIPCIONES_CORRECTAS = [
    "Identificador único del archivo de la solicitud",
    "Identificador único del estado",
    "Ruta de almacenamiento del archivo",
    "Fecha de registro del archivo; se asigna al insertar",
    "Indica si el registro se encuentra activo (1=Activo, 0=Inactivo)",
    "Correo electrónico de contacto del cliente",
    "Tabla que almacena la información del cliente",
    "Archivos adjuntos registrados para cada solicitud",
    "Monto del desembolso del crédito en soles",
    "Número de cuotas pendientes del préstamo",
    "Usuario que registra la operación",
    "Fecha y hora de la última actualización",
    "Observaciones ingresadas por el analista",
    "Código del producto crediticio",
    "Estados que puede tener una solicitud",
    "Clientes que tienen deuda vencida",
    "Campo que sirve para auditar cambios",
    "Motivo por el cual se rechaza la solicitud",
    "Se usa en @level2name y Estado.nEstadoId",
    # Casos de la usuaria que el diccionario anterior (pyspellchecker) marcaba como errores.
    "Periodo en formato AAAAMM",
    "Créditos reprogramados del mes",
    "Bono de gestión comercial",
    "Indica la tasa promedio ponderada al cierre del mes anterior",
]


@unittest.skipUnless(ortografia.disponible(), "falta el diccionario de español")
class TestOrtografia(unittest.TestCase):
    def test_descripciones_correctas_no_generan_avisos(self):
        for texto in DESCRIPCIONES_CORRECTAS:
            with self.subTest(texto=texto):
                self.assertEqual(ortografia.palabras_mal_escritas(texto), [])

    def test_detecta_palabras_mal_escritas_con_sugerencia(self):
        errores = dict(ortografia.palabras_mal_escritas("Fehca de regsitro del arhcivo del clienet"))
        self.assertEqual(errores["Fehca"], ["Fecha"])
        self.assertEqual(errores["regsitro"], ["registro"])
        self.assertEqual(errores["arhcivo"], ["archivo"])
        self.assertEqual(errores["clienet"], ["cliente"])
        self.assertEqual(ortografia.palabras_mal_escritas("Permite regsitrar el pago"), [("regsitrar", ["registrar"])])

    def test_la_sugerencia_empieza_con_la_misma_letra(self):
        # Antes sugería 'Sindicato' para 'Indicatg'.
        [(palabra, opciones)] = ortografia.palabras_mal_escritas("Indicatg si el estado esta activo")
        self.assertEqual(palabra, "Indicatg")
        self.assertTrue(all(o.lower().startswith("i") for o in opciones))

    def test_palabra_con_mayusculas_sueltas_al_final_se_revisa(self):
        # Caso reportado: 'clienteYY' se ignoraba por tener mayúsculas internas.
        self.assertEqual(
            ortografia.palabras_mal_escritas("Consulta la información del clienteYY"),
            [("clienteYY", ["cliente"])],
        )
        self.assertEqual(ortografia.palabras_mal_escritas("Estado ActivoX del registro"), [("ActivoX", ["Activo"])])

    def test_identificadores_reales_se_siguen_ignorando(self):
        self.assertEqual(
            ortografia.palabras_mal_escritas("Usa nEstadoId, cCodPersona y SolicitudArchivos del RUC"), []
        )

    def test_ejemplo_reportado_en_ambos_diccionarios(self):
        from app.analizadores.diccionario import verificar_diccionario

        procedimiento = "CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Consultar AS BEGIN SELECT 1 END"
        diccionario_proc = (
            "EXEC sys.sp_addextendedproperty\n@name=N'MS_Description',\n"
            "@value=N'Consulta la información del clienteYY',\n"
            "@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',\n"
            "@level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Consultar'\nGO"
        )
        reglas = [h.regla for h in verificar_diccionario(procedimiento, diccionario_proc)]
        self.assertIn("ERROR_ORTOGRAFICO", reglas)

        tabla = "CREATE TABLE CLICKTOPAY.Cliente (nClienteId INT NOT NULL);"
        diccionario_tabla = (
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', "
            "@value=N'Información del clienteYY', @level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', "
            "@level1type=N'TABLE', @level1name=N'Cliente';\n"
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', "
            "@value=N'Identificador del cliente', @level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', "
            "@level1type=N'TABLE', @level1name=N'Cliente', @level2type=N'COLUMN', @level2name=N'nClienteId';"
        )
        hallazgos = verificar_diccionario_tablas(tabla, diccionario_tabla)
        self.assertEqual([h.regla for h in hallazgos], ["ERROR_ORTOGRAFICO"])
        self.assertIn("corregir 'clienteYY' por 'cliente'", hallazgos[0].mensaje)

    def test_detecta_falta_de_tilde_y_sugiere_la_forma_correcta(self):
        self.assertEqual(
            ortografia.palabras_mal_escritas("Descripcion del codigo unico del credito"),
            [("Descripcion", ["Descripción"]), ("codigo", ["código"]), ("unico", ["único"]), ("credito", ["crédito"])],
        )
        # Tilde de más (guion se escribe sin tilde) y palabras que existen con y sin tilde (numero/número).
        self.assertEqual(ortografia.palabras_mal_escritas("Estado del guión"), [("guión", ["guion"])])
        self.assertEqual(ortografia.palabras_mal_escritas("Solo numero el registro"), [])

    def test_la_falta_de_tilde_se_indica_en_el_mensaje(self):
        errores = ortografia.palabras_mal_escritas("Codigo de operacion del clinete")
        self.assertEqual(
            ortografia.elemento_ortografico("del parámetro @x", errores),
            "Descripción del parámetro @x: 'Codigo' → 'Código' (tilde), 'operacion' → 'operación' (tilde), "
            "'clinete' → 'cliente'",
        )

    def test_en_mayusculas_no_se_exige_la_tilde(self):
        self.assertEqual(ortografia.palabras_mal_escritas("CODIGO DEL CLIENTE"), [])

    def test_ignora_nombres_de_objetos_siglas_y_vocabulario(self):
        texto = "Valor de nEstadoId para el RUC del cliente enviado por email desde Estado"
        self.assertEqual(ortografia.palabras_mal_escritas(texto, ["Estado"]), [])

    def test_descripcion_en_mayusculas_se_revisa(self):
        # Escrita en mayúsculas, las palabras largas no son siglas y se revisan.
        self.assertEqual(ortografia.palabras_mal_escritas("CONSULTA LA INFORMACION DEL CLEINTE"),
                         [("CLEINTE", ["CLIENTE"])])
        self.assertEqual(ortografia.palabras_mal_escritas("Consulta la ROJSH DEL CLIENTE"), [("ROJSH", [])])
        # Las siglas cortas se siguen respetando.
        self.assertEqual(ortografia.palabras_mal_escritas("CONSULTA EL RUC Y DNI DEL CLIENTE"), [])

    def test_solo_sugiere_si_la_correccion_es_segura(self):
        casos = {
            "Actualisa el estado": ("Actualisa", ["Actualiza"]),
            "Desactiba la cuenta": ("Desactiba", ["Desactiva"]),
            "Elimna el registro": ("Elimna", ["Elimina"]),
            "Devuelve el saldo disponivle": ("disponivle", ["disponible"]),
            "Consulta datos del cliente thy": ("thy", []),  # sin una corrección segura: revisar
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(ortografia.palabras_mal_escritas(texto), [esperado])
        self.assertEqual(ortografia.palabras_mal_escritas("Desactiva y reactiva la cuenta"), [])

    def test_mensaje_sin_sugerencia_pide_revisar_la_descripcion(self):
        mensaje = ortografia.redactar_error_ortografico("del procedimiento dbo.PA_X", [("ROJSH", [])], "del procedimiento")
        self.assertIn("revisar la palabra 'ROJSH' y escribir correctamente la descripción", mensaje)
        varios = ortografia.redactar_error_ortografico("de la tabla dbo.T", [("a", ["b"]), ("c", ["d"])], "de la tabla")
        self.assertTrue(varios.startswith("Se identificaron 2 errores de escritura"))

    def test_ejemplo_del_equipo_en_el_diccionario_de_tablas(self):
        tabla = "CREATE TABLE dbo.Estado (nEstadoId INT NOT NULL);"
        diccionario = (
            "EXEC sys.sp_addextendedproperty @name = N'MS_Description', "
            "@value = N'Estados que puede tener una solicitud', "
            "@level0type = N'SCHEMA', @level0name = dbo, @level1type = N'TABLE', @level1name = Estado;\n"
            "-- nEstadoId\n"
            "EXEC sys.sp_addextendedproperty \n@name = N'MS_Description',\n"
            "@value = N'Identificadodr único del estado',\n"
            "@level0type = N'SCHEMA', @level0name = dbo,\n"
            "@level1type = N'TABLE',  @level1name = Estado,\n"
            "@level2type = N'COLUMN', @level2name = nEstadoId;"
        )
        hallazgos = verificar_diccionario_tablas(tabla, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["ERROR_ORTOGRAFICO"])
        self.assertEqual(hallazgos[0].linea, 5)  # la línea del @value con el error
        self.assertIn("columna nEstadoId", hallazgos[0].mensaje)
        self.assertIn("'Identificadodr'", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
