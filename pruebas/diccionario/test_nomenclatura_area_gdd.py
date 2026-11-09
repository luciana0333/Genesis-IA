"""Diccionarios: PA_GDD_Tabla_Acción_Finalidad es válido; GDD es el área de Gestión de Datos, no la tabla (8 nov.)."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.diccionario_nomenclatura import nomenclatura_procedimiento

DICCIONARIO = """BEGIN TRY
    BEGIN TRANSACTION ProcesoDiccionario;
    EXEC sys.sp_addextendedproperty @name=N'MS_Description',
        @value=N'Job de carga para BiCobranzasDetalle. Trunca la tabla y carga la data periódicamente.',
        @level0type=N'SCHEMA', @level0name=N'dbo',
        @level1type=N'PROCEDURE', @level1name=N'PA_GDD_CobranzasDetalle_Ins_CargaPeriodica';
    EXEC sys.sp_addextendedproperty @name=N'MS_Description',
        @value=N'Indica la fecha de proceso para la carga de los datos.',
        @level0type=N'SCHEMA', @level0name=N'dbo',
        @level1type=N'PROCEDURE', @level1name=N'PA_GDD_CobranzasDetalle_Ins_CargaPeriodica',
        @level2type=N'PARAMETER', @level2name=N'@dFechaProceso';
    COMMIT TRANSACTION ProcesoDiccionario;
END TRY
BEGIN CATCH
    IF (@@TRANCOUNT > 0) ROLLBACK TRANSACTION ProcesoDiccionario;
    THROW;
END CATCH
GO"""


class NomenclaturaAreaGddTest(unittest.TestCase):
    def test_caso_real_sin_observaciones(self):
        procedimiento = "CREATE PROCEDURE DBO.PA_GDD_CobranzasDetalle_Ins_CargaPeriodica(\n    @dFechaProceso DATE\n)\n"
        self.assertEqual(verificar_diccionario(procedimiento, DICCIONARIO), [])

    def test_con_area_gdd_se_siguen_revisando_las_demas_partes(self):
        casos = {
            "PA_GDD_Cobranzas_Detalle_Ins_Carga":
                ("PROCEDIMIENTO_TABLA_SEPARADA", "(ej.: PA_GDD_CobranzasDetalle_Ins_Carga)"),
            "PA_GDD_Cobranzas_InsCarga": ("PROCEDIMIENTO_ACCION_SIN_SEPARAR", "(ej.: PA_GDD_Cobranzas_Ins_Carga)"),
            "PA_GDD_Cobranzas_Consultar_Saldo":
                ("PROCEDIMIENTO_ACCION_NO_ABREVIADA", "(ej.: PA_GDD_Cobranzas_Sel_Saldo)"),
            "PA_GDD_Cobranzas": ("PROCEDIMIENTO_NOMBRE_INCOMPLETO", "PA_GDD_Tabla_Acción_Finalidad"),
        }
        for nombre, (regla, texto) in casos.items():
            with self.subTest(nombre=nombre):
                [(encontrada, mensaje)] = nomenclatura_procedimiento(nombre)
                self.assertEqual(encontrada, regla)
                self.assertIn(texto, mensaje)

    def test_sin_area_sigue_igual(self):
        self.assertEqual(nomenclatura_procedimiento("PA_Cliente_Sel_Resumen"), [])
        [(regla, mensaje)] = nomenclatura_procedimiento("PA_Garantia_Testimonio_Upd_Estado")
        self.assertEqual(regla, "PROCEDIMIENTO_TABLA_SEPARADA")
        self.assertIn("el formato es PA_Tabla_Acción_Finalidad (ej.: PA_GarantiaTestimonio_Upd_Estado)", mensaje)


if __name__ == "__main__":
    unittest.main()
