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
            "CREATE NONCLUSTERED INDEX IX_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);": "IXN_Cliente_cCodPersona",
            "CREATE INDEX idx1 ON CLICKTOPAY.Cliente (cCodPersona);": "IXN_Cliente_cCodPersona",
            "CREATE UNIQUE INDEX IXN_Cliente_cCorreoElectronico ON CLICKTOPAY.Cliente (cCorreoElectronico);":
                "IXUN_Cliente_cCorreoElectronico",
        }
        for indices, sugerido in casos.items():
            with self.subTest(indices=indices):
                self.assertEqual(reglas(indices), [("INDICE_PREFIJO_INVALIDO", 1)])
                self.assertIn(f"(ej.: {sugerido})", mensaje(indices))

    def test_nombre_con_tabla_campos_e_inc(self):
        campos = "CREATE NONCLUSTERED INDEX IXN_Cliente_Codigo ON CLICKTOPAY.Cliente (cCodPersona);"
        self.assertEqual(reglas(campos), [("INDICE_NOMBRE_NO_ESTANDAR", 1)])
        sin_inc = ("CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona) "
                   "INCLUDE (dRegistro, cCorreoElectronico);")
        self.assertIn("(ej.: IXN_Cliente_cCodPersona_INC02)", mensaje(sin_inc))

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
        self.assertIn("(ej.: IXN_PERSONA_CPERSCOD_NPERSCLASIFICACION_CPERSESTADO_INC02)", mensaje(inc_un_digito, persona))

    def test_sintaxis(self):
        casos = {
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona (cCodPersona);": "falta la tabla",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente;": "faltan las columnas",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona;": "paréntesis que cierra",
            "CREATE NONCLUSTERED INDEX ON CLICKTOPAY.Cliente (cCodPersona);": "falta el nombre del índice",
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

    def test_unique_clustered_con_pk_identidad_se_pide_nonclustered(self):
        indices = "CREATE UNIQUE CLUSTERED INDEX IXU_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);"
        hallazgo = verificar_indices(indices, TABLA)[0]
        self.assertEqual((hallazgo.regla, hallazgo.severidad.value), ("INDICE_CLUSTERED_CON_PK", "medio"))
        self.assertIn("definirlo como UNIQUE NONCLUSTERED", hallazgo.mensaje)
        self.assertIn("(ej.: IXUN_Cliente_cCodPersona)", hallazgo.mensaje)

    def test_columna_repetida_en_el_indice(self):
        repetida = "CREATE NONCLUSTERED INDEX IXN_Movimiento_nPersonaId\nON dbo.Movimiento (nPersonaId, nPersonaId);"
        hallazgos = verificar_indices(repetida, "")
        repetidas = [h for h in hallazgos if h.regla == "INDICE_COLUMNA_REPETIDA"]
        self.assertEqual([(h.linea, h.severidad.value) for h in repetidas], [(2, "critico")])
        self.assertIn("repite la columna nPersonaId", repetidas[0].mensaje)
        # El nombre no se marca: la columna repetida cuenta una sola vez.
        self.assertNotIn("INDICE_NOMBRE_NO_ESTANDAR", {h.regla for h in hallazgos})

        en_include = "CREATE INDEX IXN_Cliente_cCodPersona_INC01 ON CLICKTOPAY.Cliente (cCodPersona) INCLUDE (cCodPersona, dRegistro);"
        self.assertEqual(reglas(en_include), [("INDICE_COLUMNA_REPETIDA", 1)])
        self.assertIn("en el INCLUDE la columna cCodPersona, que ya es columna clave", mensaje(en_include))

    def test_descripcion_usada_como_identificador(self):
        tabla = "CREATE TABLE dbo.TB_cliente_datos (id INT, cDescripcion VARCHAR(MAX), cDireccion VARCHAR(200));"
        unico = "CREATE UNIQUE CLUSTERED INDEX IXU_TB_cliente_datos_cDescripcion ON dbo.TB_cliente_datos (cDescripcion);"
        hallazgos = {h.regla: h for h in verificar_indices(unico, tabla)}
        identifica = hallazgos["INDICE_IDENTIFICA_POR_DESCRIPCION"]
        self.assertEqual(identifica.severidad.value, "alto")
        self.assertIn("para identificar los registros", identifica.mensaje)
        self.assertIn("clave primaria identidad (nClienteDatosId)", identifica.mensaje)
        self.assertIn("INDICE_COLUMNA_NO_INDEXABLE", hallazgos)  # además falla por VARCHAR(MAX)
        self.assertNotIn("INDICE_COLUMNA_DESCRIPTIVA", hallazgos)  # no se repite como «descriptiva»

        con_pk = TABLA.replace("cObservacion VARCHAR(MAX)", "cObservacion VARCHAR(200)")
        unique_nc = "CREATE UNIQUE NONCLUSTERED INDEX IXUN_Cliente_cObservacion ON CLICKTOPAY.Cliente (cObservacion);"
        self.assertIn("(nClienteId)", next(h.mensaje for h in verificar_indices(unique_nc, con_pk)
                                           if h.regla == "INDICE_IDENTIFICA_POR_DESCRIPCION"))
        # Un índice NONCLUSTERED común sobre una descripción solo es «columna descriptiva» (medio).
        normal = "CREATE NONCLUSTERED INDEX IXN_TB_cliente_datos_cDireccion ON dbo.TB_cliente_datos (cDireccion);"
        self.assertEqual([h.regla for h in verificar_indices(normal, tabla)], ["INDICE_COLUMNA_DESCRIPTIVA"])

    def test_columnas_descriptivas_en_el_indice(self):
        persona = ("CREATE TABLE DBO.PERSONA (CPERSCOD VARCHAR(20) NOT NULL, CPERSDIRECCION VARCHAR(200) NOT NULL, "
                   "cDescripcion VARCHAR(300) NOT NULL, nEstado INT NOT NULL, dRegistro DATETIME NOT NULL);")
        clave = "CREATE INDEX IXN_PERSONA_CPERSCOD_CPERSDIRECCION ON DBO.PERSONA (CPERSCOD, CPERSDIRECCION);"
        self.assertEqual(reglas(clave, persona), [("INDICE_COLUMNA_DESCRIPTIVA", 1)])
        self.assertIn("como clave la columna CPERSDIRECCION, que guarda texto descriptivo (dirección)", mensaje(clave, persona))
        incluida = "CREATE INDEX IXN_PERSONA_nEstado_INC01 ON DBO.PERSONA (nEstado) INCLUDE (cDescripcion);"
        self.assertIn("en el INCLUDE la columna cDescripcion", mensaje(incluida, persona))
        util = "CREATE INDEX IXN_PERSONA_nEstado_dRegistro ON DBO.PERSONA (nEstado, dRegistro);"
        self.assertEqual(reglas(util, persona), [])

    def test_columnas_descriptivas_sin_prefijo_en_tablas_antiguas(self):
        for columna, que in (("copinion", "opinión"), ("opinion", "opinión"), ("CPERSOPINION", "opinión"),
                             ("cComentarios", "comentario"), ("cTextoLibre", "texto"), ("Address", "dirección")):
            with self.subTest(columna=columna):
                indices = f"CREATE NONCLUSTERED INDEX IXN_Movimiento_{columna}\nON dbo.Movimiento ({columna} DESC);"
                hallazgo = next(h for h in verificar_indices(indices, "") if h.regla == "INDICE_COLUMNA_DESCRIPTIVA")
                self.assertIn(f"texto descriptivo ({que})", hallazgo.mensaje)
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
                self.assertIn("que ya existe (no se crea en este script)", mensaje(indices, tabla))
                self.assertIn("validar si la tabla realmente necesita este índice", mensaje(indices, tabla))
        con_errores = "CREATE INDEX idx ON Cliente (cX);"
        self.assertEqual([r for r, _ in reglas(con_errores, "")],
                         ["INDICE_PREFIJO_INVALIDO", "INDICE_SIN_ESQUEMA", "INDICE_TABLA_EXISTENTE"])


if __name__ == "__main__":
    unittest.main()
