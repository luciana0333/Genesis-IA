import inspect
import re
import unittest

from app.analizadores import analizador_tablas
from app.analizadores.analizador_tablas import verificar_tabla
from app.modelos.hallazgo import Severidad
from app.reglas.reglas_tablas import REGLAS_TABLAS

COLLATE = "COLLATE SQL_Latin1_General_CP1_CI_AS"

# Tabla que cumple el manual de nomenclatura (ejemplos del manual).
TABLA_CORRECTA = f"""
CREATE TABLE dbo.Persona (
    nPersonaId INT IDENTITY(1,1) NOT NULL,
    cPersonaNombre VARCHAR(100) {COLLATE} NOT NULL,
    nConceptoMayor DECIMAL(12, 2) NOT NULL DEFAULT 0,
    bPersonaEstado BIT NOT NULL DEFAULT 1,
    dPersonaFechaNacimiento DATE NOT NULL,
    CONSTRAINT PK_Persona PRIMARY KEY CLUSTERED (nPersonaId)
);
"""


def reglas(sql, **opciones):
    return [h.regla for h in verificar_tabla(sql, **opciones)]


class TestCreateTable(unittest.TestCase):
    """CREATE TABLE: la tabla es nueva, se aplican todas las reglas del manual."""

    def test_tabla_que_cumple_el_manual_no_genera_hallazgos(self):
        self.assertEqual(verificar_tabla(TABLA_CORRECTA), [])

    def test_exige_esquema(self):
        sql = TABLA_CORRECTA.replace("dbo.Persona", "Persona")
        self.assertEqual(reglas(sql), ["TABLA_SIN_ESQUEMA"])

    def test_nombre_de_tabla_en_pascal_case_sin_guiones_bajos(self):
        for nombre in ("TB_Persona", "persona", "PERSONA", "Persona_Datos"):
            with self.subTest(nombre=nombre):
                sql = TABLA_CORRECTA.replace("dbo.Persona", f"dbo.{nombre}")
                self.assertIn("TABLA_NOMBRE_NO_PASCALCASE", reglas(sql))
        for nombre in ("Persona", "CuentasPorPagar", "LibroVisitas", "SeguridadInformacion"):
            with self.subTest(nombre=nombre):
                sql = TABLA_CORRECTA.replace("dbo.Persona", f"dbo.{nombre}")
                self.assertNotIn("TABLA_NOMBRE_NO_PASCALCASE", reglas(sql))

    def test_detecta_palabra_omitible_en_nombre_de_tabla(self):
        sql = TABLA_CORRECTA.replace("dbo.Persona", "dbo.PersonaDeCliente")
        self.assertIn("TABLA_CON_PALABRA_OMITIBLE", reglas(sql))

    def test_exige_clave_primaria(self):
        sql = f"CREATE TABLE dbo.CuentasPorPagar (cCuentaCodigo VARCHAR(10) {COLLATE} NOT NULL);"
        hallazgos = verificar_tabla(sql)
        self.assertEqual([h.regla for h in hallazgos], ["PK_FALTANTE"])
        self.assertIn("nCuentasPorPagarId", hallazgos[0].mensaje)

    def test_pk_debe_llamarse_n_nombre_tabla_id(self):
        sql = TABLA_CORRECTA.replace("nPersonaId", "nId")
        self.assertIn("PK_NOMBRE_INVALIDO", reglas(sql))

    def test_pk_debe_ser_identity_cluster_y_numerica(self):
        sql = f"CREATE TABLE dbo.Persona (nPersonaId VARCHAR(10) {COLLATE} NOT NULL PRIMARY KEY NONCLUSTERED);"
        encontradas = set(reglas(sql))
        self.assertTrue({"PK_SIN_IDENTITY", "PK_NO_CLUSTER", "PK_NO_NUMERICA"} <= encontradas)

    def test_pk_compuesta(self):
        sql = TABLA_CORRECTA.replace("(nPersonaId)", "(nPersonaId, cPersonaNombre)")
        self.assertIn("PK_COMPUESTA", reglas(sql))

    def test_pk_en_la_columna_o_agregada_con_alter_en_el_mismo_script(self):
        en_columna = "CREATE TABLE dbo.Persona (nPersonaId INT IDENTITY(1,1) PRIMARY KEY);"
        self.assertEqual(verificar_tabla(en_columna), [])
        con_alter = (
            "CREATE TABLE dbo.Persona (nPersonaId INT IDENTITY(1,1) NOT NULL);\n"
            "ALTER TABLE dbo.Persona ADD CONSTRAINT PK_Persona PRIMARY KEY (nPersonaId);"
        )
        self.assertEqual(verificar_tabla(con_alter), [])

    def test_columnas_exigen_not_null_o_default(self):
        sql = TABLA_CORRECTA.replace("dPersonaFechaNacimiento DATE NOT NULL", "dPersonaFechaNacimiento DATE NULL")
        self.assertEqual(reglas(sql), ["COLUMNA_SIN_NOT_NULL_NI_DEFAULT"])


