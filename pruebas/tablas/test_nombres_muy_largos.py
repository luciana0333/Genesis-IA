"""Nombres muy largos (bajo): tablas de más de 30 caracteres y columnas de más de 40."""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla


def _reglas(sql):
    return {h.regla: h for h in verificar_tabla(sql, False)}


class NombresMuyLargosTest(unittest.TestCase):
    def test_tabla_de_mas_de_30(self):
        hallazgo = _reglas(
            "CREATE TABLE CONTABILIDAD.ReclasificacionTipoProvisionAsientos "
            "(nReclasificacionTipoProvisionAsientosId INT IDENTITY(1,1) NOT NULL PRIMARY KEY CLUSTERED)"
        )["TABLA_NOMBRE_MUY_LARGO"]
        self.assertEqual(hallazgo.severidad.value, "bajo")
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificó que el nombre de la tabla CONTABILIDAD.ReclasificacionTipoProvisionAsientos tiene 36 "
            "caracteres. Se recomienda reducir la longitud del nombre de la tabla, ya que resulta demasiado extenso. "
            "El nombre debe ser breve, claro y descriptivo, de manera que permita identificar fácilmente su "
            "finalidad.",
        )

    def test_tabla_de_30_o_menos_no_se_observa(self):
        # 30 caracteres justos (el esquema no cuenta).
        sql = ("CREATE TABLE dbo.EsquemaTotalizadoSupervisoresA "
               "(nEsquemaId INT IDENTITY(1,1) NOT NULL PRIMARY KEY CLUSTERED)")
        self.assertNotIn("TABLA_NOMBRE_MUY_LARGO", _reglas(sql))

    def test_columnas_de_mas_de_40_en_una_sola_observacion(self):
        sql = ("CREATE TABLE dbo.Detalle (nDetalleId INT IDENTITY(1,1) NOT NULL PRIMARY KEY CLUSTERED,\n"
               " nNumeroOtrasOperacionesSinCostoCajeroAutomatico INT NOT NULL,\n"
               " nImporteCostoOperacionesAdicionalesVentanilla INT NOT NULL,\n"
               " nMontoAseguradoRoboTarjetaDebito INT NOT NULL)")
        hallazgo = _reglas(sql)["COLUMNA_NOMBRE_MUY_LARGO"]
        self.assertEqual(hallazgo.severidad.value, "bajo")
        self.assertEqual(hallazgo.lineas, [2, 3])
        self.assertIn("nNumeroOtrasOperacionesSinCostoCajeroAutomatico de 47 caracteres", hallazgo.mensaje)
        self.assertIn("nImporteCostoOperacionesAdicionalesVentanilla de 45 caracteres", hallazgo.mensaje)
        self.assertNotIn("nMontoAseguradoRoboTarjetaDebito", hallazgo.mensaje)  # 32: dentro del límite
        self.assertTrue(hallazgo.mensaje.endswith(
            "Se recomienda usar nombres de máximo 40 caracteres, ya que un nombre largo dificulta escribir y "
            "leer las consultas que usan la columna."))


if __name__ == "__main__":
    unittest.main()
