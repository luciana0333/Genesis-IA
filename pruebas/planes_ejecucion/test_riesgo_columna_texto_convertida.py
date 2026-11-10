"""Riesgo identificado por Genesis: columna de texto convertida implícitamente a fecha o número (usuaria, 9 nov.).

Caso de la usuaria (Plan Explorer lo resalta, SQL Server no lo alerta): [Expr1005]=CONVERT_IMPLICIT(datetime,
[#CtaSaldoAuxTemp].[cFecha],0) en un Compute Scalar. Va aparte («Riesgos identificados por Genesis»), en Reportes y Negocio.
"""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_negocio, analizar_plan_reporte, construir_diagrama
from app.analizadores.planes_ejecucion.riesgos_genesis import columna_texto_convertida
from pruebas.planes_ejecucion.test_riesgo_texto_a_numero import _plan

_FECHA = "CONVERT_IMPLICIT(datetime,[#CtaSaldoAuxTemp].[cFecha],0)"
# Captura 2: el mismo valor dentro de la función de partición del INSERT.
_PARTICION = ("RangePartitionNew(CONVERT_IMPLICIT(datetime,[#CtaSaldoAuxTemp].[cFecha],0),(0),"
              "'2010-12-31 00:00:00.000','2011-01-31 00:00:00.000')")


def _riesgos(xml, analizar=analizar_plan_negocio):
    return [h for h in analizar(construir_diagrama(xml)) if h.regla == "COLUMNA_TEXTO_CONVERTIDA"]


class ColumnaTextoConvertidaTest(unittest.TestCase):
    def test_caso_de_la_usuaria_en_los_dos_modulos(self):
        for analizar in (analizar_plan_reporte, analizar_plan_negocio):
            with self.subTest(modulo=analizar.__name__):
                hallazgos = _riesgos(_plan([_FECHA, _PARTICION]), analizar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
                self.assertTrue(hallazgos[0].complementario)
                self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "0"}])
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó una conversión implícita sobre la columna cFecha de #CtaSaldoAuxTemp a datetime. "
                    "Se recomienda revisar el tipo de dato de la columna, ya que un valor con "
                    "formato inválido genera un error de conversión.",
                )

    def test_columna_con_base_esquema_y_alias_a_numero(self):
        expresion = "CONVERT_IMPLICIT(int,[DBCMACICA].[dbo].[Cuenta].[cCodigo] as [A].[cCodigo],0)"
        self.assertIn("cCodigo de Cuenta a int. ", _riesgos(_plan([expresion]))[0].mensaje)

    def test_varias_columnas_en_lista(self):
        otra = "CONVERT_IMPLICIT(numeric(18,2),#Saldos.[cMonto] as [S].[cMonto],0)"
        mensaje = _riesgos(_plan([_FECHA, otra]))[0].mensaje
        self.assertEqual(
            mensaje,
            "Se identificaron conversiones implícitas sobre las columnas: cFecha de #CtaSaldoAuxTemp a datetime; "
            "cMonto de #Saldos a numeric(18,2). Se recomienda revisar el tipo de dato "
            "de las columnas, ya que un valor con formato inválido genera un error de conversión.")

    def test_lo_que_no_se_observa(self):
        no_cuentan = [
            "CONVERT_IMPLICIT(int,[Expr1014],0)",                                          # COUNT(*)
            "CONVERT_IMPLICIT(int,XML Reader with XPath filter.[value],0)",               # valor de un XML
            "CONVERT_IMPLICIT(date,[@dFechaMemorando],0)",                                 # variable
            "CONVERT_IMPLICIT(int,[DBCMACICA].[Garantia].[GarantiaProvision].[nTipoGarantia],0)",  # número a número
            "CONVERT_IMPLICIT(money,#Garantias.[Porcentaje] as [DG].[Porcentaje],0)",       # sin prefijo de texto
            "CONVERT_IMPLICIT(int,substring([dbo].[Cuenta].[cCtaCod],(9),(1)),0)",          # SUBSTRING: otra regla
            "CONVERT_IMPLICIT(varchar(20),[dbo].[Cuenta].[cCodigo],0)",                     # texto a texto
            "CONVERT_IMPLICIT(int,[dbo].[Cuenta].[codigo],0)",                              # sin el prefijo del estándar
        ]
        self.assertEqual(_riesgos(_plan(no_cuentan)), [])

    def test_la_que_sql_server_ya_alerto_no_se_repite(self):
        predicado = {"nombre": "Predicate", "texto": f"{_FECHA}=[@dFecha]"}
        # La alerta usa el alias corto; el Compute Scalar, el nombre completo: es la misma conversión.
        alerta = {"tipo": "conversion", "texto": "Convert Issue: SeekPlan CONVERT_IMPLICIT(datetime,[T].[cFecha],0)"}
        sentencias = [{"numero": 1, "nodos": [{"id": "3", "predicados": [predicado], "advertencias": [alerta]}]}]
        self.assertEqual(columna_texto_convertida(sentencias), [])

    def test_misma_columna_en_dos_consultas(self):
        predicado = {"nombre": "Defined Values", "texto": f"[Expr1005] = Scalar Operator({_FECHA})"}
        sentencias = [{"numero": n, "nodos": [{"id": "1", "predicados": [predicado]}]} for n in (2, 4)]
        hallazgo = columna_texto_convertida(sentencias)[0]
        self.assertIn("a datetime. Se recomienda", hallazgo.mensaje)
        self.assertNotIn("consulta", hallazgo.mensaje)
        self.assertEqual(hallazgo.nodos, [{"consulta": 2, "nodo": "1"}, {"consulta": 4, "nodo": "1"}])


if __name__ == "__main__":
    unittest.main()
