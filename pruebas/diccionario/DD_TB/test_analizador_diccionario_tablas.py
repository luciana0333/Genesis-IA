import unittest

from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from pruebas.diccionario.DD_TB.casos.test_caso1_perfecto import TABLA as TABLA_CASO_1, DICCIONARIO as DICCIONARIO_CASO_1
from pruebas.diccionario.DD_TB.casos.test_caso2_tabla_sin_descripcion import TABLA as TABLA_CASO_2, DICCIONARIO as DICCIONARIO_CASO_2
from pruebas.diccionario.DD_TB.casos.test_caso3_columnas_faltantes import TABLA as TABLA_CASO_3, DICCIONARIO as DICCIONARIO_CASO_3
from pruebas.diccionario.DD_TB.casos.test_caso4_metadata_inconsistente import TABLA as TABLA_CASO_4, DICCIONARIO as DICCIONARIO_CASO_4
from pruebas.diccionario.DD_TB.casos.test_caso5_alter import ALTER_ADD, ALTER_COLUMN, DICCIONARIO_TABLA, DICCIONARIO_EXISTENTE as DICCIONARIO_ALTER_EXISTENTE


TABLA_OK = """
CREATE TABLE CLICKTOPAY.ProcesoEjecucion (
    nProcesoEjecucionId INT PRIMARY KEY IDENTITY(1,1) NOT NULL,
    nTipoProceso INT DEFAULT 1 NOT NULL,
    nEstado INT DEFAULT 1 NOT NULL
)
"""

DICCIONARIO_OK = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla para registrar procesos',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'PROCESOEJECUCION'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Identificador unico',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'PROCESOEJECUCION',
@level2type=N'COLUMN',
@level2name=N'NPROCESOEJECUCIONID'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tipo de proceso',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'PROCESOEJECUCION',
@level2type=N'COLUMN',
@level2name=N'NTIPOPROCESO'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Estado del proceso',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'PROCESOEJECUCION',
@level2type=N'COLUMN',
@level2name=N'NESTADO'
GO
"""

TABLA_FALTA_COLUMNA = """
CREATE TABLE CLICKTOPAY.Cliente (
    nClienteId INT PRIMARY KEY IDENTITY(1,1) NOT NULL,
    cCodPersona VARCHAR(20) NOT NULL,
    cCorreoElectronico VARCHAR(64) NOT NULL
)
"""

DICCIONARIO_FALTA_COLUMNA = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla de clientes',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'CLIENTE'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Identificador unico',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'CLIENTE',
@level2type=N'COLUMN',
@level2name=N'NCLIENTEID'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Codigo de persona',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'CLIENTE',
@level2type=N'COLUMN',
@level2name=N'CCODPERSONA'
GO
"""

ALTER_TABLE_NUEVA_COLUMNA = """
ALTER TABLE CLICKTOPAY.Cliente
ADD cCelular VARCHAR(20)
"""

DICCIONARIO_SIN_NUEVA_COLUMNA = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla de clientes',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'CLIENTE'
GO
"""

ALTER_TABLE_SIN_DICCIONARIO = """
ALTER TABLE CLICKTOPAY.Cliente
ADD cCelular VARCHAR(20)
"""

ALTER_TABLE_CAMBIO_TIPO = """
ALTER TABLE CLICKTOPAY.Cliente
ALTER COLUMN cCodPersona VARCHAR(30)
"""

DICCIONARIO_EXISTENTE = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla de clientes',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'CLIENTE'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Codigo de persona',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'CLIENTE',
@level2type=N'COLUMN',
@level2name=N'CCODPERSONA'
GO
"""

TABLA_CON_CORCHETES_SIN_COLUMNAS_DOCUMENTADAS = """
CREATE TABLE [CLICKTOPAY].[Cliente] (
    [nClienteId] INT,
    [cCodPersona] VARCHAR(20),
    [cCorreoElectronico] VARCHAR(64),
    [cCelular] VARCHAR(20),
    [cEstado] INT
)
"""

DICCIONARIO_SOLO_TABLA_CON_CORCHETES = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla de clientes',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'Cliente'
GO
"""


class TestDiccionarioTablas(unittest.TestCase):
    def test_tabla_documentada_completa(self):
        hallazgos = verificar_diccionario_tablas(TABLA_OK, DICCIONARIO_OK)
        self.assertEqual(len(hallazgos), 0)

    def test_falta_columna_documentada(self):
        hallazgos = verificar_diccionario_tablas(TABLA_FALTA_COLUMNA, DICCIONARIO_FALTA_COLUMNA)
        self.assertGreaterEqual(len(hallazgos), 1)

    def test_alter_que_agrega_columna_sin_documentacion(self):
        hallazgos = verificar_diccionario_tablas(ALTER_TABLE_NUEVA_COLUMNA, DICCIONARIO_SIN_NUEVA_COLUMNA)
        self.assertGreaterEqual(len(hallazgos), 1)

    def test_alter_add_sin_diccionario_detecta_la_columna_agregada(self):
        hallazgos = verificar_diccionario_tablas(ALTER_TABLE_SIN_DICCIONARIO, "")
        reglas = [h.regla for h in hallazgos]
        mensajes = [h.mensaje for h in hallazgos]
        self.assertIn("ALTER_SIN_DICCIONARIO", reglas)
        self.assertIn("COLUMNA_FALTANTE", reglas)
        self.assertTrue(any("ccelular" in mensaje.lower() for mensaje in mensajes))

    def test_alter_que_cambia_tipo_de_columna_existente_no_falla(self):
        hallazgos = verificar_diccionario_tablas(ALTER_TABLE_CAMBIO_TIPO, DICCIONARIO_EXISTENTE)
        self.assertEqual(len(hallazgos), 0)

    def test_create_con_identificadores_entre_corchetes_detecta_columnas_faltantes(self):
        hallazgos = verificar_diccionario_tablas(
            TABLA_CON_CORCHETES_SIN_COLUMNAS_DOCUMENTADAS,
            DICCIONARIO_SOLO_TABLA_CON_CORCHETES,
        )
        columnas_faltantes = [h for h in hallazgos if h.regla == "COLUMNA_FALTANTE"]
        self.assertEqual(len(columnas_faltantes), 5)

    def test_casos_organizados_del_diccionario_de_tablas(self):
        casos = [
            (TABLA_CASO_1, DICCIONARIO_CASO_1, set()),
            (TABLA_CASO_2, DICCIONARIO_CASO_2, {"TABLA_SIN_DESCRIPCION"}),
            (TABLA_CASO_3, DICCIONARIO_CASO_3, {"COLUMNA_FALTANTE"}),
            (TABLA_CASO_4, DICCIONARIO_CASO_4, {
                "ESQUEMA_NO_COINCIDE",
                "DESCRIPCION_COLUMNA_VACIA",
                "VALOR_SIN_COMILLAS",
            }),
        ]

        for tabla, diccionario, reglas_esperadas in casos:
            with self.subTest(tabla=tabla.strip().splitlines()[0]):
                hallazgos = verificar_diccionario_tablas(tabla, diccionario)
                self.assertEqual({h.regla for h in hallazgos}, reglas_esperadas)

        hallazgos_add = verificar_diccionario_tablas(ALTER_ADD, DICCIONARIO_TABLA)
        self.assertEqual(
            {h.regla for h in hallazgos_add},
                {"COLUMNA_FALTANTE"},
        )

        hallazgos_alter = verificar_diccionario_tablas(ALTER_COLUMN, DICCIONARIO_ALTER_EXISTENTE)
        self.assertEqual(hallazgos_alter, [])


if __name__ == "__main__":
    unittest.main()