class TestColumnas(unittest.TestCase):
    """Reglas de columna: aplican al CREATE y a las columnas nuevas de un ALTER."""

    def test_valida_prefijo_segun_el_tipo(self):
        sql = TABLA_CORRECTA.replace("cPersonaNombre", "PersonaNombre")
        hallazgos = verificar_tabla(sql)
        self.assertEqual([h.regla for h in hallazgos], ["COLUMNA_PREFIJO_TIPO_INVALIDO"])
        self.assertIn("debe iniciar con 'c'", hallazgos[0].mensaje)

    def test_despues_del_prefijo_va_pascal_case(self):
        for nombre in ("cpersonanombre", "c_persona_nombre", "cPERSONA"):
            with self.subTest(nombre=nombre):
                sql = TABLA_CORRECTA.replace("cPersonaNombre", nombre)
                self.assertIn("COLUMNA_NOMBRE_NO_PASCALCASE", reglas(sql))

    def test_prefijos_de_los_ejemplos_del_manual(self):
        self.assertEqual(verificar_tabla(TABLA_CORRECTA), [])

    def test_collate_obligatorio_en_texto_fuera_de_dbcmaica(self):
        sql = TABLA_CORRECTA.replace(f"VARCHAR(100) {COLLATE}", "VARCHAR(100)")
        self.assertEqual(reglas(sql), ["COLUMNA_SIN_COLLATE"])
        self.assertEqual(verificar_tabla(sql, es_dbcmaica=True), [])
        self.assertEqual(verificar_tabla(sql.replace("dbo.Persona", "DBCMAICA.dbo.Persona")), [])

    def test_collate_en_tipo_no_textual_es_invalido(self):
        sql = TABLA_CORRECTA.replace("BIT NOT NULL", f"BIT {COLLATE} NOT NULL")
        self.assertIn("COLLATE_EN_TIPO_NO_TEXTO", reglas(sql))

    def test_linea_del_hallazgo_es_la_de_la_columna(self):
        sql = TABLA_CORRECTA.replace("cPersonaNombre", "PersonaNombre")
        self.assertEqual(verificar_tabla(sql)[0].linea, 4)


class TestVarbinaryProhibido(unittest.TestCase):
    def test_varbinary_prohibido_en_create(self):
        sql = TABLA_CORRECTA.replace(
            "dPersonaFechaNacimiento DATE NOT NULL,",
            "dPersonaFechaNacimiento DATE NOT NULL,\n    xPersonaFoto VARBINARY(MAX) NOT NULL,",
        )
        hallazgos = [h for h in verificar_tabla(sql) if h.regla == "COLUMNA_VARBINARY_PROHIBIDA"]
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad, Severidad.ALTO)
        self.assertIn("xPersonaFoto", hallazgos[0].mensaje)

    def test_varbinary_prohibido_al_agregar_columna_con_alter(self):
        for tipo in ("VARBINARY(MAX)", "varbinary(500)", "VARBINARY"):
            with self.subTest(tipo=tipo):
                sql = f"ALTER TABLE dbo.Persona ADD xPersonaDocumento {tipo} NULL;"
                self.assertIn("COLUMNA_VARBINARY_PROHIBIDA", reglas(sql))


