"""«Variables declaradas sin uso» solo revisa variables comunes, no variables de tabla (usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _mensaje(sql, verificar):
    hallazgos = [h for h in verificar(sql) if h.regla == "VARIABLE_DECLARADA_SIN_USO"]
    return hallazgos[0].mensaje if hallazgos else None


class VariablesSinUsoSinTablasTest(unittest.TestCase):
    def test_las_variables_de_tabla_no_se_observan(self):
        sql = ("DECLARE @Contador INT, @CuentaBucle VARCHAR(18), @MontoBucle MONEY\n"
               "DECLARE @TEstadoEmergencia TABLE (Id INT, cCtaCod VARCHAR(18))\n"
               "Declare @TSuspensionPerfecta AS TABLE (Id INT)\n"
               "SET @Contador = 1")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                mensaje = _mensaje(sql, verificar)
                self.assertIn("@CuentaBucle y @MontoBucle.", mensaje)
                self.assertNotIn("@TEstadoEmergencia", mensaje)
                self.assertNotIn("@TSuspensionPerfecta", mensaje)

    def test_solo_variables_de_tabla_no_da_observacion(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertIsNone(_mensaje("DECLARE @T TABLE (n INT)\nSELECT 1", verificar))

    def test_variable_comun_con_nombre_de_tabla_si_se_observa(self):
        self.assertIn("@Tabla", _mensaje("DECLARE @Tabla INT\nSELECT 1", verificar_reporte))


if __name__ == "__main__":
    unittest.main()
