"""Lectura residual de la misma tabla e índice en varias consultas: una observación y una imagen."""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_negocio, analizar_plan_reporte, construir_diagrama


def _consulta(devueltas: int, leidas: int = 4_416_532, tabla: str = "Producto", indice: str = "IX_nPrdEstado",
              costo_scan: float = 0.59) -> str:
    """Compute Scalar ← Parallelism ← Index Scan, como en el plan de la usuaria."""
    return f"""
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT P.cCtaCod FROM dbo.{tabla} P">
  <QueryPlan>
    <RelOp NodeId="0" PhysicalOp="Compute Scalar" LogicalOp="Compute Scalar" EstimatedTotalSubtreeCost="1" EstimateRows="10">
      <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="{devueltas}" ActualExecutions="1"/></RunTimeInformation>
      <ComputeScalar>
        <RelOp NodeId="1" PhysicalOp="Parallelism" LogicalOp="Repartition Streams" EstimatedTotalSubtreeCost="{costo_scan + 0.2}" EstimateRows="10">
          <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="{devueltas}" ActualExecutions="1"/></RunTimeInformation>
          <Parallelism>
            <RelOp NodeId="2" PhysicalOp="Index Scan" LogicalOp="Index Scan" EstimatedTotalSubtreeCost="{costo_scan}" EstimateRows="10">
              <RunTimeInformation><RunTimeCountersPerThread Thread="0" ActualRows="{devueltas}" ActualRowsRead="{leidas}" ActualExecutions="1"/></RunTimeInformation>
              <IndexScan>
                <Object Database="[DBCMACICA]" Schema="[dbo]" Table="[{tabla}]" Index="[{indice}]" Alias="[P]"/>
                <Predicate><ScalarOperator ScalarString="PROBE([Bitmap1011],[DBCMACICA].[dbo].[{tabla}].[cCtaCod] as [P].[cCtaCod])"/></Predicate>
              </IndexScan>
            </RelOp>
          </Parallelism>
        </RelOp>
      </ComputeScalar>
    </RelOp>
  </QueryPlan>
</StmtSimple>"""


def _plan(*consultas: str) -> str:
    return f"<ShowPlanXML><BatchSequence><Batch><Statements>{''.join(consultas)}</Statements></Batch></BatchSequence></ShowPlanXML>"


def _residual(xml: str, analizar=analizar_plan_reporte):
    return [h for h in analizar(construir_diagrama(xml)) if h.regla == "LECTURA_RESIDUAL_ELEVADA"]


class TestLecturaResidualRepetida(unittest.TestCase):
    def test_caso_de_la_usuaria_una_observacion_y_la_imagen_mas_grave(self):
        # Consulta 1: 4,416,532 leídas → 18,243 devueltas (la más grave); consulta 2: → 41,028.
        for analizar in (analizar_plan_reporte, analizar_plan_negocio):
            with self.subTest(modulo=analizar.__name__):
                hallazgos = _residual(_plan(_consulta(18_243), _consulta(41_028, costo_scan=0.584)), analizar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se ha identificado una lectura residual elevada sobre la tabla [dbo].[Producto] (Index Scan, "
                    "índice IX_nPrdEstado), que se repite en 2 consultas (1 y 2): se leen 4,416,532 filas en cada "
                    "una y solo se devuelven 18,243 (consulta 1) y 41,028 (consulta 2). Optimizar las condiciones "
                    "de filtrado o revisar los índices existentes, ya que la lectura abarca la totalidad o casi la "
                    "totalidad de los registros.",
                )
                self.assertEqual(hallazgos[0].nodos, [{"consulta": 1, "nodo": "2"}])

    def test_la_imagen_es_la_del_caso_mas_grave_aunque_venga_despues(self):
        hallazgo = _residual(_plan(_consulta(41_028), _consulta(18_243)))[0]
        self.assertEqual(hallazgo.nodos, [{"consulta": 2, "nodo": "2"}])

    def test_lecturas_distintas_se_detallan_por_consulta(self):
        hallazgo = _residual(_plan(_consulta(18_243), _consulta(41_028, leidas=2_000_000)))[0]
        self.assertIn("que se repite en 2 consultas (1 y 2): en la consulta 1 se leen 4,416,532 filas y solo se "
                      "devuelven 18,243 y en la consulta 2 se leen 2,000,000 filas y solo se devuelven 41,028.",
                      hallazgo.mensaje)

    def test_otro_indice_de_la_misma_tabla_va_aparte(self):
        hallazgo = _residual(_plan(_consulta(18_243), _consulta(41_028, indice="IX_cCtaCod")))[0]
        self.assertTrue(hallazgo.mensaje.startswith("Se identificaron 2 lecturas residuales elevadas, en las consultas 1, 2: "))
        self.assertEqual(len(hallazgo.nodos), 2)

    def test_otra_tabla_va_aparte(self):
        hallazgo = _residual(_plan(_consulta(18_243), _consulta(41_028, tabla="Credito")))[0]
        self.assertIn("La tabla [dbo].[Credito] (Index Scan, índice IX_nPrdEstado, consulta 2)", hallazgo.mensaje)
        self.assertEqual(len(hallazgo.nodos), 2)


if __name__ == "__main__":
    unittest.main()
