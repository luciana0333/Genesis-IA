"""Reglas de los planes de ejecución del área Negocio (procedimientos transaccionales).

Las define la usuaria. Tiempo superado, conversión implícita y lectura residual son
las mismas de Reportes (cada área con su propio límite de tiempo); Table Scan, spill y sobreestimación de memoria son propias de Negocio.
Igual que en Reportes, trabajan sobre el árbol de construir_diagrama: lo que dice
la observación y lo que se ve en el diagrama siempre coinciden.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.analizadores.planes_ejecucion.reglas_reporte import (
    _conversion_implicita,
    _lectura_residual,
    _nombre_operador,
    _tiempo_superado,
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

    # Un Table Scan ocurre en tablas sin índice clúster (heap): la recomendación es su PK CLUSTERED.
    if len(casos) == 1:
        mensaje = (
            f"Se ha identificado un Table Scan dentro del procedimiento sobre {describir(casos[0])}. Evaluar agregar "
            f"la PK CLUSTERED en la tabla, ya que forma parte de las buenas prácticas y ayuda a agilizar la búsqueda."
        )
    else:
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(c) for c in casos))
        mensaje = (
            f"Se identificaron {len(casos)} Table Scan dentro del procedimiento, en {_encabezado(casos)}: "
            f"{detalle}. Evaluar agregar la PK CLUSTERED en las tablas con Table Scan, ya que forma parte de las "
            f"buenas prácticas y ayuda a agilizar la búsqueda."
        )
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

    if len(casos) == 1:
        mensaje = (f"Se ha identificado un spill a TempDB en {describir(casos[0])}. Corregir la alerta por spill "
                   f"dentro del procedimiento, ya que puede ocasionar impactos en TempDB y afectar el rendimiento.")
    else:
        detalle = "; ".join("O" + d[4:] for d in (describir(c) for c in casos))  # «el operador…» → «Operador…»
        mensaje = (f"Se identificaron {len(casos)} spills a TempDB, en {_encabezado(casos)}: {detalle}. Corregir las "
                   f"alertas por spill dentro del procedimiento, ya que pueden ocasionar impactos en TempDB y afectar "
                   f"el rendimiento.")
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

    motivo = (
        "ya que la cantidad reservada es muy alta para la cantidad utilizada; si bien se trata de tablas "
        "transaccionales, se debe reducir lo más posible."
    )
    if len(casos) == 1:
        lugar = f" en la consulta {casos[0]['consulta']}" if varias else ""
        mensaje = (f"Se observa una sobreestimación en la reserva de memoria{lugar}, ya que "
                   f"{describir(casos[0])}. Corregir la sobreestimación de memoria, {motivo}")
    else:
        detalle = "; ".join(f"Consulta {c['consulta']}: {describir(c)}" for c in casos)
        mensaje = (f"Se identificaron {len(casos)} sobreestimaciones en la reserva de memoria, en "
                   f"{_encabezado(casos)}: {detalle}. Corregir las sobreestimaciones de memoria, {motivo}")
    return [_hallazgo("MEMORIA_SOBREESTIMADA", Severidad.MEDIO, mensaje, casos)]


def analizar_plan_negocio(sentencias: List[Dict], limite_s: Optional[float] = None) -> List[Hallazgo]:
    """Hallazgos del plan para el área Negocio, a partir del árbol de construir_diagrama.

    limite_s: límite de tiempo del área en segundos (None = sin límite definido).
    """
    return (
        _tiempo_superado(sentencias, limite_s)
        + _table_scan(sentencias)
        + _conversion_implicita(sentencias)
        + _lectura_residual(sentencias)
        + _spill(sentencias)
        + _memoria(sentencias)
    )
