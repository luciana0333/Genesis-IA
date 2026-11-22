"""Encabezado: el historial sin el título «Control de cambios» también cuenta (usuaria, 22 nov.).

Caso real FluGenSol_InsPropuesta_SP: «HISTORIAL DE FECHA» y unas 80 líneas «2019-03-06  IPAL   Se adapta…», separadas
solo por espacios; Genesis decía que el encabezado no indicaba el control de cambios.
"""
import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)
DATOS = ("PROPOSITO | STORE PROCEDURE Que inserta la propuesta de crédito\nCREADO POR | JURR\n"
         "FECHA CREACION | 03/01/2019\n")
EJEMPLO = "EXEC COLOCACIONES.FluGenSol_InsPropuesta_SP @x\n"
CUERPO = "ALTER PROCEDURE COLOCACIONES.FluGenSol_InsPropuesta_SP (@x XML)\nAS\nBEGIN\n    SELECT 1\nEND"


def _encabezado(historial, verificar):
    sql = f"/*\n{DATOS}{historial}{EJEMPLO}*/\n{CUERPO}"
    return [h.mensaje for h in verificar(sql) if h.regla == "ENCABEZADO_PROCEDIMIENTO"]


class HistorialSinTitulo(unittest.TestCase):
    def test_historial_que_si_cuenta(self):
        casos = {
            "caso real": "HISTORIAL DE FECHA\n  CAMBIOS RESPONSABLE   MOTIVO\n"
                         "2019-03-06  IPAL   Se adapta para unificación de deuda.\n",
            "solo líneas con fecha": "2019-03-06  IPAL   Se adapta para unificación de deuda.\n",
            "con tabulación": "2026-09-09\tJACK   Adecuacion para guardar capacidad de pago\n",
            "fecha con puntos": "2016.11.18\tBJMS\tse cambio para el calculo de saldo\n",
            "fecha día/mes/año": "18/11/2016  BJMS  se cambio para el calculo de saldo\n",
            "fecha mal escrita (2024-29-01)": "2024-29-01  Y127   Mejora para la creacion del repositorio\n",
            "historial de versiones": "Historial de versiones\n",
            "control de versiones": "Control de versiones\n",
        }
        for nombre, historial in casos.items():
            for verificar in MODULOS:
                with self.subTest(nombre, modulo=verificar.__name__):
                    self.assertEqual(_encabezado(historial, verificar), [])

    def test_sin_historial_se_sigue_observando(self):
        casos = {
            "nada": "",
            "solo la fecha de creación repetida": "FECHA | 03/01/2019\n",
            "fecha sola en una línea": "2019-03-06\n",
            "historial vacío con otro texto": "Observaciones generales del proceso\n",
        }
        for nombre, historial in casos.items():
            for verificar in MODULOS:
                with self.subTest(nombre, modulo=verificar.__name__):
                    mensajes = _encabezado(historial, verificar)
                    self.assertEqual(len(mensajes), 1)
                    self.assertIn("no indica el control de cambios", mensajes[0])


if __name__ == "__main__":
    unittest.main()
