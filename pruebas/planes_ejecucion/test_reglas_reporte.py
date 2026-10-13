"""Reglas de planes de ejecución del área Reportes."""

import unittest
from pathlib import Path

from app.analizadores.planes_ejecucion import analizar_plan_reporte, construir_diagrama

EJEMPLO = Path(__file__).resolve().parents[2] / "frontend" / "public" / "ejemplos" / "plan-ejemplo.sqlplan"


def _plan(advertencias_raiz: str, advertencias_compute: str = "", convert_sin_alerta: bool = False) -> str:
    compute = (
        '<ComputeScalar><DefinedValues><DefinedValue><ScalarOperator '
        'ScalarString="CONVERT_IMPLICIT(int,[T].[cCodigo],0)"><Convert Implicit="1" DataType="int"/>'
        '</ScalarOperator></DefinedValue></DefinedValues></ComputeScalar>'
    ) if convert_sin_alerta else ""
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan>
    <Warnings>{advertencias_raiz}</Warnings>
    <RelOp NodeId="0" PhysicalOp="Compute Scalar" LogicalOp="Compute Scalar" EstimatedTotalSubtreeCost="1" EstimateRows="1">
      <Warnings>{advertencias_compute}</Warnings>
      {compute}
      <RelOp NodeId="1" PhysicalOp="Table Scan" LogicalOp="Table Scan" EstimatedTotalSubtreeCost="0.5" EstimateRows="1">
        <TableScan><Object Schema="[dbo]" Table="[Cliente]"/></TableScan>
      </RelOp>
    </RelOp>
  </QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>
