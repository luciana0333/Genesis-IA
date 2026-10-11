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
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona_dRegistro_INC1 ON CLICKTOPAY.Cliente "
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
        self.assertIn("(ej.: IXN_Cliente_cCodPersona_INC2)", mensaje(sin_inc))

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
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona_INC1 ON CLICKTOPAY.Cliente (cCodPersona) INCLUDE (cTelefono);":
                "INDICE_COLUMNA_NO_EXISTE",
            "CREATE NONCLUSTERED INDEX IXN_Cliente_cObservacion ON CLICKTOPAY.Cliente (cObservacion);": "INDICE_COLUMNA_NO_INDEXABLE",
            "CREATE NONCLUSTERED INDEX IXN_Pais_cNombre ON CLICKTOPAY.Pais (cNombre);": "INDICE_OTRA_TABLA",
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

    def test_indice_duplicado_entre_indices(self):
        indices = ("CREATE NONCLUSTERED INDEX IXN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);\n"
                   "CREATE UNIQUE NONCLUSTERED INDEX IXUN_Cliente_cCodPersona ON CLICKTOPAY.Cliente (cCodPersona);")
        self.assertEqual(reglas(indices), [("INDICE_DUPLICADO", 2)])

    def test_sin_tabla_en_el_script_solo_revisa_sintaxis_y_nombre(self):
        indices = "CREATE NONCLUSTERED INDEX IXN_Cliente_cDocumento ON CLICKTOPAY.Cliente (cDocumento);"
        self.assertEqual(reglas(indices, tabla="ALTER TABLE CLICKTOPAY.Cliente ADD cX VARCHAR(5) NULL;"), [])


if __name__ == "__main__":
    unittest.main()