class TestNombreSinNumeros(unittest.TestCase):
    def test_columna_con_numeros_en_create(self):
        sql = TABLA_CORRECTA.replace("cPersonaNombre", "cPersonaNombre89")
        hallazgos = [h for h in verificar_tabla(sql) if h.regla == "COLUMNA_NOMBRE_CON_NUMERO"]
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad, Severidad.ALTO)
        self.assertIn("89", hallazgos[0].mensaje)
        self.assertIn("(ej.: cPersonaNombre)", hallazgos[0].mensaje)

    def test_columna_con_numeros_en_alter(self):
        sql = f"ALTER TABLE dbo.Persona ADD cDireccion2 VARCHAR(100) {COLLATE} NOT NULL DEFAULT '';"
        self.assertEqual(reglas(sql), ["COLUMNA_NOMBRE_CON_NUMERO"])

    def test_columnas_sin_numeros_no_generan_hallazgo(self):
        self.assertNotIn("COLUMNA_NOMBRE_CON_NUMERO", reglas(TABLA_CORRECTA))


class TestAlterTable(unittest.TestCase):
    """ALTER TABLE: solo se revisan las columnas nuevas."""

    def test_no_aplica_reglas_de_tabla_ni_de_pk(self):
        sql = f"ALTER TABLE TB_Persona ADD cPersonaApodo VARCHAR(30) {COLLATE} NOT NULL DEFAULT '';"
        self.assertEqual(verificar_tabla(sql), [])

    def test_columna_que_acepta_null_solo_pide_evaluar_un_default(self):
        sql = f"ALTER TABLE dbo.Persona ADD cPersonaApodo VARCHAR(30) {COLLATE} NULL;"
        hallazgos = verificar_tabla(sql)
        self.assertEqual([h.regla for h in hallazgos], ["COLUMNA_NULL_EN_ALTER"])
        self.assertEqual(hallazgos[0].severidad, Severidad.BAJO)
        self.assertIn("¿Evaluó definir un valor por defecto", hallazgos[0].mensaje)

    def test_revisa_prefijo_nombre_y_collate_de_la_columna_nueva(self):
        sql = "ALTER TABLE dbo.Persona ADD Apodo VARCHAR(30) NOT NULL DEFAULT '';"
        self.assertEqual(set(reglas(sql)), {"COLUMNA_PREFIJO_TIPO_INVALIDO", "COLUMNA_SIN_COLLATE"})

    def test_add_con_varias_columnas_y_con_parentesis(self):
        sql = f"ALTER TABLE dbo.Persona ADD cPersonaApodo VARCHAR(30) {COLLATE} NOT NULL DEFAULT '', Activo BIT NULL;"
        self.assertEqual(set(reglas(sql)), {"COLUMNA_PREFIJO_TIPO_INVALIDO", "COLUMNA_NULL_EN_ALTER"})
        con_parentesis = f"ALTER TABLE dbo.Persona ADD (cPersonaApodo VARCHAR(30) {COLLATE} NOT NULL DEFAULT '')"
        self.assertEqual(verificar_tabla(con_parentesis), [])

    def test_add_constraint_no_es_una_columna(self):
        sql = "ALTER TABLE dbo.Persona ADD CONSTRAINT DF_Persona_bActivo DEFAULT 1 FOR bPersonaActivo;"
        self.assertEqual(verificar_tabla(sql), [])


class TestCatalogo(unittest.TestCase):
    def test_toda_regla_emitida_esta_en_el_catalogo(self):
        codigo = inspect.getsource(analizador_tablas)
        emitidas = set(re.findall(r'_hallazgo\(\s*[^,]+,\s*[^,]+,\s*"([A-Z_]+)"', codigo))
        self.assertTrue(emitidas)
        self.assertEqual(emitidas - set(REGLAS_TABLAS), set())

    def test_hallazgos_de_la_tabla_en_la_linea_del_create(self):
        sql = "-- Tabla de clientes\n\nCREATE TABLE cliente (\n  nId INT\n);"
        hallazgos = {h.regla: h.linea for h in verificar_tabla(sql)}
        for regla in ("TABLA_SIN_ESQUEMA", "TABLA_NOMBRE_NO_PASCALCASE", "PK_FALTANTE"):
            self.assertEqual(hallazgos[regla], 3, regla)


if __name__ == "__main__":
    unittest.main()