"""


IMPLICITA_SEEK = '<PlanAffectingConvert ConvertIssue="Seek Plan" Expression="[DC].[nDocTpo]=CONVERT_IMPLICIT(int,[CL].[nConsEquivalente],0)"/>'
IMPLICITA_CARDINALIDAD = '<PlanAffectingConvert ConvertIssue="Cardinality Estimate" Expression="CONVERT_IMPLICIT(int,[CL].[nConsEquivalente],0)"/>'
EXPLICITA = '<PlanAffectingConvert ConvertIssue="Cardinality Estimate" Expression="CONVERT(date,[T].[FechaRegistro],0)"/>'


def _hallazgos(xml: str):
    return analizar_plan_reporte(construir_diagrama(xml))


class TestConversionImplicitaReporte(unittest.TestCase):
    def test_conversion_implicita_con_alerta_en_el_select(self):
        hallazgos = _hallazgos(_plan(IMPLICITA_SEEK))
        self.assertEqual([h.regla for h in hallazgos], ["CONVERSION_IMPLICITA_DETECTADA"])
        self.assertEqual(hallazgos[0].severidad.value, "alto")
        self.assertIn(
            "Se ha identificado una conversión implícita en el operador SELECT: "
            "«[DC].[nDocTpo]=CONVERT_IMPLICIT(int,[CL].[nConsEquivalente],0)», que impide buscar en el índice (SeekPlan). "
            "Corregir la conversión implícita, verificando que los tipos de datos de la comparación "
            "coincidan para favorecer el rendimiento de la consulta.",
            hallazgos[0].mensaje,
        )
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "raiz"}])

    def test_conversion_implicita_con_alerta_en_un_compute_scalar(self):
        hallazgos = _hallazgos(_plan("", advertencias_compute=IMPLICITA_CARDINALIDAD))
        self.assertIn("en el operador Compute Scalar:", hallazgos[0].mensaje)
        self.assertIn("altera la estimación de filas (CardinalityEstimate)", hallazgos[0].mensaje)
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "0"}])

    def test_varias_conversiones_se_agrupan(self):
        hallazgos = _hallazgos(_plan(IMPLICITA_SEEK, advertencias_compute=IMPLICITA_CARDINALIDAD))
        self.assertEqual(len(hallazgos), 1)
        self.assertTrue(hallazgos[0].mensaje.startswith("Se identificaron 2 conversiones implícitas, en la consulta 1: "))
        self.assertIn("1: Operador SELECT: «[DC].[nDocTpo]=CONVERT_IMPLICIT(", hallazgos[0].mensaje)
        self.assertIn("; Operador Compute Scalar: «CONVERT_IMPLICIT(", hallazgos[0].mensaje)
        self.assertEqual(len(hallazgos[0].nodos), 2)
        self.assertTrue(hallazgos[0].mensaje.endswith(
            "Corregir las conversiones implícitas, verificando que los tipos de datos en las "
            "comparaciones coincidan para favorecer el rendimiento de las consultas."))

    def test_dos_alertas_en_el_mismo_operador_se_muestran_una_vez_en_la_imagen(self):
        hallazgos = _hallazgos(_plan(IMPLICITA_SEEK + IMPLICITA_CARDINALIDAD))
        self.assertIn("Se identificaron 2 conversiones implícitas", hallazgos[0].mensaje)
        self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "raiz"}])

    def test_conversion_explicita_con_alerta_no_cuenta(self):
        self.assertEqual(_hallazgos(_plan(EXPLICITA)), [])

    def test_conversion_implicita_sin_alerta_no_cuenta(self):
        self.assertEqual(_hallazgos(_plan("", convert_sin_alerta=True)), [])

    def test_plan_de_ejemplo_solo_tiene_conversiones_explicitas(self):
        self.assertEqual(analizar_plan_reporte(construir_diagrama(EJEMPLO.read_bytes())), [])

    def test_en_el_diagrama_solo_se_resalta_convert_implicit(self):
        raiz = construir_diagrama(_plan(IMPLICITA_SEEK + EXPLICITA))[0]["nodos"][0]
        resaltados = [a["resaltados"] for a in raiz["advertencias"]]
        self.assertEqual(resaltados, [["CONVERT_IMPLICIT"], []])


    def test_expresion_con_comillas_propias_va_entre_comillas_angulares(self):
        con_texto = '<PlanAffectingConvert ConvertIssue="Cardinality Estimate" Expression="CONVERT_IMPLICIT(nvarchar(50),[A].[cZona],0)=N&apos;SUR&apos;"/>'
        hallazgos = _hallazgos(_plan(con_texto))
        self.assertIn("«CONVERT_IMPLICIT(nvarchar(50),[A].[cZona],0)=N'SUR'»", hallazgos[0].mensaje)


class TestCondicionIf(unittest.TestCase):
    """La condición de un IF (StmtCond) tiene su propio plan: también se revisa."""

    XML = (
        "<ShowPlanXML><BatchSequence><Batch><Statements>"
        '<StmtCond StatementText="IF EXISTS (SELECT 1 FROM dbo.X WHERE c = @n)" StatementType="COND" StatementSubTreeCost="1">'
        "<Condition><QueryPlan><Warnings>" + IMPLICITA_SEEK + "</Warnings>"
        '<QueryTimeStats CpuTime="10" ElapsedTime="40000"/>'
        '<RelOp NodeId="0" PhysicalOp="Clustered Index Scan" LogicalOp="Clustered Index Scan" EstimateRows="1" EstimatedTotalSubtreeCost="1">'
        '<RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="1" ActualRowsRead="3000000" ActualExecutions="1"/></RunTimeInformation>'
        '<IndexScan><Object Schema="[dbo]" Table="[X]"/></IndexScan></RelOp>'
        "</QueryPlan></Condition>"
        '<Then><Statements><StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">'
        '<QueryPlan><QueryTimeStats CpuTime="10" ElapsedTime="1000"/>'
        '<RelOp NodeId="0" PhysicalOp="Constant Scan" LogicalOp="Constant Scan" EstimateRows="1" EstimatedTotalSubtreeCost="0"/>'
        "</QueryPlan></StmtSimple></Statements></Then></StmtCond>"
        "</Statements></Batch></BatchSequence></ShowPlanXML>"
    )

    def test_la_condicion_es_una_sentencia_con_su_plan(self):
        sentencias = construir_diagrama(self.XML)
        self.assertEqual([(s["numero"], s["tipo"]) for s in sentencias], [(1, "IF"), (2, "SELECT")])

    def test_las_reglas_revisan_la_condicion(self):
        hallazgos = {h.regla: h for h in analizar_plan_reporte(construir_diagrama(self.XML), 30)}
        self.assertEqual(set(hallazgos), {"TIEMPO_EJECUCION_SUPERADO", "CONVERSION_IMPLICITA_DETECTADA", "LECTURA_RESIDUAL_ELEVADA"})
        self.assertIn("en la condición IF de la consulta 1", hallazgos["CONVERSION_IMPLICITA_DETECTADA"].mensaje)
        self.assertEqual(hallazgos["TIEMPO_EJECUCION_SUPERADO"].codigo, "IF EXISTS (SELECT 1 FROM dbo.X WHERE c = @n)")


class TestPlanEjemploReportes(unittest.TestCase):
    """El plan de ejemplo de Reportes («Ver ejemplo») debe romper todas sus reglas, y solo donde corresponde."""

    def test_rompe_las_tres_reglas(self):
        ejemplo = EJEMPLO.parent / "plan-ejemplo-reportes.sqlplan"
        hallazgos = {h.regla: h for h in analizar_plan_reporte(construir_diagrama(ejemplo.read_bytes()), 30)}
        self.assertEqual(set(hallazgos), {"TIEMPO_EJECUCION_SUPERADO", "CONVERSION_IMPLICITA_DETECTADA", "LECTURA_RESIDUAL_ELEVADA"})
        self.assertEqual(hallazgos["TIEMPO_EJECUCION_SUPERADO"].nodos, [{"consulta": 2, "nodo": "raiz"}])
        self.assertIn("Se identificaron 3 conversiones implícitas", hallazgos["CONVERSION_IMPLICITA_DETECTADA"].mensaje)
        # Creditos (3.2 M) y Agencias (1.5 M); no Clientes (devuelve todo) ni el Seek de Movimientos.
        self.assertEqual(hallazgos["LECTURA_RESIDUAL_ELEVADA"].nodos, [{"consulta": 1, "nodo": "2"}, {"consulta": 3, "nodo": "2"}])


if __name__ == "__main__":
    unittest.main()
