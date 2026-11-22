"""Riesgo identificado por Genesis: columna convertida al guardarse o unirse con otro tipo de dato (usuaria, 20 nov.).

Caso de la usuaria (captura de Plan Explorer, sin plan): [Expr1005] = CONVERT_IMPLICIT(varchar(10), cc_gestion.cuser),
[Expr1006] = CONVERT_IMPLICIT(decimal(18,9), cc_gestion.nLatitud)… en un Compute Scalar. Genesis no lo marcaba porque
la conversión no estaba en un filtro. Comprobado en SQL Server Express (recursos/conversion_destino_*.sqlplan, reales):
  1) INSERT INTO #destino (VARCHAR(10), DECIMAL(18,9)) SELECT columnas VARCHAR(4), DECIMAL(10,6) → se marca.
  2) el mismo SELECT sin destino                                                             → no hay conversión.
  3) UPDATE … SET D.nLatitud = G.nLatitud (DECIMAL(18,9) ← DECIMAL(10,6))                     → se marca.
"""

import unittest
from pathlib import Path

from app.analizadores.planes_ejecucion.riesgos_genesis import conversion_columna_a_destino
from app.analizadores.planes_ejecucion.servicio import analizar_plan_completo

RECURSOS = Path(__file__).parent / "recursos"


def _observaciones(numero: int, area: str):
    contenido = (RECURSOS / f"conversion_destino_{numero}.sqlplan").read_bytes()
    resultado = analizar_plan_completo(f"conversion_destino_{numero}.sqlplan", contenido, area, None)
    return [h for h in resultado["hallazgos"] if h["regla"] == "CONVERSION_COLUMNA_A_DESTINO"]


def _sentencia(tipo, predicados, advertencias=()):
    return [{"numero": 1, "tipo": tipo, "nodos": [
        {"id": "3", "fisica": "Compute Scalar", "objeto": "", "advertencias": list(advertencias),
         "predicados": predicados}]}]


DEFINIDA = ("[Expr1005] = Scalar Operator(CONVERT_IMPLICIT(varchar(10),[DBCMACICA].[dbo].[cc_gestion].[cuser],0)), "
            "[Expr1006] = Scalar Operator(CONVERT_IMPLICIT(decimal(18,9),[DBCMACICA].[dbo].[cc_gestion].[nLatitud],0))")


class ConversionADestinoTest(unittest.TestCase):
    def test_planes_reales_en_los_dos_modulos(self):
        for area in ("negocio", "reporte"):
            with self.subTest(area=area):
                insert = _observaciones(1, area)
                self.assertEqual(len(insert), 1)
                self.assertEqual(insert[0]["severidad"], "bajo")
                # Texto de la usuaria (20 nov.): corto y directo.
                self.assertEqual(
                    insert[0]["mensaje"],
                    "Se detectó una conversión implícita, ya que los tipos de datos no son iguales. Se recomienda "
                    "corregir la conversión implícita identificada en el Compute Scalar del INSERT.",
                )
                self.assertEqual(_observaciones(2, area), [])
                self.assertIn("en el Compute Scalar del UPDATE.", _observaciones(3, area)[0]["mensaje"])

    def test_caso_de_la_captura(self):
        hallazgo = conversion_columna_a_destino(_sentencia("INSERT", [{"nombre": "Defined Values", "texto": DEFINIDA}]))[0]
        self.assertEqual(hallazgo.nodos, [{"consulta": 1, "nodo": "3", "resaltar": [
            "CONVERT_IMPLICIT(varchar(10),[DBCMACICA].[dbo].[cc_gestion].[cuser],0)",
            "CONVERT_IMPLICIT(decimal(18,9),[DBCMACICA].[dbo].[cc_gestion].[nLatitud],0)"]}])
        self.assertTrue(hallazgo.complementario)

    def test_lo_que_ve_otra_regla_no_se_repite(self):
        # Usada en un filtro: «conversión en un filtro».
        en_filtro = _sentencia("SELECT", [{"nombre": "Defined Values", "texto": DEFINIDA},
                                          {"nombre": "Predicate", "texto": "[Expr1005]=[@cUser]"},
                                          {"nombre": "Predicate", "texto": "[Expr1006]>(0)"}])
        self.assertEqual(conversion_columna_a_destino(en_filtro), [])
        # Ya alertada por SQL Server (Convert Issue), de cualquier tipo.
        alertada = [{"tipo": "conversion", "texto": "Type conversion in expression (CONVERT_IMPLICIT(varchar(10),"
                     "[DBCMACICA].[dbo].[cc_gestion].[cuser],0)) may affect..."},
                    {"tipo": "conversion", "texto": "CONVERT_IMPLICIT(decimal(18,9),[DBCMACICA].[dbo].[cc_gestion]."
                     "[nLatitud],0)"}]
        self.assertEqual(conversion_columna_a_destino(
            _sentencia("INSERT", [{"nombre": "Defined Values", "texto": DEFINIDA}], alertada)), [])
        # Texto (cFecha) a fecha: «columna de texto convertida».
        fecha = ("[Expr1002] = Scalar Operator(CONVERT_IMPLICIT(datetime,[DBCMACICA].[dbo].[Cta].[cFecha],0))")
        self.assertEqual(conversion_columna_a_destino(
            _sentencia("INSERT", [{"nombre": "Defined Values", "texto": fecha}])), [])

    def test_dentro_de_un_calculo_no_es_guardar(self):
        # La columna convertida dentro de una suma o un CASE no se guarda tal cual: no es este caso.
        calculo = ("[Expr1004] = Scalar Operator([DBCMACICA].[dbo].[Cta].[nSaldo]*CONVERT_IMPLICIT(decimal(18,2),"
                   "[DBCMACICA].[dbo].[Cta].[nTasa],0))")
        self.assertEqual(conversion_columna_a_destino(
            _sentencia("SELECT", [{"nombre": "Defined Values", "texto": calculo}])), [])


if __name__ == "__main__":
    unittest.main()
