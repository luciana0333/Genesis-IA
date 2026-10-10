import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas

TABLA_SIN_ESQUEMA = """CREATE TABLE Cliente (
    nClienteId INT IDENTITY(1,1) NOT NULL,
    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)
);"""

PROC_SIN_ESQUEMA = """CREATE PROCEDURE PA_Cliente_Consultar
    @nClienteId INT
AS
BEGIN
    SELECT nClienteId FROM dbo.Cliente WHERE nClienteId = @nClienteId;
END;"""


def reglas(hallazgos):
    return [h.regla for h in hallazgos]


class TestEsquemaDeclarado(unittest.TestCase):
    def test_tabla_sin_esquema(self):
        hallazgos = [h for h in verificar_diccionario_tablas(TABLA_SIN_ESQUEMA, "") if h.regla == "OBJETO_SIN_ESQUEMA"]
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].linea, 1)
        self.assertIn("dbo.Cliente", hallazgos[0].mensaje)

    def test_tabla_con_esquema(self):
        sql = TABLA_SIN_ESQUEMA.replace("CREATE TABLE Cliente", "CREATE TABLE dbo.Cliente")
        self.assertNotIn("OBJETO_SIN_ESQUEMA", reglas(verificar_diccionario_tablas(sql, "")))

    def test_procedimiento_sin_esquema_igual_se_revisa(self):
        hallazgos = verificar_diccionario(PROC_SIN_ESQUEMA, "")
        self.assertIn("OBJETO_SIN_ESQUEMA", reglas(hallazgos))
        # Antes, sin esquema no se revisaba nada: ahora también reporta lo demás.
        self.assertGreater(len(hallazgos), 1)
        self.assertFalse(any("None." in h.mensaje for h in hallazgos))

    def test_procedimiento_con_esquema(self):
        sql = PROC_SIN_ESQUEMA.replace("PROCEDURE PA_", "PROCEDURE dbo.PA_")
        self.assertNotIn("OBJETO_SIN_ESQUEMA", reglas(verificar_diccionario(sql, "")))


if __name__ == "__main__":
    unittest.main()
