"""El mismo objeto creado dos veces en el script (dos CREATE TABLE o dos CREATE PROCEDURE iguales)."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.analizador_tablas import verificar_tabla

TABLA = """CREATE TABLE TB_cliente_datos (
    id INT,
    nombre89 VARCHAR(50),
    cDescripcion VARCHAR(MAX),
    nMonto DECIMAL(18,2) COLLATE SQL_Latin1_General_CP1_CI_AS
);
"""
DOS_VECES = TABLA + "\n" + TABLA


def reglas(hallazgos):
    return [h.regla for h in hallazgos]


class TestTablaDuplicada(unittest.TestCase):
    def test_tablas_avisa_una_vez_y_no_duplica_los_demas_errores(self):
        hallazgos = verificar_tabla(DOS_VECES)
        duplicada = [h for h in hallazgos if h.regla == "TABLA_DUPLICADA"]
        self.assertEqual(len(duplicada), 1)
        self.assertEqual(duplicada[0].severidad.value, "critico")
        self.assertEqual(duplicada[0].linea, 8)
        self.assertEqual(
            duplicada[0].mensaje,
            "Se identificó que la tabla TB_cliente_datos se crea dos veces en el script. "
            "Se recomienda retirar una de las sentencias CREATE TABLE, ya que SQL Server genera un error "
            "al intentar crear un objeto que ya existe.",
        )
        # El resto, igual que si la tabla estuviera una sola vez.
        self.assertEqual(
            [(h.regla, h.mensaje) for h in hallazgos if h.regla != "TABLA_DUPLICADA"],
            [(h.regla, h.mensaje) for h in verificar_tabla(TABLA)],
        )

    def test_diccionarios_avisa_una_vez(self):
        hallazgos = verificar_diccionario_tablas(DOS_VECES, "")
        self.assertEqual(reglas(hallazgos).count("TABLA_DUPLICADA"), 1)
        self.assertEqual(reglas(hallazgos).count("COLUMNA_FALTANTE"), 1)
        self.assertIn("en las líneas 2, 3, 4, 5:", next(h for h in hallazgos if h.regla == "COLUMNA_FALTANTE").mensaje)

    def test_tres_veces(self):
        hallazgo = verificar_tabla(TABLA + TABLA + TABLA)[0]
        self.assertIn("se crea tres veces en el script.", hallazgo.mensaje)
        self.assertIn("retirar las sentencias repetidas CREATE TABLE", hallazgo.mensaje)

    def test_create_y_alter_de_la_misma_tabla_no_es_duplicado(self):
        script = TABLA + "ALTER TABLE TB_cliente_datos ADD nTotal INT NOT NULL;\n"
        self.assertNotIn("TABLA_DUPLICADA", reglas(verificar_tabla(script)))

    def test_misma_tabla_en_otro_esquema_no_es_duplicado(self):
        script = TABLA.replace("TB_cliente_datos", "Ventas.TB_cliente_datos") + TABLA
        self.assertNotIn("TABLA_DUPLICADA", reglas(verificar_tabla(script)))

    def test_sin_esquema_y_con_dbo_es_la_misma_tabla(self):
        script = TABLA + TABLA.replace("TB_cliente_datos", "dbo.TB_cliente_datos")
        self.assertIn("TABLA_DUPLICADA", reglas(verificar_tabla(script)))

    def test_create_comentado_no_cuenta(self):
        script = TABLA + "/*\n" + TABLA + "*/\n"
        self.assertNotIn("TABLA_DUPLICADA", reglas(verificar_tabla(script)))

    def test_dos_tablas_repetidas_en_una_observacion(self):
        otra = TABLA.replace("TB_cliente_datos", "dbo.Persona")
        hallazgos = [h for h in verificar_tabla(TABLA + otra + TABLA + otra) if h.regla == "TABLA_DUPLICADA"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("Se identificaron dos tablas que se crean más de una vez en el script: "
                      "TB_cliente_datos; Persona.", hallazgos[0].mensaje)


class TestProcedimientoDuplicado(unittest.TestCase):
    PROCEDIMIENTO = """CREATE PROCEDURE dbo.PA_Cliente_Sel_PorId
    @nIdCliente INT
AS
BEGIN
    SELECT 1;
END
GO
"""

    def test_procedimiento_creado_dos_veces(self):
        hallazgos = verificar_diccionario(self.PROCEDIMIENTO + self.PROCEDIMIENTO, "")
        self.assertEqual(reglas(hallazgos).count("PROCEDIMIENTO_DUPLICADO"), 1)
        duplicado = hallazgos[0]
        self.assertIn("el procedimiento PA_Cliente_Sel_PorId se crea dos veces en el script.",
                      duplicado.mensaje)
        self.assertIn("CREATE PROCEDURE", duplicado.mensaje)
        self.assertEqual(reglas(hallazgos).count("PARAMETRO_FALTANTE"), 1)

    def test_solo_encabezados_repetidos(self):
        encabezado = "CREATE PROCEDURE dbo.PA_Cliente_Sel_PorId\n    @nIdCliente INT\n\n"
        self.assertIn("PROCEDIMIENTO_DUPLICADO", reglas(verificar_diccionario(encabezado + encabezado, "")))

    def test_create_or_alter_repetido_no_es_duplicado(self):
        procedimiento = self.PROCEDIMIENTO.replace("CREATE PROCEDURE", "CREATE OR ALTER PROCEDURE")
        self.assertNotIn("PROCEDIMIENTO_DUPLICADO", reglas(verificar_diccionario(procedimiento + procedimiento, "")))


if __name__ == "__main__":
    unittest.main()
