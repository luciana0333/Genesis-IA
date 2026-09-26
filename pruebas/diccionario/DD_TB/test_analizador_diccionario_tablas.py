import inspect
import re
import unittest
from dataclasses import replace

from app.analizadores import analizador_diccionario_tablas
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.modelos.hallazgo import Severidad
from app.reglas.reglas_diccionario_tablas import REGLAS_DICCIONARIO_TABLAS
from pruebas.diccionario.DD_TB.casos.test_caso1_perfecto import TABLA as TABLA_CASO_1, DICCIONARIO as DICCIONARIO_CASO_1
from pruebas.diccionario.DD_TB.casos.test_caso2_tabla_sin_descripcion import TABLA as TABLA_CASO_2, DICCIONARIO as DICCIONARIO_CASO_2
from pruebas.diccionario.DD_TB.casos.test_caso3_columnas_faltantes import TABLA as TABLA_CASO_3, DICCIONARIO as DICCIONARIO_CASO_3
from pruebas.diccionario.DD_TB.casos.test_caso4_metadata_inconsistente import TABLA as TABLA_CASO_4, DICCIONARIO as DICCIONARIO_CASO_4
from pruebas.diccionario.DD_TB.casos.test_caso5_alter import ALTER_ADD, ALTER_COLUMN, DICCIONARIO_TABLA, DICCIONARIO_EXISTENTE as DICCIONARIO_ALTER_EXISTENTE
from pruebas.diccionario.DD_TB.casos import test_caso6_separadores as caso6


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


class TestCatalogoDiccionarioTablas(unittest.TestCase):
    """El catálogo de reglas define la severidad y si la regla está activa."""

    def test_tabla_y_columna_sin_descripcion_son_alto(self):
        diccionario_vacio_de_columnas = DICCIONARIO_SOLO_TABLA_CON_CORCHETES.replace(
            "@value=N'Tabla de clientes'", "@value=N''"
        )
        hallazgos = verificar_diccionario_tablas(
            TABLA_CON_CORCHETES_SIN_COLUMNAS_DOCUMENTADAS, diccionario_vacio_de_columnas
        )
        severidades = {h.regla: h.severidad for h in hallazgos}
        self.assertEqual(severidades["TABLA_SIN_DESCRIPCION"], Severidad.ALTO)
        self.assertEqual(severidades["COLUMNA_FALTANTE"], Severidad.ALTO)

        hallazgos_caso4 = verificar_diccionario_tablas(TABLA_CASO_4, DICCIONARIO_CASO_4)
        vacia = next(h for h in hallazgos_caso4 if h.regla == "DESCRIPCION_COLUMNA_VACIA")
        self.assertEqual(vacia.severidad, Severidad.ALTO)

    def test_toda_regla_emitida_esta_en_el_catalogo(self):
        codigo = inspect.getsource(analizador_diccionario_tablas)
        reglas_en_codigo = set(re.findall(r'_hallazgo\(\s*[^,]+?,\s*"([A-Z_]+)"', codigo))
        self.assertTrue(reglas_en_codigo)
        self.assertEqual(reglas_en_codigo - set(REGLAS_DICCIONARIO_TABLAS), set())

    def test_nombres_sin_comillas_no_se_reportan(self):
        diccionario = caso6.diccionario_correcto(";").replace("N'dbo'", "dbo").replace(
            "N'TB_SolicitudArchivos'", "TB_SolicitudArchivos"
        )
        self.assertEqual(verificar_diccionario_tablas(caso6.TABLA, diccionario), [])

    def test_mensajes_directos_de_tabla_sin_descripcion(self):
        solo_columnas = "\n".join(
            caso6._sentencia(col, desc) + ";" for col, desc in caso6._DESCRIPCIONES if col
        )
        faltante = verificar_diccionario_tablas(caso6.TABLA, solo_columnas)
        self.assertEqual([h.regla for h in faltante], ["TABLA_SIN_DESCRIPCION"])
        self.assertIn("Falta documentar la tabla creada dbo.TB_SolicitudArchivos", faltante[0].mensaje)

        vacia = verificar_diccionario_tablas(
            caso6.TABLA,
            caso6.diccionario_correcto(";").replace(
                "Archivos adjuntos registrados para cada solicitud", ""
            ),
        )
        self.assertEqual([h.regla for h in vacia], ["TABLA_SIN_DESCRIPCION"])
        self.assertIn("está vacía", vacia[0].mensaje)
        self.assertGreater(vacia[0].linea, 0)

    def test_regla_desactivada_no_se_reporta(self):
        original = REGLAS_DICCIONARIO_TABLAS["COLUMNA_FALTANTE"]
        REGLAS_DICCIONARIO_TABLAS["COLUMNA_FALTANTE"] = replace(original, activo=False)
        try:
            hallazgos = verificar_diccionario_tablas(TABLA_FALTA_COLUMNA, DICCIONARIO_FALTA_COLUMNA)
        finally:
            REGLAS_DICCIONARIO_TABLAS["COLUMNA_FALTANTE"] = original
        self.assertNotIn("COLUMNA_FALTANTE", {h.regla for h in hallazgos})


