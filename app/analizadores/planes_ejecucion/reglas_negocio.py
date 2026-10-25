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
from app.analizadores.planes_ejecucion.diagrama import _kb
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


def _funciones_de_tabla(sentencia: Dict) -> set:
    """
    Funciones de tabla (ej.: dbo.fn_Split) de la consulta. Su resultado se lee con un
    «Table Scan» con el nombre de la función, junto al operador «Table-valued function»:
    no es una tabla física, así que no lleva PK.
    """
    return {n["objeto"] for n in sentencia["nodos"] if n["fisica"] == "Table-valued function" and n.get("objeto")}


def _table_scan(sentencias: List[Dict]) -> List[Hallazgo]:
    """Table Scan sobre tablas físicas: en un procedimiento de negocio se recorre la tabla completa."""
    varias = len({s["numero"] for s in sentencias}) > 1
    casos = [
        {"consulta": s["numero"], "nodo": n}
        for s in sentencias
        for n in s["nodos"]
        if n["fisica"] == "Table Scan" and n.get("objeto") and not _es_temporal(n["objeto"])
        and n["objeto"] not in _funciones_de_tabla(s)
    ]
    if not casos:
        return []

    # La misma tabla es un solo problema: al agregarle su PK se arreglan todos sus Table Scan. Si se
    # recorre en varias consultas, se muestra una sola vez, con la consulta de su recorrido más costoso
    # (sus filas y su imagen), sin listar las demás consultas.
    por_consulta: Dict[str, Dict[int, List[Dict]]] = {}
    for caso in casos:
        por_consulta.setdefault(caso["nodo"]["objeto"], {}).setdefault(caso["consulta"], []).append(caso["nodo"])
    por_tabla: Dict[str, tuple] = {}
    for tabla, consultas in por_consulta.items():
        elegida = max(consultas, key=lambda n: max(nodo.get("costoPct") or 0 for nodo in consultas[n]))
        por_tabla[tabla] = (elegida, consultas[elegida], len(consultas) > 1)
    mostrados = [{"consulta": consulta, "nodo": nodo} for consulta, nodos, _ in por_tabla.values() for nodo in nodos]

    def describir(tabla: str, con_veces: bool = True) -> str:
        consulta, nodos, repetida = por_tabla[tabla]
        texto = f"la tabla {tabla}"
        detalles = []
        if varias and not repetida:
            detalles.append(f"consulta {consulta}")
        if con_veces and len(nodos) > 1:
            detalles.append(f"{len(nodos)} veces")
        if detalles:
            texto += f" ({', '.join(detalles)})"
        # Se leen en la misma consulta: sus filas se suman.
        if all(n.get("filasLeidas") is not None and n.get("filasReales") is not None for n in nodos):
            leidas = sum(n["filasLeidas"] for n in nodos)
            devueltas = sum(n["filasReales"] for n in nodos)
            texto += f": se leen {_cifra(leidas)} filas y se devuelven {_cifra(devueltas)}"
        return texto

    # Un Table Scan ocurre en tablas sin índice clúster (heap): la recomendación es su PK CLUSTERED.
    if len(por_tabla) == 1:
        # Una sola tabla (una o varias veces): «Se ha identificado un…» o «Se identificaron N… sobre la tabla…».
        inicio = ("Se ha identificado un Table Scan" if len(mostrados) == 1
                  else f"Se identificaron {len(mostrados)} Table Scan")
        mensaje = (
            f"{inicio} dentro del procedimiento sobre {describir(next(iter(por_tabla)), con_veces=False)}. Evaluar "
            f"agregar la PK CLUSTERED en la tabla, ya que forma parte de las buenas prácticas y ayuda a agilizar la "
            f"búsqueda."
        )
    else:
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(tabla) for tabla in por_tabla))
        mensaje = (
            f"Se identificaron {len(mostrados)} Table Scan dentro del procedimiento, en {_encabezado(mostrados)}: "
            f"{detalle}. Evaluar agregar la PK CLUSTERED en las tablas con Table Scan, ya que forma parte de las "
            f"buenas prácticas y ayuda a agilizar la búsqueda."
        )
    return [_hallazgo("TABLE_SCAN_DETECTADO", Severidad.ALTO, mensaje, mostrados)]


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

# En un entorno muy transaccional, reservar poca memoria no es un problema: solo se observa a partir de
# 80 MB reservados y si se usó el 10 % o menos (ej.: 80 MB reservados y 1 MB usado), tenga o no la
# alerta Excessive Grant de SQL Server.
MEMORIA_MINIMA_KB = 80 * 1024
PORCENTAJE_MAXIMO_USADO = 0.10


def _reserva_desproporcionada(memoria: Optional[Dict]) -> bool:
    if not memoria or memoria.get("concedida") is None or memoria.get("usada") is None:
        return False
    return memoria["concedida"] >= MEMORIA_MINIMA_KB and memoria["usada"] <= memoria["concedida"] * PORCENTAJE_MAXIMO_USADO


def _memoria(sentencias: List[Dict]) -> List[Hallazgo]:
    """
    Consultas con la memoria reservada muy por encima de la usada: la alerta Excessive Grant del XML
    (si reservó MEMORIA_MINIMA_KB o más) o, aunque no la traiga, una reserva desproporcionada
    (MEMORIA_MINIMA_KB y PORCENTAJE_MAXIMO_USADO).
    """
    varias = len({s["numero"] for s in sentencias}) > 1
    casos = []
    for s in sentencias:
        raiz = next((n for n in s["nodos"] if n["padre"] is None), None)
        if raiz is None:
            continue
        # Solo «Excessive Grant» es sobreestimación; «Grant Increase» y «Used More Than Granted» son lo contrario.
        alerta = next((a for a in raiz["advertencias"] if a["tipo"] == "memoria"
                       and a.get("datos", {}).get("tipo", "Excessive Grant") == "Excessive Grant"), None)
        concedida = (alerta or {}).get("datos", {}).get("concedidaKb")
        if concedida is None:
            concedida = (s.get("memoria") or {}).get("concedida")
        if alerta and concedida is not None and concedida >= MEMORIA_MINIMA_KB:
            casos.append({"consulta": s["numero"], "nodo": raiz, "datos": alerta.get("datos", {})})
        elif _reserva_desproporcionada(s.get("memoria")):
            memoria = s["memoria"]
            casos.append({"consulta": s["numero"], "nodo": raiz, "datos": {
                "solicitada": _kb(memoria.get("solicitada")), "concedida": _kb(memoria["concedida"]),
                "usada": _kb(memoria["usada"]),
            }})
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
