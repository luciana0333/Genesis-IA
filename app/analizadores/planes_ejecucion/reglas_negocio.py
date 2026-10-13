"""Reglas de los planes de ejecución del área Negocio (procedimientos transaccionales).

Las define la usuaria. Conversión implícita y lectura residual son las mismas de
Reportes; Table Scan, spill y sobreestimación de memoria son propias de Negocio.
Igual que en Reportes, trabajan sobre el árbol de construir_diagrama: lo que dice
la observación y lo que se ve en el diagrama siempre coinciden.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.analizadores.planes_ejecucion.reglas_reporte import (
    _conversion_implicita,
    _lectura_residual,
    _nombre_operador,
)
from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad


def _hallazgo(regla: str, severidad: Severidad, mensaje: str, casos: List[Dict]) -> Hallazgo:
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=severidad,
        regla=regla,
        mensaje=mensaje,
    )
    # Un operador aparece una sola vez en la imagen, aunque tenga varios casos.
    hallazgo.nodos = list({
        (c["consulta"], c["nodo"]["id"]): {"consulta": c["consulta"], "nodo": c["nodo"]["id"]} for c in casos
    }.values())
    return hallazgo


def _encabezado(casos: List[Dict]) -> str:
    consultas = sorted({c["consulta"] for c in casos})
    return ("la consulta " if len(consultas) == 1 else "las consultas ") + ", ".join(map(str, consultas))


def _cifra(valor: Optional[float]) -> str:
    return f"{valor:,.0f}"


# --- Table Scan ------------------------------------------------------------

def _es_temporal(objeto: str) -> bool:
    """#tabla, ##tabla o @variable: las crea el propio procedimiento."""
    nombre = objeto.split(".")[-1].strip("[]")
    return nombre.startswith(("#", "@"))


def _table_scan(sentencias: List[Dict]) -> List[Hallazgo]:
    """Table Scan sobre tablas físicas: en un procedimiento de negocio se recorre la tabla completa."""
    varias = len({s["numero"] for s in sentencias}) > 1
    casos = [
        {"consulta": s["numero"], "nodo": n}
        for s in sentencias
        for n in s["nodos"]
        if n["fisica"] == "Table Scan" and n.get("objeto") and not _es_temporal(n["objeto"])
    ]
    if not casos:
        return []

    def describir(caso: Dict) -> str:
        nodo = caso["nodo"]
        texto = f"la tabla {nodo['objeto']}"
        if varias:
            texto += f" (consulta {caso['consulta']})"
        leidas = nodo.get("filasLeidas")
        devueltas = nodo.get("filasReales")
        if leidas is not None and devueltas is not None:
            texto += f": se leen {_cifra(leidas)} filas y se devuelven {_cifra(devueltas)}"
        return texto

    recomendacion = (
        "Se recomienda revisar los filtros de la consulta o crear un índice adecuado sobre las columnas que se "
        "filtran, ya que en un procedimiento de negocio recorrer la tabla completa aumenta el tiempo de respuesta "
        "y los bloqueos."
    )
    if len(casos) == 1:
        mensaje = f"Se ha identificado un Table Scan sobre {describir(casos[0])}. {recomendacion}"
    else:
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(c) for c in casos))
        mensaje = f"Se identificaron {len(casos)} Table Scan, en {_encabezado(casos)}: {detalle}. {recomendacion}"
    return [_hallazgo("TABLE_SCAN_DETECTADO", Severidad.ALTO, mensaje, casos)]


# --- Spill a TempDB ---------------------------------------------------------

def _spill(sentencias: List[Dict]) -> List[Hallazgo]:
    """Operadores con la alerta SpillToTempDb del XML: la memoria no alcanzó y usaron TempDB."""
    varias = len({s["numero"] for s in sentencias}) > 1
    casos = [
        {"consulta": s["numero"], "nodo": n, "datos": a.get("datos", {})}
        for s in sentencias
        for n in s["nodos"]
        for a in n["advertencias"]
        if a["tipo"] == "spill"
    ]
    if not casos:
        return []

    def describir(caso: Dict) -> str:
        nodo = caso["nodo"]
        texto = f"el operador {_nombre_operador(nodo)}"
        if nodo.get("objeto"):
            texto += f" sobre {nodo['objeto']}"
        if varias:
            texto += f" de la consulta {caso['consulta']}"
        escritas = caso["datos"].get("escritas")
        if escritas is not None:
            texto += f": se escribieron {_cifra(escritas)} páginas en TempDB"
        return texto

    recomendacion = (
        "Se recomienda revisar la estimación de filas y los índices de la consulta, ya que al no alcanzar la "
        "memoria asignada SQL Server escribe en disco (TempDB) y la ejecución se vuelve más lenta."
    )
    if len(casos) == 1:
        mensaje = f"Se ha identificado un spill a TempDB en {describir(casos[0])}. {recomendacion}"
    else:
        detalle = "; ".join("O" + d[4:] for d in (describir(c) for c in casos))  # «el operador…» → «Operador…»
        mensaje = f"Se identificaron {len(casos)} spills a TempDB, en {_encabezado(casos)}: {detalle}. {recomendacion}"
    return [_hallazgo("SPILL_TEMPDB_DETECTADO", Severidad.ALTO, mensaje, casos)]


# --- Sobreestimación de memoria ------------------------------------------------

def _memoria(sentencias: List[Dict]) -> List[Hallazgo]:
    """Sentencias con la alerta Excessive Grant del XML (memoria reservada muy por encima de la usada)."""
    varias = len({s["numero"] for s in sentencias}) > 1
    casos = [
        {"consulta": s["numero"], "nodo": n, "datos": a.get("datos", {})}
        for s in sentencias
        for n in s["nodos"]
        if n["padre"] is None
        for a in n["advertencias"]
        if a["tipo"] == "memoria"
    ]
    if not casos:
        return []

    def describir(caso: Dict) -> str:
        datos = caso["datos"]
        solicitada, concedida, usada = datos.get("solicitada"), datos.get("concedida"), datos.get("usada")
        reserva = (f"se solicitan y reservan {concedida}" if solicitada == concedida
                   else f"se solicitan {solicitada} y se reservan {concedida}")
        return f"{reserva}, mientras que solo se utilizan {usada} durante la ejecución"

    recomendacion = (
        "Se recomienda revisar las estadísticas de las tablas y el tamaño de las columnas de la consulta, ya que "
        "la memoria reservada y no usada deja de estar disponible para otros procesos."
    )
    if len(casos) == 1:
        lugar = f" en la consulta {casos[0]['consulta']}" if varias else ""
        mensaje = (f"Se observa una sobreestimación en la reserva de memoria{lugar}, ya que "
                   f"{describir(casos[0])}. {recomendacion}")
    else:
        detalle = "; ".join(f"Consulta {c['consulta']}: {describir(c)}" for c in casos)
        mensaje = (f"Se identificaron {len(casos)} sobreestimaciones en la reserva de memoria, en "
                   f"{_encabezado(casos)}: {detalle}. {recomendacion}")
    return [_hallazgo("MEMORIA_SOBREESTIMADA", Severidad.MEDIO, mensaje, casos)]


def analizar_plan_negocio(sentencias: List[Dict]) -> List[Hallazgo]:
    """Hallazgos del plan para el área Negocio, a partir del árbol de construir_diagrama."""
    return (
        _table_scan(sentencias)
        + _conversion_implicita(sentencias)
        + _lectura_residual(sentencias)
        + _spill(sentencias)
        + _memoria(sentencias)
    )
