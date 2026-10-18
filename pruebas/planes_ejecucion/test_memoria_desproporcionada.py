"""Negocio: sobreestimación de memoria por diferencia (aunque el XML no traiga la alerta Excessive Grant)."""

import unittest

from app.analizadores.planes_ejecucion import analizar_plan_negocio, construir_diagrama


def _plan(concedida_kb: int, usada_kb: int, con_alerta: bool = False) -> str:
    alerta = (
        f'<Warnings><MemoryGrantWarning GrantWarningKind="Excessive Grant" RequestedMemory="{concedida_kb}" '
        f'GrantedMemory="{concedida_kb}" MaxUsedMemory="{usada_kb}"/></Warnings>'
    ) if con_alerta else ""
    return f"""
<ShowPlanXML><BatchSequence><Batch><Statements>
<StmtSimple StatementType="SELECT" StatementSubTreeCost="1" StatementText="SELECT 1">
  <QueryPlan>
    {alerta}
    <MemoryGrantInfo RequestedMemory="{concedida_kb}" GrantedMemory="{concedida_kb}" MaxUsedMemory="{usada_kb}"/>
    <RelOp NodeId="0" PhysicalOp="Sort" LogicalOp="Sort" EstimateRows="1" EstimatedTotalSubtreeCost="1">
      <Sort><OrderBy/></Sort>
    </RelOp>
  </QueryPlan>
</StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>"""


def _memoria(xml: str):
    return [h for h in analizar_plan_negocio(construir_diagrama(xml)) if h.regla == "MEMORIA_SOBREESTIMADA"]


class TestMemoriaDesproporcionada(unittest.TestCase):
    def test_reserva_enorme_sin_alerta_se_marca(self):
        hallazgos = _memoria(_plan(200 * 1024, 30))
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se observa una sobreestimación en la reserva de memoria, ya que se solicitan y reservan 200 MB, "
            "mientras que solo se utilizan 30 KB durante la ejecución. Corregir la sobreestimación de memoria, ya "
            "que la cantidad reservada es muy alta para la cantidad utilizada; si bien se trata de tablas "
            "transaccionales, se debe reducir lo más posible.",
        )

    def test_uso_razonable_no_se_marca(self):
        self.assertEqual(_memoria(_plan(200 * 1024, 50 * 1024)), [])  # usa el 25 %

    def test_reserva_pequena_no_se_marca(self):
        self.assertEqual(_memoria(_plan(5 * 1024, 10)), [])  # menos de 10 MB

    def test_limites_exactos(self):
        self.assertEqual(len(_memoria(_plan(10 * 1024, 1024))), 1)  # 10 MB y 10 %: se marca
        self.assertEqual(_memoria(_plan(10 * 1024, 1025)), [])  # un poco más del 10 %

    def test_con_alerta_y_desproporcion_sale_una_sola_vez(self):
        self.assertEqual(len(_memoria(_plan(200 * 1024, 30, con_alerta=True))), 1)

    def test_la_alerta_de_sql_server_se_sigue_respetando(self):
        # SQL Server pone Excessive Grant aunque no cumpla nuestro criterio: se marca igual.
        self.assertEqual(len(_memoria(_plan(5 * 1024, 10, con_alerta=True))), 1)


if __name__ == "__main__":
    unittest.main()
