import unittest

from app.analizadores import ortografia
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas


DESCRIPCIONES_CORRECTAS = [
    "Identificador unico del archivo de la solicitud",
    "Identificador único del estado",
    "Ruta de almacenamiento del archivo",
    "Fecha de registro del archivo; se asigna al insertar",
    "Indica si el registro se encuentra activo (1=Activo, 0=Inactivo)",
    "Correo electronico de contacto del cliente",
    "Tabla que almacena la informacion del cliente",
    "Archivos adjuntos registrados para cada solicitud",
    "Monto del desembolso del credito en soles",
    "Numero de cuotas pendientes del prestamo",
    "Usuario que registra la operacion",
    "Fecha y hora de la ultima actualizacion",
    "Observaciones ingresadas por el analista",
    "Codigo del producto crediticio",
    "Estados que puede tener una solicitud",
    "Clientes que tienen deuda vencida",
    "Campo que sirve para auditar cambios",
    "Motivo por el cual se rechaza la solicitud",
    "Se usa en @level2name y TB_Estado.nEstadoId",
]


@unittest.skipUnless(ortografia.disponible(), "pyspellchecker no está instalado")
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
            ortografia.palabras_mal_escritas("Consulta la informacion del clienteYY"),
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
            "@value=N'Consulta la informacion del clienteYY',\n"
            "@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',\n"
            "@level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Consultar'\nGO"
        )
        reglas = [h.regla for h in verificar_diccionario(procedimiento, diccionario_proc)]
        self.assertIn("ERROR_ORTOGRAFICO", reglas)

        tabla = "CREATE TABLE CLICKTOPAY.Cliente (nClienteId INT NOT NULL);"
        diccionario_tabla = (
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', "
            "@value=N'Informacion del clienteYY', @level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', "
            "@level1type=N'TABLE', @level1name=N'Cliente';\n"
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', "
            "@value=N'Identificador del cliente', @level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', "
            "@level1type=N'TABLE', @level1name=N'Cliente', @level2type=N'COLUMN', @level2name=N'nClienteId';"
        )
        hallazgos = verificar_diccionario_tablas(tabla, diccionario_tabla)
        self.assertEqual([h.regla for h in hallazgos], ["ERROR_ORTOGRAFICO"])
        self.assertIn("'clienteYY' (¿quiso decir 'cliente'?)", hallazgos[0].mensaje)

    def test_no_exige_tildes(self):
        self.assertEqual(ortografia.palabras_mal_escritas("Descripcion del codigo unico"), [])

    def test_ignora_nombres_de_objetos_siglas_y_vocabulario(self):
        texto = "Valor de nEstadoId para el RUC del cliente enviado por email desde TB_Estado"
        self.assertEqual(ortografia.palabras_mal_escritas(texto, ["TB_Estado"]), [])

    def test_ejemplo_del_equipo_en_el_diccionario_de_tablas(self):
        tabla = "CREATE TABLE dbo.TB_Estado (nEstadoId INT NOT NULL);"
        diccionario = (
            "EXEC sys.sp_addextendedproperty @name = N'MS_Description', "
            "@value = N'Estados que puede tener una solicitud', "
            "@level0type = N'SCHEMA', @level0name = dbo, @level1type = N'TABLE', @level1name = TB_Estado;\n"
            "-- nEstadoId\n"
            "EXEC sys.sp_addextendedproperty \n@name = N'MS_Description',\n"
            "@value = N'Identificadodr único del estado',\n"
            "@level0type = N'SCHEMA', @level0name = dbo,\n"
            "@level1type = N'TABLE',  @level1name = TB_Estado,\n"
            "@level2type = N'COLUMN', @level2name = nEstadoId;"
        )
        hallazgos = verificar_diccionario_tablas(tabla, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["ERROR_ORTOGRAFICO"])
        self.assertEqual(hallazgos[0].linea, 3)
        self.assertIn("columna nEstadoId", hallazgos[0].mensaje)
        self.assertIn("'Identificadodr'", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