class TestDiccionarioTablasSinDependerDeGO(unittest.TestCase):
    """El diccionario se lee igual con GO, con ";", con ambos o sin nada."""

    def test_diccionario_correcto_con_cualquier_separador(self):
        for nombre, terminador in caso6.SEPARADORES.items():
            with self.subTest(separador=nombre):
                hallazgos = verificar_diccionario_tablas(caso6.TABLA, caso6.diccionario_correcto(terminador))
                self.assertEqual(hallazgos, [], [str(h) for h in hallazgos])

    def test_script_real_de_solicitud_archivos(self):
        hallazgos = verificar_diccionario_tablas(caso6.TABLA, caso6.DICCIONARIO_REAL)
        reglas = [h.regla for h in hallazgos]

        # Las 6 columnas y la tabla están documentadas: no hay falsos positivos.
        self.assertNotIn("COLUMNA_FALTANTE", reglas)
        self.assertNotIn("TABLA_SIN_DESCRIPCION", reglas)

        sintaxis = [h for h in hallazgos if h.regla == "SINTAXIS_DICCIONARIO"]
        self.assertEqual(len(sintaxis), 1)
        self.assertEqual(sintaxis[0].linea, 5)
        self.assertIn("Coma sobrante", sintaxis[0].mensaje)

        self.assertIn("DESCRIPCION_TABLA_INADECUADA", reglas)
        # SQL Server acepta nombres simples sin comillas: no se reportan.
        self.assertNotIn("VALOR_SIN_COMILLAS", reglas)

    def test_punto_y_coma_y_exec_dentro_de_la_descripcion_no_cortan_la_sentencia(self):
        diccionario = caso6.diccionario_correcto(";").replace(
            "Nombre del archivo adjunto",
            "Nombre del archivo; no ejecutar EXEC sys.sp_addextendedproperty aqui",
        )
        self.assertEqual(verificar_diccionario_tablas(caso6.TABLA, diccionario), [])

    def test_sentencias_comentadas_se_ignoran(self):
        diccionario = caso6.diccionario_correcto(";") + (
            "\n-- EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'x', "
            "@level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', "
            "@level1name = N'TB_SolicitudArchivos', @level2type = N'COLUMN', @level2name = N'cOtra';"
        )
        self.assertEqual(verificar_diccionario_tablas(caso6.TABLA, diccionario), [])

    def test_columna_documentada_que_no_existe(self):
        diccionario = caso6.diccionario_correcto(";").replace("N'bActivo'", "N'bActivoo'")
        reglas = {h.regla for h in verificar_diccionario_tablas(caso6.TABLA, diccionario)}
        self.assertEqual(reglas, {"COLUMNA_NO_EXISTE", "COLUMNA_FALTANTE"})

    def test_columna_documentada_dos_veces(self):
        base = caso6.diccionario_correcto(";")
        repetida = caso6._sentencia("cNombreArchivo", "Otra descripcion") + ";"
        hallazgos = verificar_diccionario_tablas(caso6.TABLA, base + "\n" + repetida)
        self.assertEqual([h.regla for h in hallazgos], ["DOCUMENTACION_DUPLICADA"])

    def test_sentencia_sin_parametros_obligatorios(self):
        diccionario = caso6.diccionario_correcto(";").replace(
            "@level1type = N'TABLE', @level1name = N'TB_SolicitudArchivos',\n@level2type = N'COLUMN', @level2name = N'bActivo'",
            "@level1type = N'TABLE', @level1name = N'TB_SolicitudArchivos',\n@level2type = N'COLUMN'",
        )
        reglas = {h.regla for h in verificar_diccionario_tablas(caso6.TABLA, diccionario)}
        self.assertIn("PARAMETROS_INCOMPLETOS", reglas)


if __name__ == "__main__":
    unittest.main()
