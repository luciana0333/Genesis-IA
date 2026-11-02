"""Diccionario con un solo objeto en el script que documenta además otro objeto (2 nov.).

Si el objeto del script ya está documentado con su nombre, otro nombre que no se le parece es otra tabla u
otro procedimiento que no vino en el script: se avisa una vez como «fuera del script», no como «el nombre no
coincide» (que pedía cambiarlo por el del script) ni con sus columnas o parámetros como inexistentes.
Un nombre parecido sigue siendo un error al escribirlo.
"""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas

TABLA = ("CREATE TABLE dbo.Cliente (\n nClienteId INT IDENTITY(1,1) NOT NULL,\n"
         " cNombre VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,\n"
         " CONSTRAINT PK_Cliente_nClienteId PRIMARY KEY CLUSTERED (nClienteId))")
PROCEDIMIENTO = "CREATE PROCEDURE dbo.PA_Cliente_Sel_Datos\n @pnClienteId INT\nAS\nBEGIN\n SELECT 1\nEND"


def _descripcion(valor, tipo, nombre, tipo2=None, nombre2=None):
    sentencia = (f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{valor}', "
                 f"@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'{tipo}', @level1name=N'{nombre}'")
    if tipo2:
        sentencia += f", @level2type=N'{tipo2}', @level2name=N'{nombre2}'"
    return sentencia + "\nGO\n"


DICC_TABLA = (_descripcion("Clientes de la caja", "TABLE", "Cliente")
              + _descripcion("Identificador del cliente", "TABLE", "Cliente", "COLUMN", "nClienteId")
              + _descripcion("Nombre del cliente", "TABLE", "Cliente", "COLUMN", "cNombre"))
DICC_PROC = (_descripcion("Obtiene los datos del cliente", "PROCEDURE", "PA_Cliente_Sel_Datos")
             + _descripcion("Identificador del cliente", "PROCEDURE", "PA_Cliente_Sel_Datos", "PARAMETER",
                            "@pnClienteId"))


class OtraTablaDocumentadaTest(unittest.TestCase):
    def test_otra_tabla_es_tabla_fuera_del_script(self):
        diccionario = (DICC_TABLA + _descripcion("Proveedores", "TABLE", "Proveedor")
                       + _descripcion("Identificador del proveedor", "TABLE", "Proveedor", "COLUMN", "nProveedorId"))
        hallazgos = verificar_diccionario_tablas(TABLA, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["TABLA_FUERA_DEL_SCRIPT"])
        self.assertTrue(hallazgos[0].mensaje.startswith(
            "Se identificó documentación de la tabla Proveedor, que no está en el script de las tablas."))
        self.assertEqual(hallazgos[0].linea, 7)

    def test_nombre_mal_escrito_sigue_siendo_no_coincide(self):
        diccionario = DICC_TABLA.replace("@level1name=N'Cliente'", "@level1name=N'Clientes'")
        hallazgos = verificar_diccionario_tablas(TABLA, diccionario)
        # Sin «la tabla no se encuentra documentada»: sí lo está, con el nombre mal escrito.
        self.assertEqual([h.regla for h in hallazgos], ["NOMBRE_TABLA_NO_COINCIDE"])
        self.assertIn("'Clientes'", hallazgos[0].mensaje)

    def test_tipo_de_nivel_incorrecto(self):
        diccionario = DICC_TABLA.replace(
            "@level1type=N'TABLE', @level1name=N'Cliente', @level2type=N'COLUMN', @level2name=N'cNombre'",
            "@level1type=N'VIEW', @level1name=N'Cliente', @level2type=N'COLUMN', @level2name=N'cNombre'",
        )
        hallazgos = verificar_diccionario_tablas(TABLA, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["TIPO_NIVEL_INCORRECTO"])
        self.assertIn("'VIEW'", hallazgos[0].mensaje)


