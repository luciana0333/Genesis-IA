"""Nombre del reporte con solo mayúsculas mal (sel → Sel): bajo y señala la parte (pedido de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte


def _nombre(nombre):
    sql = f"CREATE PROCEDURE dbo.{nombre}\nAS\nSELECT 1;"
    return [h for h in verificar_reporte(sql) if h.regla == "REPORTE_NOMBRE_FUERA_DEL_ESTANDAR"]


class NombreReporteMayusculaTest(unittest.TestCase):
    def test_solo_la_mayuscula_va_en_bajo_y_senala_la_parte(self):
        hallazgo = _nombre("PA_GDD_CARTERACREDITOS_sel_ObtenerDesembolsosCartera")[0]
        self.assertEqual(hallazgo.severidad.value, "bajo")
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificó que en el nombre del procedimiento la acción está escrita como «sel» en lugar de «Sel». "
            "Se recomienda renombrarlo como PA_GDD_CARTERACREDITOS_Sel_ObtenerDesembolsosCartera.",
        )

    def test_dos_partes_con_mayusculas(self):
        hallazgo = _nombre("pa_GDD_CARTERACREDITOS_sel_ObtenerDesembolsosCartera")[0]
        self.assertIn("el prefijo está escrito como «pa» en lugar de «PA» y la acción como «sel» en lugar de «Sel».",
                      hallazgo.mensaje)

    def test_si_falta_una_parte_sigue_en_medio_con_el_formato(self):
        hallazgo = _nombre("PA_CARTERACREDITOS_Sel_ObtenerDesembolsosCartera")[0]
        self.assertEqual(hallazgo.severidad.value, "medio")
        self.assertIn("falta el área GDD después de PA_", hallazgo.mensaje)
        self.assertIn("PA_GDD_Tabla_Acción_Finalidad", hallazgo.mensaje)


if __name__ == "__main__":
    unittest.main()
