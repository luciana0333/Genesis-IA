"""Nombres vacíos (N'') en el diccionario: el diccionario no indica el objeto documentado."""
import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas

PROCEDIMIENTO = """CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Sel_PorId
    @nClienteId INT
AS
BEGIN
    SELECT nClienteId FROM CLICKTOPAY.Cliente WHERE nClienteId = @nClienteId;
END;"""

DICCIONARIO_PROCEDIMIENTO = """EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Consulta la informacion del cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'PROCEDURE', @level1name=N''
GO"""

TABLA = """CREATE TABLE CLICKTOPAY.Cliente (
    nClienteId INT IDENTITY(1,1) NOT NULL,
    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)
);"""

DICCIONARIO_TABLA = """EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Clientes',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', @level1type=N'TABLE', @level1name=N''
GO"""


class TestNombreVacio(unittest.TestCase):
    def test_procedimiento_con_nombre_vacio(self):
        hallazgos = verificar_diccionario(PROCEDIMIENTO, DICCIONARIO_PROCEDIMIENTO)
        reglas = {h.regla: h for h in hallazgos}
        self.assertNotIn("NOMBRE_NO_COINCIDE", reglas)
        vacio = reglas["NOMBRE_VACIO"]
        self.assertEqual((vacio.linea, vacio.severidad.value), (5, "alto"))
        self.assertIn("no indica el nombre del procedimiento", vacio.mensaje)
        self.assertIn("@level1name=N'PA_Cliente_Sel_PorId'", vacio.mensaje)

    def test_procedimiento_con_esquema_vacio(self):
        diccionario = (DICCIONARIO_PROCEDIMIENTO.replace("@level0name=N'CLICKTOPAY'", "@level0name=N''")
                       .replace("@level1name=N''", "@level1name=N'PA_Cliente_Sel_PorId'"))
        vacio = next(h for h in verificar_diccionario(PROCEDIMIENTO, diccionario) if h.regla == "NOMBRE_VACIO")
        self.assertIn("no indica el esquema del procedimiento", vacio.mensaje)
        self.assertIn("@level0name=N'CLICKTOPAY'", vacio.mensaje)

    def test_tabla_con_nombre_vacio(self):
        hallazgos = verificar_diccionario_tablas(TABLA, DICCIONARIO_TABLA)
        reglas = {h.regla: h for h in hallazgos}
        # La tabla sí se documentó (con el nombre vacío): no se marca además «sin descripción».
        self.assertNotIn("TABLA_SIN_DESCRIPCION", reglas)
        self.assertEqual(reglas["NOMBRE_VACIO"].linea, 2)
        self.assertIn("@level1name=N'Cliente'", reglas["NOMBRE_VACIO"].mensaje)

    def test_columna_con_nombre_vacio(self):
        diccionario = DICCIONARIO_TABLA.replace("@level1name=N''", "@level1name=N'Cliente'") + """
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Identificador',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', @level1type=N'TABLE', @level1name=N'Cliente',
@level2type=N'COLUMN', @level2name=N''
GO"""
        vacio = next(h for h in verificar_diccionario_tablas(TABLA, diccionario) if h.regla == "NOMBRE_VACIO")
        self.assertEqual(vacio.linea, 6)
        self.assertIn("no indica el nombre de la columna", vacio.mensaje)


if __name__ == "__main__":
    unittest.main()
