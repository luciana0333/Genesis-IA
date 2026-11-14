"""Riesgo identificado por Genesis: texto (SUBSTRING, LEFT, RIGHT) convertido implícitamente a número.

SQL Server no lo alerta (está en el SELECT o en un CASE), pero si el dato no es numérico la consulta se cae.
Va aparte («Riesgos identificados por Genesis»), en Reportes y en Negocio.
"""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_negocio, analizar_plan_reporte, construir_diagrama


def _plan(expresiones):
    valores = "".join(
        f'<DefinedValue><ColumnReference Column="Expr100{i}" /><ScalarOperator ScalarString="{e}" /></DefinedValue>'
        for i, e in enumerate(expresiones)
    )
    return f"""
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan"><BatchSequence><Batch><Statements>
<StmtSimple StatementId="2" StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
<QueryPlan>
<RelOp NodeId="0" PhysicalOp="Compute Scalar" LogicalOp="Compute Scalar" EstimatedTotalSubtreeCost="1" EstimateRows="10">
<ComputeScalar><DefinedValues>{valores}</DefinedValues>
<RelOp NodeId="1" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan" EstimatedTotalSubtreeCost="1" EstimateRows="10">
<IndexScan><Object Schema="[dbo]" Table="[Cuenta]" Index="[PK_Cuenta]"/></IndexScan></RelOp>
</ComputeScalar></RelOp>
</QueryPlan></StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>"""


_CASE = ("CASE WHEN CONVERT_IMPLICIT(int,substring([DBCMACICA].[dbo].[Cuenta].[cCtaCod] as [A].[cCtaCod],(9),(1)),0)=(1) "
         "THEN 'SOLES' ELSE 'DOLARES' END")


def _riesgos(xml, analizar=analizar_plan_negocio):
    return [h for h in analizar(construir_diagrama(xml)) if h.regla == "CONVERSION_TEXTO_A_NUMERO"]


class RiesgoTextoANumeroTest(unittest.TestCase):
    def test_comparacion_en_un_case_en_los_dos_modulos(self):
        for analizar in (analizar_plan_reporte, analizar_plan_negocio):
            with self.subTest(modulo=analizar.__name__):
                hallazgos = _riesgos(_plan([_CASE]), analizar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
                self.assertTrue(hallazgos[0].complementario)
                self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "0"}])
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó una conversión implícita al comparar SUBSTRING(cCtaCod, 9, 1) con el valor "
                    "numérico 1. Se recomienda corregir la conversión implícita identificada, realizando la comparación "
                    "con un valor del mismo tipo de dato y validando que el cambio no altere el resultado esperado.",
                )

    def test_misma_comparacion_repetida_sale_una_vez(self):
        self.assertEqual(_riesgos(_plan([_CASE, _CASE.replace("'SOLES'", "'S'")]))[0].mensaje.count("SUBSTRING(cCtaCod, 9, 1) con el valor numérico 1"), 1)

    def test_left_y_constante_antes(self):
        expresion = "CASE WHEN (10)=CONVERT_IMPLICIT(smallint,left([dbo].[Cuenta].[cCodigo],(2)),0) THEN 1 END"
        mensaje = _riesgos(_plan([expresion]))[0].mensaje
        self.assertIn("al comparar LEFT(cCodigo, 2) con el valor numérico 10.", mensaje)

    def test_asignacion_sin_comparacion_no_se_observa(self):
        # SELECT @nMoneda = SUBSTRING(cCtaCod, 9, 1) con @nMoneda INT: suele ser intencional (decisión de la usuaria).
        expresion = "CONVERT_IMPLICIT(int,substring([DBCMACICA].[dbo].[Cuenta].[cCtaCod],(9),(1)),0)"
        self.assertEqual(_riesgos(_plan([expresion])), [])

    def test_misma_comparacion_en_dos_operadores_marca_uno(self):
        # Caso de la usuaria: SQL Server calcula el mismo «= 1» en dos Compute Scalar (nodos 0 y 7).
        from app.analizadores.planes_ejecucion.riesgos_genesis import conversion_texto_a_numero
        predicado = {"nombre": "Defined Values", "texto": _CASE}
        sentencias = [{"numero": 2, "nodos": [{"id": "0", "predicados": [predicado]},
                                               {"id": "7", "predicados": [predicado]}]}]
        hallazgos = conversion_texto_a_numero(sentencias)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 2, "nodo": "0"}])

    def test_varios_casos_en_lista(self):
        otro = "CASE WHEN CONVERT_IMPLICIT(int,right([dbo].[Cuenta].[cCodigo],(1)),0)&lt;&gt;(0) THEN 1 END"
        mensaje = _riesgos(_plan([_CASE, otro]))[0].mensaje
        self.assertEqual(
            mensaje,
            "Se identificaron conversiones implícitas al comparar: SUBSTRING(cCtaCod, 9, 1) con el valor numérico 1; "
            "RIGHT(cCodigo, 1) con el valor numérico 0. Se recomienda corregir las conversiones implícitas "
            "identificadas, realizando cada comparación con un valor del mismo tipo de dato y validando que el cambio "
            "no altere el resultado esperado.")

    def test_no_se_observa(self):
        casos = (
            "CONVERT_IMPLICIT(varchar(25),[@cUltimaActualizacion],0)",          # texto a texto (BienesAsegurados)
            "CONVERT_IMPLICIT(int,[dbo].[Cuenta].[nNumero],0)",                 # columna sin SUBSTRING/LEFT/RIGHT
            "CONVERT_IMPLICIT(int,XML Reader with XPath filter.[value],0)",     # valor leído de un XML
            "CASE WHEN substring([dbo].[Cuenta].[cCtaCod],(9),(1))='1' THEN 1 END",  # ya compara con texto
            "CONVERT_IMPLICIT(nvarchar(10),substring([dbo].[Cuenta].[cCtaCod],(9),(1)),0)",  # a texto, no a número
        )
        for expresion in casos:
            with self.subTest(expresion=expresion):
                self.assertEqual(_riesgos(_plan([expresion])), [])


if __name__ == "__main__":
    unittest.main()
