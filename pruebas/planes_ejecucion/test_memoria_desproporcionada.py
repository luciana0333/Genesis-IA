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
        self.assertEqual(_memoria(_plan(5 * 1024, 10)), [])  # menos de 80 MB
        self.assertEqual(_memoria(_plan(79 * 1024, 10)), [])

    def test_limites_exactos(self):
        self.assertEqual(len(_memoria(_plan(80 * 1024, 8 * 1024))), 1)  # 80 MB y 10 %: se marca
        self.assertEqual(_memoria(_plan(80 * 1024, 8 * 1024 + 1)), [])  # un poco más del 10 %

    def test_ejemplo_de_la_usuaria_80_mb_y_1_mb(self):
        self.assertEqual(len(_memoria(_plan(80 * 1024, 1024))), 1)

    def test_con_alerta_y_desproporcion_sale_una_sola_vez(self):
        self.assertEqual(len(_memoria(_plan(200 * 1024, 30, con_alerta=True))), 1)

    def test_alerta_con_reserva_minima_no_se_marca(self):
        # Caso de la usuaria: Excessive Grant de 1 MB reservado y 16 KB usados; en un entorno transaccional
        # es mínimo. La alerta se sigue viendo en el diagrama, pero no es observación.
        self.assertEqual(_memoria(_plan(1024, 16, con_alerta=True)), [])
        self.assertEqual(_memoria(_plan(79 * 1024, 16, con_alerta=True)), [])

    def test_alerta_desde_80_mb_se_marca(self):
        self.assertEqual(len(_memoria(_plan(80 * 1024, 16, con_alerta=True))), 1)


if __name__ == "__main__":
    unittest.main()
