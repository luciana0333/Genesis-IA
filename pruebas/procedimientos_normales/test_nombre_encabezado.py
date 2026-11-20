"""Nombre del encabezado distinto al del procedimiento (usuaria, 19 nov.): Reportes y Negocio, texto de la usuaria."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

_MODULOS = (verificar_procedimiento_normal, verificar_reporte)


def _pa(encabezado: str, nombre: str) -> str:
    return (f"/*****\n{encabezado}\nAUTOR: DCBM\nFECHA: 12/11/2026\nCONTROL DE CAMBIOS\n"
            f"EXEC {nombre} '20260801'\n*****/\nCREATE PROCEDURE {nombre}\n  @dFecha DATE\nAS\nBEGIN\n"
            f"  SET NOCOUNT ON;\n  SELECT @dFecha AS dFecha;\nEND")


def _observaciones(analizar, sql):
    return [h for h in analizar(sql) if h.regla == "NOMBRE_ENCABEZADO_DISTINTO"]


class NombreEncabezadoTest(unittest.TestCase):
    def test_caso_real_en_los_dos_modulos(self):
        sql = _pa("PROCEDIMIENTO: DBO.PA_RPT_ColocCredSaras_Sel_GestionMonitoreoSaras",
                  "DBO.PA_GDD_ColocCredSaras_Sel_GestionMonitoreoSaras")
        for analizar in _MODULOS:
            with self.subTest(modulo=analizar.__name__):
                hallazgos = _observaciones(analizar, sql)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].linea, 2)
                self.assertEqual(hallazgos[0].severidad.value, "bajo")
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó que el encabezado indica el nombre DBO.PA_RPT_ColocCredSaras_Sel_GestionMonitoreoSaras, "
                    "mientras que el procedimiento se crea como DBO.PA_GDD_ColocCredSaras_Sel_GestionMonitoreoSaras. Se "
                    "recomienda actualizar el nombre indicado en el encabezado para que coincida con el procedimiento "
                    "creado y mantener la documentación alineada con el objeto.",
                )

    def test_formas_que_son_el_mismo_nombre(self):
        casos = (
            ("NOMBRE | [DUN].[PA_Producto_Sel_Validacion]", "DUN.PA_Producto_Sel_Validacion"),  # corchetes
            ("Nombre del PA  | dbo.pa_producto_sel_validacion", "DBO.PA_Producto_Sel_Validacion"),  # mayúsculas
            ("PROCEDIMIENTO: PA_Producto_Sel_Validacion", "dbo.PA_Producto_Sel_Validacion"),  # sin esquema
            ("PROCEDIMIENTO: DBCMACICA.dbo.PA_Producto_Sel_Validacion", "dbo.PA_Producto_Sel_Validacion"),  # con base
            ("PROPOSITO | PROCEDIMIENTO ALMACENADO QUE VALIDA REGLAS", "dbo.PA_Producto_Sel_Validacion"),  # no es nombre
            ("NOMBRE: Juan", "dbo.PA_Producto_Sel_Validacion"),  # no es un objeto
        )
        for encabezado, nombre in casos:
            for analizar in _MODULOS:
                with self.subTest(encabezado=encabezado, modulo=analizar.__name__):
                    self.assertEqual(_observaciones(analizar, _pa(encabezado, nombre)), [])

    def test_otro_esquema_si_se_marca(self):
        sql = _pa("PROCEDIMIENTO: dbo.PA_Producto_Sel_Validacion", "DUN.PA_Producto_Sel_Validacion")
        self.assertEqual(len(_observaciones(verificar_procedimiento_normal, sql)), 1)


if __name__ == "__main__":
    unittest.main()
