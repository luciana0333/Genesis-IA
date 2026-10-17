"""Reglas del bloque de índices (segunda cajita de la pestaña Tablas)."""
import unittest

from app.analizadores.analizador_indices import verificar_indices

C = "COLLATE SQL_Latin1_General_CP1_CI_AS"
TABLA = f"""CREATE TABLE CLICKTOPAY.Cliente (
    nClienteId INT IDENTITY(1,1) NOT NULL,
    cCodPersona VARCHAR(20) {C} NOT NULL,
    cCorreoElectronico VARCHAR(64) {C} NOT NULL,
    cObservacion VARCHAR(MAX) {C} NOT NULL,
    dRegistro DATETIME NOT NULL,
    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)
);"""


def reglas(indices, tabla=TABLA):
    return [(h.regla, h.linea) for h in verificar_indices(indices, tabla)]


def mensaje(indices, tabla=TABLA):
    return verificar_indices(indices, tabla)[0].mensaje


class TestIndices(unittest.TestCase):
    def test_indices_correctos(self):
        casos = (
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona\n    ON CLICKTOPAY.Cliente (cCodPersona);",
            "CREATE INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);",  # NONCLUSTERED por defecto
            "CREATE UNIQUE NONCLUSTERED INDEX IXUN_Cliente_cCorreoElectronico ON CLICKTOPAY.Cliente (cCorreoElectronico);",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona_dRegistro_INC01 ON CLICKTOPAY.Cliente "
            "(cCodPersona, dRegistro DESC) INCLUDE (cCorreoElectronico);",
            "CREATE NONCLUSTERED INDEX [IXN_Cliente_cCodPersona] ON [CLICKTOPAY].[Cliente] ([cCodPersona] ASC);",
        )
        for indices in casos:
            with self.subTest(indices=indices):
                self.assertEqual(reglas(indices), [])

    def test_los_hallazgos_son_de_la_cajita_de_indices(self):
        hallazgo = verificar_indices("\n\nCREATE INDEX idx1 ON CLICKTOPAY.Cliente (cCodPersona);", TABLA)[0]
        self.assertEqual((hallazgo.linea, hallazgo.seccion), (3, "indices"))

    def test_prefijo_segun_el_tipo(self):
        casos = {
            # Con el tipo declarado: el prefijo de ese tipo y el nombre de ejemplo.
            "CREATE NONCLUSTERED INDEX IX_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);":
                "(IXN_ para índices nonclustered), por ejemplo: IXN_Cliente_cCodPersona",
            # Sin el tipo: los prefijos posibles y que se declare el tipo.
            "CREATE INDEX idx1 ON CLICKTOPAY.Cliente (cCodPersona);":
                "(IX_ para índices clustered o IXN_ para nonclustered) y especificar el tipo de índice",
            "CREATE UNIQUE INDEX IXN_Cliente_cCorreoElectronico ON CLICKTOPAY.Cliente (cCorreoElectronico);":
                "(IXU_ para índices unique clustered o IXUN_ para unique nonclustered)",
        }
        for indices, recomendacion in casos.items():
            with self.subTest(indices=indices):
                self.assertEqual(reglas(indices), [("INDICE_PREFIJO_INVALIDO", 1)])
                self.assertIn("no cumple con la nomenclatura establecida", mensaje(indices))
                self.assertIn(recomendacion, mensaje(indices))

    def test_include_con_mas_de_cinco_columnas(self):
        tabla = ("CREATE TABLE dbo.Persona (nPersonaId INT IDENTITY(1,1) NOT NULL, nEstado INT NOT NULL, "
                 "c1 INT NOT NULL, c2 INT NOT NULL, c3 INT NOT NULL, c4 INT NOT NULL, c5 INT NOT NULL, c6 INT NOT NULL, "
                 "CONSTRAINT PK_Persona PRIMARY KEY CLUSTERED (nPersonaId));")
        seis = "CREATE NONCLUSTERED INDEX IXN_Persona_nEstado_INC06 ON dbo.Persona (nEstado) INCLUDE (c1, c2, c3, c4, c5, c6);"
        hallazgo = next(h for h in verificar_indices(seis, tabla) if h.regla == "INDICE_INCLUDE_EXTENSO")
        self.assertEqual(hallazgo.severidad.value, "medio")
        self.assertIn("lleva 6 columnas en su INCLUDE (c1, c2, c3, c4, c5, c6)", hallazgo.mensaje)
        cinco = "CREATE NONCLUSTERED INDEX IXN_Persona_nEstado_INC05 ON dbo.Persona (nEstado) INCLUDE (c1, c2, c3, c4, c5);"
        self.assertNotIn("INDICE_INCLUDE_EXTENSO", {h.regla for h in verificar_indices(cinco, tabla)})

    def test_indice_sin_tipo_pide_anadir_el_tipo(self):
        sin_tipo = "CREATE INDEX idx_persona\n    ON CLICKTOPAY.Cliente (cCodPersona);"
        texto = mensaje(sin_tipo)
        self.assertEqual(
            texto,
            "Se identificó que el índice idx_persona no cumple con la nomenclatura establecida. Se recomienda "
            "utilizar el prefijo correspondiente (IX_ para índices clustered o IXN_ para nonclustered) y "
            "especificar el tipo de índice explícitamente en su creación.",
        )
        con_tipo = "CREATE NONCLUSTERED INDEX IX_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);"
        self.assertNotIn("especificar el tipo de índice", mensaje(con_tipo))

    def test_nombre_con_tabla_campos_e_inc(self):
        campos = "CREATE NONCLUSTERED INDEX IXN_Cliente_Codigo ON CLICKTOPAY.Cliente (cCodPersona);"
        self.assertEqual(reglas(campos), [("INDICE_NOMBRE_NO_ESTANDAR", 1)])
        sin_inc = ("CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona) "
                   "INCLUDE (dRegistro, cCorreoElectronico);")
        self.assertIn("Renombrarlo como IXN_Cliente_cCodPersona_INC02", mensaje(sin_inc))

    def test_ejemplos_del_manual(self):
        persona = """CREATE TABLE DBO.PERSONA (
    CPERSCOD VARCHAR(20) NOT NULL, NPERSCLASIFICACION INT NOT NULL, CPERSESTADO CHAR(1) NOT NULL,
    CPERSNOMBRE VARCHAR(100) NOT NULL, NPERSPERSONERIA INT NOT NULL, DPERSNACCREAC DATETIME NOT NULL
);"""
        con_include = (
            "CREATE NONCLUSTERED INDEX [IXN_PERSONA_CPERSCOD_NPERSCLASIFICACION_CPERSESTADO_INC02]\n"
            "ON     [DBO].[PERSONA] ([CPERSCOD] ASC,[NPERSCLASIFICACION] ASC,[CPERSESTADO] ASC)\n"
            "INCLUDE ([CPERSNOMBRE] ,[NPERSPERSONERIA])\nGO"
        )
        sin_include = (
            "CREATE NONCLUSTERED INDEX [IXN_PERSONA_DPERSNACCREAC_CPERSCOD]\n"
            "ON [DBO].[PERSONA]([DPERSNACCREAC] ASC, [CPERSCOD] ASC )\nGO"
        )
        sin_corchetes = "CREATE NONCLUSTERED INDEX IXN_PERSONA_DPERSNACCREAC_CPERSCOD ON DBO.PERSONA (DPERSNACCREAC, CPERSCOD)"
        for indices in (con_include, sin_include, sin_corchetes):
            with self.subTest(indices=indices):
                self.assertEqual(reglas(indices, persona), [])
        inc_un_digito = con_include.replace("_INC02", "_INC2")
        self.assertIn("Renombrarlo como IXN_PERSONA_CPERSCOD_NPERSCLASIFICACION_CPERSESTADO_INC02", mensaje(inc_un_digito, persona))

    def test_sintaxis(self):
        casos = {
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona (cCodPersona);": "le falta la tabla a la que pertenece",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente;": "le falta la lista de columnas",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona;": "paréntesis que cierra",
            "CREATE NONCLUSTERED INDEX ON CLICKTOPAY.Cliente (cCodPersona);": "a un índice le falta el nombre",
        }
        for indices, texto in casos.items():
            with self.subTest(indices=indices):
                self.assertEqual(reglas(indices), [("INDICE_SINTAXIS_INVALIDA", 1)])
                self.assertIn(texto, mensaje(indices))

    def test_estructura_contra_la_tabla(self):
        casos = {
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON Cliente (cCodPersona);": "INDICE_SIN_ESQUEMA",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cDocumento ON CLICKTOPAY.Cliente (cDocumento);": "INDICE_COLUMNA_NO_EXISTE",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona_INC01 ON CLICKTOPAY.Cliente (cCodPersona) INCLUDE (cTelefono);":
                "INDICE_COLUMNA_NO_EXISTE",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cObservacion ON CLICKTOPAY.Cliente (cObservacion);": "INDICE_COLUMNA_NO_INDEXABLE",
            "CREATE NONCLUSTERED INDEX IXN_Pais_cNombre ON CLICKTOPAY.Pais (cNombre);": "INDICE_TABLA_EXISTENTE",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_nClienteId ON CLICKTOPAY.Cliente (nClienteId);": "INDICE_DUPLICADO",
        }
        for indices, regla in casos.items():
            with self.subTest(indices=indices):
                self.assertEqual([r for r, _ in reglas(indices)], [regla])

    def test_unique_clustered_se_pide_declarar_la_pk(self):
        indices = "CREATE UNIQUE CLUSTERED INDEX IXU_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);"
        # La tabla ya tiene su PK como CONSTRAINT PRIMARY KEY CLUSTERED: un segundo clustered no se crea.
        hallazgo = verificar_indices(indices, TABLA)[0]
        self.assertEqual((hallazgo.regla, hallazgo.severidad.value), ("INDICE_SEGUNDO_CLUSTERED", "critico"))
        self.assertIn("ya tiene su clave primaria nClienteId declarada como CONSTRAINT PRIMARY KEY CLUSTERED",
                      hallazgo.mensaje)
        self.assertIn("Créelo como NONCLUSTERED (ej.: IXUN_Cliente_cCodPersona)", hallazgo.mensaje)
        # Repite la PK: se retira, sin además marcarlo como duplicado.
        repite = "CREATE UNIQUE CLUSTERED INDEX IXU_Cliente_nClienteId ON CLICKTOPAY.Cliente (nClienteId);"
        self.assertEqual(reglas(repite), [("INDICE_CLUSTERED_CON_PK", 1)])
        self.assertIn("repite la clave primaria nClienteId", mensaje(repite))
        # Sin PK: si es sobre la columna IDENTITY(1,1), se retira y se declara la PK como CONSTRAINT.
        sin_pk = "CREATE TABLE dbo.Cliente (nClienteId INT IDENTITY(1,1) NOT NULL, cCodigo VARCHAR(10));"
        sobre_identidad = "CREATE UNIQUE CLUSTERED INDEX IXU_Cliente_nClienteId ON dbo.Cliente (nClienteId);"
        self.assertIn(
            "que ya tiene IDENTITY(1,1). Se recomienda retirar dicho índice y declarar nClienteId como clave primaria "
            "mediante un CONSTRAINT PRIMARY KEY CLUSTERED", mensaje(sobre_identidad, sin_pk))
        # Sin PK y sobre otra columna: NONCLUSTERED y PK como CONSTRAINT.
        otra = "CREATE CLUSTERED INDEX IX_Cliente_cCodigo ON dbo.Cliente (cCodigo);"
        self.assertIn("crearlo como NONCLUSTERED (ej.: IXN_Cliente_cCodigo) y declarar nClienteId como clave primaria",
                      mensaje(otra, sin_pk))

    def test_columna_repetida_en_el_indice(self):
        repetida = "CREATE NONCLUSTERED INDEX IXN_Movimiento_nPersonaId\nON dbo.Movimiento (nPersonaId, nPersonaId);"
        hallazgos = verificar_indices(repetida, "")
        repetidas = [h for h in hallazgos if h.regla == "INDICE_COLUMNA_REPETIDA"]
        self.assertEqual([(h.linea, h.severidad.value) for h in repetidas], [(2, "critico")])
        self.assertIn("la columna nPersonaId aparece dos veces", repetidas[0].mensaje)
        # El nombre no se marca: la columna repetida cuenta una sola vez.
        self.assertNotIn("INDICE_NOMBRE_NO_ESTANDAR", {h.regla for h in hallazgos})

        en_include = "CREATE INDEX IXN_Cliente_cCodPersona_INC01 ON CLICKTOPAY.Cliente (cCodPersona) INCLUDE (cCodPersona, dRegistro);"
        self.assertEqual(reglas(en_include), [("INDICE_COLUMNA_REPETIDA", 1)])
        self.assertIn("está a la vez entre las columnas del índice IXN_Cliente_cCodPersona_INC01 y en su INCLUDE", mensaje(en_include))

    def test_qa_sintaxis_con_mensajes_claros(self):
        con_esquema = "CREATE INDEX dbo.IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);"
        self.assertEqual(reglas(con_esquema), [("INDICE_SINTAXIS_INVALIDA", 1)])
        self.assertIn("incluye el esquema (dbo)", mensaje(con_esquema))
        sin_coma = "CREATE INDEX IXN_Cliente_cCodPersona_dRegistro ON CLICKTOPAY.Cliente (cCodPersona dRegistro);"
        self.assertEqual(reglas(sin_coma), [("INDICE_SINTAXIS_INVALIDA", 1)])
        self.assertIn("le falta la coma entre las columnas cCodPersona y dRegistro", mensaje(sin_coma))

    def test_qa_instrucciones_que_no_son_indices(self):
        for texto, frase in (("DROP INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente;", "un DROP INDEX"),
                             ("SELECT 1;", "no es un CREATE INDEX (SELECT 1...)"),
                             ("CREATE INDX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);", "no es un CREATE INDEX")):
            with self.subTest(texto=texto):
                self.assertEqual(reglas(texto), [("INDICE_SENTENCIA_NO_RECONOCIDA", 1)])
                self.assertIn(frase, mensaje(texto))
        envuelto = ("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IXN_Cliente_cCodPersona')\n"
                    "    CREATE INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);")
        self.assertEqual(reglas(envuelto), [])

    def test_qa_duplicado_de_la_pk_pide_eliminar_el_indice(self):
        indices = "CREATE NONCLUSTERED INDEX IXN_Cliente_nClienteId ON CLICKTOPAY.Cliente (nClienteId);"
        self.assertIn("eliminar el índice IXN_Cliente_nClienteId, ya que la clave primaria ya cubre esas columnas",
                      mensaje(indices))

    def test_tipos_no_indexables_segun_donde_van(self):
        tabla = ("CREATE TABLE dbo.Persona (nPersonaId INT IDENTITY(1,1) NOT NULL, cObs VARCHAR(MAX) NOT NULL, "
                 "cNota NTEXT NOT NULL, xDatos XML NULL, nEstado INT NOT NULL, "
                 "CONSTRAINT PK_Persona PRIMARY KEY CLUSTERED (nPersonaId));")

        def aviso(indices):
            return next((h.mensaje for h in verificar_indices(indices, tabla) if h.regla == "INDICE_COLUMNA_NO_INDEXABLE"), None)

        # (N)VARCHAR(MAX), VARBINARY(MAX) y XML: no como clave, sí en el INCLUDE.
        self.assertEqual(
            aviso("CREATE INDEX IXN_Persona_cObs ON dbo.Persona (cObs);"),
            "Se identificó que la columna cObs, de tipo VARCHAR(MAX), forma parte de las claves del índice, lo cual "
            "no está permitido en SQL Server. Se recomienda cambiar su tipo de dato a VARCHAR(n) o retirarla de las "
            "claves del índice y agregarla mediante INCLUDE.",
        )
        # XML no tiene una longitud fija que proponer: solo se lleva al INCLUDE.
        self.assertNotIn("cambiar su tipo de dato", aviso("CREATE INDEX IXN_Persona_xDatos ON dbo.Persona (xDatos);"))
        for incluida in ("cObs", "xDatos"):
            with self.subTest(incluida=incluida):
                self.assertIsNone(aviso(f"CREATE INDEX IXN_Persona_nEstado_INC01 ON dbo.Persona (nEstado) INCLUDE ({incluida});"))
        # TEXT, NTEXT, IMAGE: ni siquiera en el INCLUDE.
        self.assertIn("ni siquiera mediante INCLUDE",
                      aviso("CREATE INDEX IXN_Persona_nEstado_INC01 ON dbo.Persona (nEstado) INCLUDE (cNota);"))

    def test_descripcion_usada_como_identificador(self):
        tabla = "CREATE TABLE dbo.TB_cliente_datos (id INT, cDescripcion VARCHAR(MAX), cDireccion VARCHAR(200));"
        unico = "CREATE UNIQUE CLUSTERED INDEX IXU_TB_cliente_datos_cDescripcion ON dbo.TB_cliente_datos (cDescripcion);"
        hallazgos = {h.regla: h for h in verificar_indices(unico, tabla)}
        clustered = hallazgos["INDICE_CLUSTERED_DESCRIPTIVO"]
        self.assertEqual(clustered.severidad.value, "alto")
        self.assertEqual(
            clustered.mensaje,
            "Se identificó que el índice IXU_TB_cliente_datos_cDescripcion utiliza la columna descriptiva "
            "cDescripcion como clave clustered. Se recomienda retirar dicho índice y definir nClienteDatosId "
            "como clave primaria mediante un CONSTRAINT PRIMARY KEY CLUSTERED.",
        )
        self.assertIn("INDICE_COLUMNA_NO_INDEXABLE", hallazgos)  # además falla por VARCHAR(MAX)
        # Un solo mensaje para ese índice: ni «descripción como identificador», ni «descriptiva», ni el de clúster.
        for repetida in ("INDICE_IDENTIFICA_POR_DESCRIPCION", "INDICE_COLUMNA_DESCRIPTIVA", "INDICE_CLUSTERED_CON_PK"):
            self.assertNotIn(repetida, hallazgos)

        con_pk = TABLA.replace("cObservacion VARCHAR(MAX)", "cObservacion VARCHAR(200)")
        unique_nc = "CREATE UNIQUE NONCLUSTERED INDEX IXUN_Cliente_cObservacion ON CLICKTOPAY.Cliente (cObservacion);"
        self.assertIn("(nClienteId)", next(h.mensaje for h in verificar_indices(unique_nc, con_pk)
                                           if h.regla == "INDICE_IDENTIFICA_POR_DESCRIPCION"))
        # Un índice NONCLUSTERED común sobre una descripción es «columna descriptiva» (alto).
        normal = "CREATE NONCLUSTERED INDEX IXN_TB_cliente_datos_cDireccion ON dbo.TB_cliente_datos (cDireccion);"
        hallazgos_normal = verificar_indices(normal, tabla)
        self.assertEqual([(h.regla, h.severidad.value) for h in hallazgos_normal],
                         [("INDICE_COLUMNA_DESCRIPTIVA", "alto")])

    def test_columnas_descriptivas_en_el_indice(self):
        persona = ("CREATE TABLE DBO.PERSONA (CPERSCOD VARCHAR(20) NOT NULL, CPERSDIRECCION VARCHAR(200) NOT NULL, "
                   "cDescripcion VARCHAR(300) NOT NULL, nEstado INT NOT NULL, dRegistro DATETIME NOT NULL);")
        clave = "CREATE INDEX IXN_PERSONA_CPERSCOD_CPERSDIRECCION ON DBO.PERSONA (CPERSCOD, CPERSDIRECCION);"
        self.assertEqual(reglas(clave, persona), [("INDICE_COLUMNA_DESCRIPTIVA", 1)])
        self.assertIn("utiliza la columna descriptiva CPERSDIRECCION (dirección)", mensaje(clave, persona))
        incluida = "CREATE INDEX IXN_PERSONA_nEstado_INC01 ON DBO.PERSONA (nEstado) INCLUDE (cDescripcion);"
        self.assertIn("utiliza en su INCLUDE la columna descriptiva cDescripcion", mensaje(incluida, persona))
        util = "CREATE INDEX IXN_PERSONA_nEstado_dRegistro ON DBO.PERSONA (nEstado, dRegistro);"
        self.assertEqual(reglas(util, persona), [])

    def test_columnas_descriptivas_sin_prefijo_en_tablas_antiguas(self):
        for columna, que in (("copinion", "opinión"), ("opinion", "opinión"), ("CPERSOPINION", "opinión"),
                             ("cComentarios", "comentario"), ("cTextoLibre", "texto"), ("Address", "dirección")):
            with self.subTest(columna=columna):
                indices = f"CREATE NONCLUSTERED INDEX IXN_Movimiento_{columna}\nON dbo.Movimiento ({columna} DESC);"
                hallazgo = next(h for h in verificar_indices(indices, "") if h.regla == "INDICE_COLUMNA_DESCRIPTIVA")
                self.assertIn(f"columna descriptiva {columna} ({que})", hallazgo.mensaje)
        for columna in ("nPersonaId", "cCodPersona", "dFecha", "nEstado", "cContexto"):
            with self.subTest(columna=columna):
                indices = f"CREATE NONCLUSTERED INDEX IXN_Movimiento_{columna} ON dbo.Movimiento ({columna});"
                self.assertNotIn("INDICE_COLUMNA_DESCRIPTIVA", {h.regla for h in verificar_indices(indices, "")})

    def test_ningun_indice_puede_ser_clustered(self):
        # La PK siempre es CLUSTERED: aunque el script la declare NONCLUSTERED o no la tenga,
        # un índice CLUSTERED adicional se pide como NONCLUSTERED.
        indices = "CREATE CLUSTERED INDEX IX_Cliente_dRegistro ON CLICKTOPAY.Cliente (dRegistro);"
        for tabla in (TABLA.replace("PRIMARY KEY CLUSTERED", "PRIMARY KEY NONCLUSTERED"),
                      TABLA.replace(",\n    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)", ""), ""):
            with self.subTest(tabla=tabla[-60:]):
                self.assertIn(("INDICE_CLUSTERED_CON_PK", 1), reglas(indices, tabla))
                self.assertIn("(ej.: IXN_Cliente_dRegistro)", mensaje(indices, tabla))

    def test_indice_duplicado_entre_indices(self):
        indices = ("CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);\n"
                   "CREATE UNIQUE NONCLUSTERED INDEX IXUN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);")
        self.assertEqual(reglas(indices), [("INDICE_DUPLICADO", 2)])

    def test_indice_sobre_tabla_existente_pide_validar(self):
        # La tabla no se crea en el script (ALTER, vacío u otra tabla): se valida la estructura
        # y se pide validar si la tabla de verdad necesita el índice.
        indices = "CREATE NONCLUSTERED INDEX IXN_Cliente_cDocumento ON CLICKTOPAY.Cliente (cDocumento);"
        for tabla in ("ALTER TABLE CLICKTOPAY.Cliente ADD cX VARCHAR(5) NULL;", ""):
            with self.subTest(tabla=tabla):
                self.assertEqual(reglas(indices, tabla), [("INDICE_TABLA_EXISTENTE", 1)])
                self.assertIn("que ya existe (su CREATE TABLE no está en el script de la tabla)", mensaje(indices, tabla))
                self.assertIn("validar que la tabla realmente necesite este índice", mensaje(indices, tabla))
        con_errores = "CREATE INDEX idx ON Cliente (cX);"
        self.assertEqual([r for r, _ in reglas(con_errores, "")],
                         ["INDICE_PREFIJO_INVALIDO", "INDICE_SIN_ESQUEMA", "INDICE_TABLA_EXISTENTE"])

    def test_nombre_sugerido_segun_si_la_tabla_es_nueva(self):
        indice = "CREATE NONCLUSTERED INDEX idx_cliente ON dbo.TB_cliente_datos (nombre89);"
        nueva = (
            "CREATE TABLE dbo.TB_cliente_datos (\n nClienteDatosId INT IDENTITY(1,1) NOT NULL,\n"
            " nombre89 VARCHAR(50) NOT NULL,\n CONSTRAINT PK_x PRIMARY KEY CLUSTERED (nClienteDatosId)\n);"
        )
        # Tabla nueva: también se le pide corregir su nombre, así que el índice usa el estándar.
        self.assertIn("por ejemplo: IXN_ClienteDatos_nombre89", mensaje(indice, nueva))
        # Tabla existente: no se va a renombrar, así que el índice usa su nombre real.
        self.assertIn("por ejemplo: IXN_TB_cliente_datos_nombre89", mensaje(indice, ""))
        # Con el nombre real de la tabla también es válido.
        real = "CREATE NONCLUSTERED INDEX IXN_TB_cliente_datos_nombre89 ON dbo.TB_cliente_datos (nombre89);"
        self.assertEqual(reglas(real, nueva), [])

    def test_mensajes_cortos_de_nombre_y_esquema(self):
        sin_esquema = "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON Cliente (cCodPersona);"
        self.assertEqual(
            mensaje(sin_esquema),
            "El índice IXN_Cliente_cCodPersona indica la tabla Cliente sin su esquema. Se recomienda especificar "
            "el esquema de la tabla al crear el índice, incluso si pertenece a dbo (ejemplo: ON dbo.Cliente), "
            "para evitar referencias incorrectas.",
        )

    def test_indice_duplicado_no_sugiere_renombrarlo(self):
        # Renombrar IXN_Cliente_cCodPersona2 como IXN_Cliente_cCodPersona chocaría con el índice que ya existe.
        indices = (
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);\n"
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona2 ON CLICKTOPAY.Cliente (cCodPersona);"
        )
        self.assertEqual(reglas(indices), [("INDICE_DUPLICADO", 2)])
        self.assertIn("eliminar uno de los dos", mensaje(indices))

    def test_duplicado_en_la_misma_linea_conserva_las_demas_observaciones(self):
        indices = (
            "CREATE NONCLUSTERED INDEX IXN_Cliente_Persona ON CLICKTOPAY.Cliente (cCodPersona); "
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);"
        )
        self.assertEqual({r for r, _ in reglas(indices)}, {"INDICE_NOMBRE_NO_ESTANDAR", "INDICE_DUPLICADO"})


if __name__ == "__main__":
    unittest.main()
