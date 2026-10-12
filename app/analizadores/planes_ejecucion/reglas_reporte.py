"""Reglas de los planes de ejecución del área Reportes (las define la usuaria, una por una).

Trabajan sobre el mismo árbol que se dibuja (construir_diagrama), así lo que dice
la observación y lo que se ve en el diagrama siempre coinciden.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

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


# Lectura residual: filas leídas (ActualRowsRead) a partir de las cuales se marca.
LECTURA_RESIDUAL_MINIMA = 1_000_000


def _cifra(valor: float) -> str:
    return f"{valor:,.0f}"


def _lectura_residual(sentencias: List[Dict]) -> List[Hallazgo]:
    """Scans que leen más de un millón de filas y devuelven menos de las que leen.

    Un Scan (Table Scan, Clustered Index Scan, Index Scan) recorre la tabla completa
    o casi completa y descarta con el filtro las filas que no sirven: «lectura residual».
    Un Seek no se marca: ya busca directo en el índice, es el acceso óptimo.
    """
    varias_consultas = len({s["numero"] for s in sentencias}) > 1
    casos = []
    for sentencia in sentencias:
        for nodo in sentencia["nodos"]:
            if "scan" not in nodo["fisica"].lower():
                continue
            leidas, devueltas = nodo.get("filasLeidas"), nodo.get("filasReales")
            if leidas is None or devueltas is None or leidas <= LECTURA_RESIDUAL_MINIMA or devueltas >= leidas:
                continue
            casos.append({"consulta": sentencia["numero"], "nodo": nodo, "leidas": leidas, "devueltas": devueltas})
    if not casos:
        return []

    def describir(caso: Dict) -> str:
        nodo = caso["nodo"]
        tabla = f"la tabla {nodo['objeto']}" if nodo.get("objeto") else "una tabla"
        lugar = f"{tabla} ({_nombre_operador(nodo)}, nodo {nodo['id']}"
        lugar += f", consulta {caso['consulta']})" if varias_consultas else ")"
        return (f"{lugar}, que se lee en su totalidad o casi en su totalidad: se leen {_cifra(caso['leidas'])} filas "
                f"y solo se devuelven {_cifra(caso['devueltas'])}")

    accion = (
        "optimizar sus filtros o revisar sus índices existentes, ya que leer y descartar millones de filas eleva "
        "las lecturas, el tiempo de ejecución y el consumo de recursos del servidor."
    )
    if len(casos) == 1:
        mensaje = f"Se ha identificado una lectura residual elevada sobre {describir(casos[0])}, por lo que se recomienda {accion}"
    else:
        consultas = sorted({c["consulta"] for c in casos})
        encabezado = ("la consulta " if len(consultas) == 1 else "las consultas ") + ", ".join(map(str, consultas))
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(c) for c in casos))
        mensaje = (f"Se identificaron {len(casos)} lecturas residuales elevadas, en {encabezado}: {detalle}. "
                   f"Se recomienda {accion}")
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.ALTO,
        regla="LECTURA_RESIDUAL_ELEVADA",
        mensaje=mensaje,
    )
    hallazgo.nodos = [{"consulta": c["consulta"], "nodo": c["nodo"]["id"]} for c in casos]
    return [hallazgo]


def _segundos(valor: float) -> str:
    return f"{valor:,.2f} s" if valor < 10 else f"{valor:,.1f} s"


def _tiempo_superado(sentencias: List[Dict], limite_s: Optional[float]) -> List[Hallazgo]:
    """El procedimiento tarda más que el límite de tiempo del área (suma de Duration de sus consultas)."""
    con_tiempo = [s for s in sentencias if s.get("duracionMs") is not None]
    if not limite_s or not con_tiempo:
        return []
    total_s = sum(s["duracionMs"] for s in con_tiempo) / 1000
    if total_s <= limite_s:
        return []
    lenta = max(con_tiempo, key=lambda s: s["duracionMs"])
    lenta_s = lenta["duracionMs"] / 1000
    bloque = f"consulta {lenta['numero']}, {_segundos(lenta_s)}"
    if len(con_tiempo) > 1:
        bloque += f", el {lenta_s / total_s:.0%} del tiempo total"
    mensaje = (
        f"El procedimiento supera el umbral de tiempo establecido: su ejecución tomó {_segundos(total_s)} y el "
        f"límite es de {limite_s:g} s (+{_segundos(total_s - limite_s)}). Se recomienda optimizar la siguiente "
        f"consulta ({bloque}), ya que toma la mayor parte del tiempo."
    )
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.ALTO,
        regla="TIEMPO_EJECUCION_SUPERADO",
        mensaje=mensaje,
    )
    hallazgo.nodos = [{"consulta": lenta["numero"], "nodo": "raiz"}]
    hallazgo.codigo = lenta.get("codigo") or lenta.get("texto", "")  # el bloque, tal cual el XML
    return [hallazgo]


def analizar_plan_reporte(sentencias: List[Dict], limite_s: Optional[float] = None) -> List[Hallazgo]:
    """Hallazgos del plan para el área Reportes, a partir del árbol de construir_diagrama.

    limite_s: límite de tiempo del área en segundos (None = sin límite definido).
    """
    return (
        _tiempo_superado(sentencias, limite_s)
        + _conversion_implicita(sentencias)
        + _lectura_residual(sentencias)
    )