class OtroProcedimientoDocumentadoTest(unittest.TestCase):
    def test_otro_procedimiento_es_procedimiento_fuera_del_script(self):
        diccionario = (DICC_PROC + _descripcion("Lista los proveedores", "PROCEDURE", "PA_Proveedor_Sel_Lista")
                       + _descripcion("Identificador del proveedor", "PROCEDURE", "PA_Proveedor_Sel_Lista",
                                      "PARAMETER", "@pnProveedorId"))
        hallazgos = verificar_diccionario(PROCEDIMIENTO, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["PROCEDIMIENTO_FUERA_DEL_SCRIPT"])
        self.assertIn("PA_Proveedor_Sel_Lista", hallazgos[0].mensaje)

    def test_nombre_mal_escrito_sigue_siendo_no_coincide(self):
        diccionario = DICC_PROC.replace("N'PA_Cliente_Sel_Datos'", "N'PA_Cliente_Sel_Dato'")
        self.assertEqual([h.regla for h in verificar_diccionario(PROCEDIMIENTO, diccionario)], ["NOMBRE_NO_COINCIDE"])


if __name__ == "__main__":
    unittest.main()


NOMBRES_20 = ["Cliente", "Agencia", "Producto", "Credito", "CreditoDetalle", "Cuenta", "CuentaMovimiento", "Moneda",
              "Tasa", "TasaHistorico", "Garantia", "GarantiaTipo", "Persona", "PersonaDireccion", "Usuario",
              "UsuarioPerfil", "Perfil", "Zona", "Area", "Cargo"]


def _tabla(nombre):
    return (f"CREATE TABLE dbo.{nombre} (\n n{nombre}Id INT IDENTITY(1,1) NOT NULL,\n"
            f" cDescripcion VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,\n nEstado INT NOT NULL,\n"
            f" CONSTRAINT PK_{nombre}_n{nombre}Id PRIMARY KEY CLUSTERED (n{nombre}Id))\nGO\n")


def _diccionario(nombre):
    return (_descripcion(f"Registro de {nombre}", "TABLE", nombre)
            + _descripcion("Identificador del registro", "TABLE", nombre, "COLUMN", f"n{nombre}Id")
            + _descripcion("Descripción del registro", "TABLE", nombre, "COLUMN", "cDescripcion")
            + _descripcion("Estado del registro", "TABLE", nombre, "COLUMN", "nEstado"))


class VeinteTablasTest(unittest.TestCase):
    """20 tablas con las mismas columnas: cada sentencia del diccionario va a su tabla."""

    def setUp(self):
        self.tablas = "".join(_tabla(n) for n in NOMBRES_20)
        self.diccionario = "".join(_diccionario(n) for n in NOMBRES_20)

    def test_bien_documentadas_en_cualquier_orden(self):
        self.assertEqual(verificar_diccionario_tablas(self.tablas, self.diccionario), [])
        al_reves = "".join(_diccionario(n) for n in reversed(NOMBRES_20))
        self.assertEqual(verificar_diccionario_tablas(self.tablas, al_reves), [])

    def test_tabla_mal_escrita_va_a_la_mas_parecida_y_no_a_la_anterior(self):
        # GarantiaTipos se parece a GarantiaTipo, no a la tabla anterior (Garantia).
        diccionario = self.diccionario.replace("N'GarantiaTipo'", "N'GarantiaTipos'")
        hallazgos = verificar_diccionario_tablas(self.tablas, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["NOMBRE_TABLA_NO_COINCIDE"])
        self.assertIn("'GarantiaTipos', pero la tabla se llama 'GarantiaTipo'", hallazgos[0].mensaje)

    def test_tabla_extra_y_tabla_sin_documentar(self):
        diccionario = "".join(_diccionario(n) for n in NOMBRES_20 if n != "Zona") + _diccionario("Proveedor")
        reglas = sorted(h.regla for h in verificar_diccionario_tablas(self.tablas, diccionario))
        self.assertEqual(reglas, ["COLUMNA_FALTANTE", "TABLA_FUERA_DEL_SCRIPT", "TABLA_SIN_DESCRIPCION"])
