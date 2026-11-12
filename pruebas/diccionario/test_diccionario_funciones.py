"""Diccionario de funciones: mismas reglas que el de procedimientos (usuaria, 11 nov.), con sus textos en femenino."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import extraer_parametros, verificar_diccionario
from app.analizadores.deteccion_objeto import detectar_objeto
from app.analizadores.diccionario_generador import diccionario_faltante_procedimiento
from app.analizadores.objeto_programable import FUNCION, actual, restaurar, usar

# Caso de la usuaria: función de tabla con sus 4 parámetros y el diccionario por posición.
_SU_FUNCION = (
    "ALTER FUNCTION dbo.FN_DevAreaDependiente_EO (@cArea varchar(3), @Nivel int, @cTipo varchar(3),"
    "@cActivo VARCHAR(2))\n"
    "RETURNS @Areas TABLE (cAreaCod VARCHAR(3))\nAS\nBEGIN\n    RETURN;\nEND"
)


def _sentencia(descripcion, parametro=None):
    texto = (f"EXEC sp_addextendedproperty\n\tN'MS_Description',N'{descripcion}',\n\tN'SCHEMA',N'DBO',\n"
             f"\tN'FUNCTION',N'FN_DevAreaDependiente_EO'")
    return texto + (f",\n\tN'PARAMETER',N'{parametro}'" if parametro else "")


_SU_DICCIONARIO = "\n\n".join([
    _sentencia("Función que devuelve las unidades orgánicas de niveles superiores e inferiores del área que se "
               "consulta."),
    _sentencia("Código del área que se consulta según la tabla Areas.", "@cArea"),
    _sentencia("Número de niveles limitante a consultar.", "@Nivel"),
    _sentencia("Tipo de búsqueda (NI: nivel inferior, NS: nivel superior).", "@cTipo"),
    _sentencia("Indica si la búsqueda se realizará de áreas activas o no (0: inactivo, 1: activo, 2: todos)",
               "@cActivo"),
])
_CREATE = _SU_FUNCION.replace("ALTER FUNCTION", "CREATE FUNCTION")


def _funcion(sql, diccionario):
    return verificar_diccionario(sql, diccionario, objeto="funcion")


class DiccionarioFuncionesTest(unittest.TestCase):
    def test_se_detecta_la_funcion(self):
        self.assertEqual(detectar_objeto(_SU_FUNCION), "funcion")

    def test_parametros_hasta_returns_sin_la_tabla_de_retorno(self):
        token = usar(FUNCION)
        try:
            self.assertEqual(extraer_parametros(_SU_FUNCION), {"@cArea", "@Nivel", "@cTipo", "@cActivo"})
        finally:
            restaurar(token)
        self.assertEqual(actual().clave, "procedimiento")  # se restaura

    def test_caso_de_la_usuaria_completo_en_create_no_tiene_observaciones(self):
        self.assertEqual(_funcion(_CREATE, _SU_DICCIONARIO), [])

    def test_caso_de_la_usuaria_en_alter_pide_validar_la_documentacion_existente(self):
        hallazgos = _funcion(_SU_FUNCION, _SU_DICCIONARIO)
        self.assertEqual([h.regla for h in hallazgos], ["DOCUMENTACION_EXISTENTE_EN_ALTER"])
        self.assertIn("agrega descripciones a la función dbo.FN_DevAreaDependiente_EO, que ya existe (ALTER): la "
                      "función y 4 parámetros.", hallazgos[0].mensaje)

    def test_funcion_sin_documentar_en_femenino(self):
        hallazgos = {h.regla: h for h in _funcion(_CREATE, "")}
        self.assertEqual(
            hallazgos["FUNCION_SIN_DESCRIPCION"].mensaje,
            "La función dbo.FN_DevAreaDependiente_EO no se encuentra documentada. Añadir la descripción de la "
            "función al diccionario, ya que toda función nueva debe estar documentada.",
        )
        self.assertIn("añadir los parámetros faltantes al diccionario de la función, cada uno con su descripción, ya "
                      "que todo parámetro de una función nueva debe estar documentado.",
                      hallazgos["PARAMETRO_FALTANTE"].mensaje)

    def test_alter_sin_diccionario(self):
        hallazgo = _funcion(_SU_FUNCION, "")[0]
        self.assertEqual(hallazgo.regla, "ALTER_SIN_DICCIONARIO")
        self.assertIn("la función dbo.FN_DevAreaDependiente_EO se modifica (ALTER FUNCTION)", hallazgo.mensaje)

    def test_las_demas_reglas_tambien_aplican(self):
        diccionario = (_SU_DICCIONARIO.replace("N'@cTipo'", "N'@cTipos'")
                       .replace("Número de niveles", "Número de de niveles")
                       .replace("N'FN_DevAreaDependiente_EO'", "N'FN_DevAreaDependiente'", 1))
        reglas = {h.regla for h in _funcion(_CREATE, diccionario)}
        self.assertTrue({"NOMBRE_FUNCION_NO_COINCIDE", "PALABRA_REPETIDA"} <= reglas, reglas)
        self.assertTrue(reglas & {"PARAMETRO_NO_EXISTE", "PARAMETRO_NOMBRE_INCORRECTO"}, reglas)

    def test_la_nomenclatura_de_procedimientos_no_se_aplica(self):
        sql = "CREATE FUNCTION dbo.ObtenerNombre (@n INT) RETURNS INT AS BEGIN RETURN 1; END"
        self.assertFalse([h for h in _funcion(sql, "") if h.regla.startswith("PROCEDIMIENTO_")])

    def test_generar_diccionario_faltante_usa_function(self):
        faltante = diccionario_faltante_procedimiento(_CREATE, "", "funcion")
        self.assertIn("-- Diccionario faltante de la función dbo.FN_DevAreaDependiente_EO", faltante["script"])
        self.assertIn("@level1type = N'FUNCTION'", faltante["script"])
        self.assertNotIn("PROCEDURE", faltante["script"])

    def test_el_procedimiento_sigue_igual(self):
        sql = "CREATE PROCEDURE dbo.PA_Area_Sel_Datos @cArea VARCHAR(3) AS BEGIN SELECT 1; END"
        hallazgos = {h.regla: h for h in verificar_diccionario(sql, "")}
        self.assertIn("PROCEDIMIENTO_SIN_DESCRIPCION", hallazgos)
        self.assertIn("El procedimiento dbo.PA_Area_Sel_Datos no se encuentra documentado.",
                      hallazgos["PROCEDIMIENTO_SIN_DESCRIPCION"].mensaje)


if __name__ == "__main__":
    unittest.main()
