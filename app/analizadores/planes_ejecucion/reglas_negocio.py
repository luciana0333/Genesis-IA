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

    # La misma tabla es un solo problema (se arregla con su PK una vez), aunque se recorra en varias
    # consultas: se nombra una vez, con las filas de cada consulta y la imagen del recorrido más costoso.
    # Si se recorre varias veces en una misma consulta, sus filas se suman.
    por_tabla: Dict[str, Dict[int, List[Dict]]] = {}
    for caso in casos:
        por_tabla.setdefault(caso["nodo"]["objeto"], {}).setdefault(caso["consulta"], []).append(caso["nodo"])

    def filas(nodos: List[Dict]) -> Optional[tuple]:
        if all(n.get("filasLeidas") is not None and n.get("filasReales") is not None for n in nodos):
            return sum(n["filasLeidas"] for n in nodos), sum(n["filasReales"] for n in nodos)
        return None

    def describir(tabla: str, con_veces: bool = True) -> str:
        consultas = por_tabla[tabla]
        texto = f"la tabla {tabla}"
        if len(consultas) == 1:
            consulta, nodos = next(iter(consultas.items()))
            detalles = []
            if varias:
                detalles.append(f"consulta {consulta}")
            if con_veces and len(nodos) > 1:
                detalles.append(f"{len(nodos)} veces")
            if detalles:
                texto += f" ({', '.join(detalles)})"
            cifras = filas(nodos)
            if cifras:
                texto += f": se leen {_cifra(cifras[0])} filas y se devuelven {_cifra(cifras[1])}"
            return texto
        numeros = sorted(consultas)
        texto += (f", que se repite en {len(numeros)} consultas "
                  f"({', '.join(map(str, numeros[:-1]))} y {numeros[-1]})")
        cifras = {numero: filas(consultas[numero]) for numero in numeros}
        if all(cifras.values()):
            if len({leidas for leidas, _ in cifras.values()}) == 1:
                devueltas = [f"{_cifra(cifras[n][1])} (consulta {n})" for n in numeros]
                texto += (f": se leen {_cifra(cifras[numeros[0]][0])} filas en cada una y se devuelven "
                          f"{', '.join(devueltas[:-1])} y {devueltas[-1]}")
            else:
                partes = [f"en la consulta {n} se leen {_cifra(cifras[n][0])} filas y se devuelven "
                          f"{_cifra(cifras[n][1])}" for n in numeros]
                texto += f": {', '.join(partes[:-1])} y {partes[-1]}"
        return texto

    # Un Table Scan ocurre en tablas sin índice clúster (heap): la recomendación es su PK CLUSTERED.
    if len(por_tabla) == 1:
        tabla = next(iter(por_tabla))
        # Una sola tabla en una consulta: «Se ha identificado un…» o «Se identificaron N…» (varias veces).
        una_consulta = len(por_tabla[tabla]) == 1
        inicio = ("Se ha identificado un Table Scan" if len(casos) == 1 or not una_consulta
                  else f"Se identificaron {len(casos)} Table Scan")
        mensaje = (
            f"{inicio} dentro del procedimiento sobre {describir(tabla, con_veces=False)}. Evaluar "
            f"agregar la PK CLUSTERED en la tabla, ya que forma parte de las buenas prácticas y ayuda a agilizar la "
            f"búsqueda."
        )
    else:
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(tabla) for tabla in por_tabla))
        mensaje = (
            f"Se identificaron {len(casos)} Table Scan dentro del procedimiento, en {_encabezado(casos)}: "
            f"{detalle}. Evaluar agregar la PK CLUSTERED en las tablas con Table Scan, ya que forma parte de las "
            f"buenas prácticas y ayuda a agilizar la búsqueda."
        )
    # Una imagen por tabla: la de la consulta con su recorrido más costoso (con todos sus Table Scan
    # de esa consulta, si la recorre varias veces).
    imagenes = []
    for tabla, consultas in por_tabla.items():
        elegida = max(consultas, key=lambda n: max(nodo.get("costoPct") or 0 for nodo in consultas[n]))
        imagenes += [{"consulta": elegida, "nodo": nodo} for nodo in consultas[elegida]]
    return [_hallazgo("TABLE_SCAN_DETECTADO", Severidad.ALTO, mensaje, imagenes)]


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

# Reserva desproporcionada aunque SQL Server no ponga la alerta: se reservaron 10 MB o más y se
# usó el 10 % o menos (ej.: 200 MB reservados y 30 KB usados).
MEMORIA_MINIMA_KB = 10 * 1024
PORCENTAJE_MAXIMO_USADO = 0.10


def _reserva_desproporcionada(memoria: Optional[Dict]) -> bool:
    if not memoria or memoria.get("concedida") is None or memoria.get("usada") is None:
        return False
    return memoria["concedida"] >= MEMORIA_MINIMA_KB and memoria["usada"] <= memoria["concedida"] * PORCENTAJE_MAXIMO_USADO


def _memoria(sentencias: List[Dict]) -> List[Hallazgo]:
    """
    Consultas con la memoria reservada muy por encima de la usada: la alerta Excessive Grant del XML
    o, aunque no la traiga, una reserva desproporcionada (MEMORIA_MINIMA_KB y PORCENTAJE_MAXIMO_USADO).
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
        if alerta:
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
