"""Casos de borde encontrados en la auditoría de QA de los diccionarios."""
import unittest

from app.analizadores.analizador_diccionario_procedimientos import (
    extraer_esquema_y_nombre,
    extraer_parametros,
    extraer_tipo_sentencia,
    verificar_diccionario,
)
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas

PROC = """CREATE PROCEDURE dbo.PA_Cliente_Sel_PorId
    @nClienteId INT,
    @cCodigo VARCHAR(10) = NULL
AS
BEGIN
    DECLARE @nTotal INT;
    SELECT nClienteId FROM dbo.Cliente WHERE nClienteId = @nClienteId;
END"""


def sentencia(descripcion="Consulta el cliente", parametro=None, nombre="PA_Cliente_Sel_PorId"):
    nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
    return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{descripcion}', "
            f"@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'PROCEDURE', "
            f"@level1name=N'{nombre}'{nivel2}\nGO")


COMPLETO = "\n".join([sentencia(), sentencia("Identificador del cliente", "@nClienteId"),
                      sentencia("Codigo del cliente", "@cCodigo")])


def reglas(hallazgos):
    return sorted(h.regla for h in hallazgos)


class TestEncabezadoDelProcedimiento(unittest.TestCase):
    def test_variantes_del_encabezado(self):
        casos = {
            "CREATE PROCEDURE dbo.PA_X_Sel @a INT AS SELECT 1": (("dbo", "PA_X_Sel"), {"@a"}, "CREATE"),
            "create proc [dbo].[PA_X_Sel] (@a INT, @b VARCHAR(5) = 'x,y') AS SELECT 1": (("dbo", "PA_X_Sel"), {"@a", "@b"}, "CREATE"),
            "CREATE OR ALTER PROCEDURE PA_Y\n  @a INT, -- @viejo INT\n  @c INT OUTPUT\nWITH RECOMPILE\nAS SELECT 1": ((None, "PA_Y"), {"@a", "@c"}, "CREATE"),
            "ALTER PROCEDURE BD.dbo.PA_Z AS SELECT @@ROWCOUNT": (("dbo", "PA_Z"), set(), "ALTER"),
            "-- CREATE PROCEDURE comentado\nALTER PROC x.y @q INT AS SELECT 1": (("x", "y"), {"@q"}, "ALTER"),
        }
        for sql, (nombre, parametros, tipo) in casos.items():
            with self.subTest(sql=sql.splitlines()[0]):
                self.assertEqual(extraer_esquema_y_nombre(sql), nombre)
                self.assertEqual(extraer_parametros(sql), parametros)
                self.assertEqual(extraer_tipo_sentencia(sql), tipo)

    def test_create_proc_y_corchetes_detectan_parametros_faltantes(self):
        for variante in (PROC.replace("CREATE PROCEDURE", "CREATE PROC"),
                         PROC.replace("dbo.PA_Cliente_Sel_PorId", "[dbo].[PA_Cliente_Sel_PorId]"),
                         PROC.replace("CREATE PROCEDURE", "CREATE OR ALTER PROCEDURE")):
            with self.subTest(variante=variante.splitlines()[0]):
                self.assertEqual(reglas(verificar_diccionario(variante, sentencia())), ["PARAMETRO_FALTANTE"])

    def test_parametro_comentado_no_se_exige(self):
        sql = PROC.replace("    @nClienteId INT,", "    @nClienteId INT,\n    -- @nViejo INT,")
        self.assertEqual(verificar_diccionario(sql, COMPLETO), [])


class TestDiccionarioDeProcedimientoQA(unittest.TestCase):
    def test_parametro_documentado_que_no_existe(self):
        diccionario = COMPLETO.replace("N'@nClienteId'", "N'@nClienteID2'")
        hallazgos = {h.regla: h for h in verificar_diccionario(PROC, diccionario)}
        self.assertIn("PARAMETRO_NO_EXISTE", hallazgos)
        self.assertIn("(¿quiso decir '@nClienteId'?)", hallazgos["PARAMETRO_NO_EXISTE"].mensaje)

    def test_sentencia_incompleta(self):
        sin_nivel1 = COMPLETO.replace(
            ", @level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Sel_PorId', @level2type",
            ", @level1type=N'PROCEDURE', @level2type", 1)
        self.assertIn("PARAMETROS_INCOMPLETOS", reglas(verificar_diccionario(PROC, sin_nivel1)))


class TestDiccionarioDeTablaQA(unittest.TestCase):
    TABLA = """CREATE TABLE dbo.Cliente (
    nClienteId INT IDENTITY(1,1) NOT NULL,
    cNombre VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL DEFAULT (','),
    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)
);"""

    def diccionario(self, tabla="Cliente"):
        def s(desc, col=None):
            nivel2 = f", @level2type=N'COLUMN', @level2name=N'{col}'" if col else ""
            return (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{desc}', "
                    f"@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', "
                    f"@level1name=N'{tabla}'{nivel2}\nGO")
        return "\n".join([s("Almacena los clientes"), s("Identificador del cliente", "nClienteId"),
                          s("Nombre del cliente", "cNombre")])

    def test_nombre_con_base_de_datos(self):
        sql = self.TABLA.replace("dbo.Cliente", "BD.dbo.Cliente")
        self.assertEqual(verificar_diccionario_tablas(sql, self.diccionario()), [])

    def test_default_con_coma_no_rompe_las_columnas(self):
        self.assertEqual(verificar_diccionario_tablas(self.TABLA, self.diccionario()), [])


if __name__ == "__main__":
    unittest.main()
