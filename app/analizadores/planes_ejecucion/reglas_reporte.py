"""Reglas de los planes de ejecución del área Reportes (las define la usuaria, una por una).

Trabajan sobre el mismo árbol que se dibuja (construir_diagrama), así lo que dice
la observación y lo que se ve en el diagrama siempre coinciden.
"""

from __future__ import annotations

import re
from typing import Dict, List

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

_CONVERSION_IMPLICITA = re.compile(r"CONVERT_IMPLICIT\((?:[^()]|\([^()]*\))*\)")

# Qué provoca cada tipo de «Convert Issue» de SQL Server.
_EFECTO = {
    "SeekPlan": "impide buscar en el índice (SeekPlan)",
    "CardinalityEstimate": "altera la estimación de filas (CardinalityEstimate)",
}


def _nombre_operador(nodo: Dict) -> str:
    return nodo["fisica"].upper() if nodo["padre"] is None else nodo["fisica"]


def _conversiones_con_alerta(sentencias: List[Dict]) -> List[Dict]:
    """Conversiones implícitas que SQL Server marcó con alerta (Convert Issue con CONVERT_IMPLICIT).

    Una conversión explícita (CONVERT o CAST escrito en la consulta) o una
    conversión implícita sin alerta no cuentan.
    """
    casos = []
    for sentencia in sentencias:
        for nodo in sentencia["nodos"]:
            for advertencia in nodo["advertencias"]:
                if advertencia["tipo"] != "conversion":
                    continue
                if not _CONVERSION_IMPLICITA.search(advertencia["texto"]):
                    continue
                # «Convert Issue: <Problema> <expresión tal cual el XML>»
                partes = advertencia["texto"].split(" ", 3)
                problema = partes[2] if len(partes) > 2 else ""
                casos.append({
                    "consulta": sentencia["numero"],
                    "nodo": nodo,
                    "expresion": partes[3] if len(partes) > 3 else advertencia["texto"],
                    "efecto": _EFECTO.get(problema, problema),
                })
    return casos


def _ubicacion(caso: Dict, varias_consultas: bool) -> str:
    nodo = caso["nodo"]
    lugar = f"el operador {_nombre_operador(nodo)}"
    if nodo["padre"] is not None:
        lugar += f" (nodo {nodo['id']})"
    if varias_consultas:
        lugar += f" de la consulta {caso['consulta']}"
    return lugar


_RECOMENDACION = (
    "se recomienda revisarla y corregirla usando el mismo tipo de dato en ambos lados de la comparación "
    "(columna, variable o parámetro), ya que SQL Server convierte el valor fila por fila, lo que puede "
    "impedir el uso del índice y alterar la estimación de filas del plan."
)


def _conversion_implicita(sentencias: List[Dict]) -> List[Hallazgo]:
    casos = _conversiones_con_alerta(sentencias)
    if not casos:
        return []
    varias_consultas = len({s["numero"] for s in sentencias}) > 1
    if len(casos) == 1:
        caso = casos[0]
        mensaje = (
            f"Se ha identificado una conversión implícita en {_ubicacion(caso, varias_consultas)}: "
            f"'{caso['expresion']}', que {caso['efecto']}, por lo que {_RECOMENDACION}"
        )
    else:
        consultas = sorted({c["consulta"] for c in casos})
        encabezado = ("la consulta " if len(consultas) == 1 else "las consultas ") + ", ".join(map(str, consultas))
        detalle = "; ".join(
            f"O{_ubicacion(c, varias_consultas)[4:]}: '{c['expresion']}', que {c['efecto']}" for c in casos
        )
        mensaje = (
            f"Se identificaron {len(casos)} conversiones implícitas, en {encabezado}: {detalle}. "
            f"Se recomienda revisarlas y corregirlas usando el mismo tipo de dato en ambos lados de la "
            f"comparación (columna, variable o parámetro), ya que SQL Server convierte el valor fila por fila, "
            f"lo que puede impedir el uso del índice y alterar la estimación de filas del plan."
        )
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.ALTO,
        regla="CONVERSION_IMPLICITA_DETECTADA",
        mensaje=mensaje,
    )
    # Un operador con varias alertas aparece una sola vez (su imagen ya las muestra todas).
    hallazgo.nodos = list({(c["consulta"], c["nodo"]["id"]): {"consulta": c["consulta"], "nodo": c["nodo"]["id"]} for c in casos}.values())
    return [hallazgo]


def analizar_plan_reporte(sentencias: List[Dict]) -> List[Hallazgo]:
    """Hallazgos del plan para el área Reportes, a partir del árbol de construir_diagrama."""
    return _conversion_implicita(sentencias)
