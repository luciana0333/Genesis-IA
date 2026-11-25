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
    LECTURA_RESIDUAL_MINIMA,
    _lectura_residual,
    _nombre_operador,
    _tiempo_superado,
)
from app.analizadores.planes_ejecucion.diagrama import _kb
from app.analizadores.planes_ejecucion.riesgos_genesis import riesgos_genesis
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


# «Qué hacer» del Table Scan: texto de la usuaria (2 nov.).
_ACCION_PK = (
    "Evaluar agregar una PK CLUSTERED {donde}, ya que, según nuestras buenas prácticas, toda tabla debe contar con "
    "una. Esto permite identificar los registros de forma única y facilita su búsqueda mediante índices."
)


# Lectura completa de tabla (usuaria, 25 nov.): el Scan devuelve casi todo lo que lee (90 % o más), pero el
# Filter que viene después deja una cantidad mínima (10 % o menos de lo leído). Caso real
# PA_CuentasOrden_Ajuste_EstadisticoCapitalMensual: Producto, 4,658,459 leídas → 4,612,906 → Filter (bitmap) → 6,875.
CASI_TODO = 0.9
CANTIDAD_MINIMA = 0.1
# Operadores que pasan las filas sin filtrarlas: se sube por ellos hasta encontrar el Filter.
_SIN_FILTRO = {"parallelism", "compute scalar"}


def _filtro_posterior(nodo: Dict, nodos: List[Dict]) -> Optional[Dict]:
    """El Filter que recibe las filas del Scan (subiendo por Parallelism o Compute Scalar), o None."""
    por_id = {n["id"]: n for n in nodos}
    padre = por_id.get(nodo["padre"])
    while padre is not None and padre["fisica"].lower() in _SIN_FILTRO:
        padre = por_id.get(padre["padre"])
    return padre if padre is not None and padre["fisica"].lower() == "filter" else None


def _lectura_completa(sentencias: List[Dict]) -> List[Dict]:
    casos = []
    for sentencia in sentencias:
        for nodo in sentencia["nodos"]:
            if "scan" not in nodo["fisica"].lower():
                continue
            devueltas = nodo.get("filasReales")
            leidas = nodo.get("filasLeidas") if nodo.get("filasLeidas") is not None else devueltas
            if leidas is None or devueltas is None or leidas <= LECTURA_RESIDUAL_MINIMA or devueltas < leidas * CASI_TODO:
                continue
            filtro = _filtro_posterior(nodo, sentencia["nodos"])
            usadas = filtro.get("filasReales") if filtro is not None else None
            if usadas is None or usadas > leidas * CANTIDAD_MINIMA:
                continue
            casos.append({"consulta": sentencia["numero"], "nodo": nodo, "filtro": filtro})
    return casos


def _hallazgo_lectura_completa(casos: List[Dict]) -> List[Hallazgo]:
    if not casos:
        return []
    tablas = list(dict.fromkeys(c["nodo"].get("objeto") or "sin nombre" for c in casos))
    if len(tablas) == 1:
        sujeto = f"la tabla {tablas[0]}"
    else:
        sujeto = f"las tablas {', '.join(tablas[:-1])} y {tablas[-1]}"
    mensaje = (
        f"Se observa que se estaría leyendo la totalidad o casi la totalidad de {sujeto}. ¿Este comportamiento "
        f"está validado? De no ser así, se recomienda revisar las condiciones de filtrado, ya que posteriormente "
        f"solo se utiliza una cantidad mínima de los registros leídos."
    )
    hallazgo = _hallazgo("LECTURA_COMPLETA_TABLA", Severidad.ALTO, mensaje, [])
    # La imagen muestra solo el Scan de la tabla (usuaria, 25 nov.: «en el Filter no, la tabla solamente»); la misma
    # tabla en varias consultas sale una sola vez en la imagen, con todas sus consultas (agruparCasos del frontend).
    hallazgo.nodos = [{"consulta": c["consulta"], "nodo": c["nodo"]["id"]} for c in casos]
    return [hallazgo]


def _table_scan(sentencias: List[Dict]) -> List[Hallazgo]:
    """Table Scan sobre tablas físicas: en un procedimiento de negocio se recorre la tabla completa."""
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
        _, nodos, _ = por_tabla[tabla]
        texto = f"la tabla {tabla}"
        # La consulta no va en el mensaje: ya está en la imagen (usuaria, 25 nov.).
        detalles = []
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
            f"{inicio} dentro del procedimiento sobre {describir(next(iter(por_tabla)), con_veces=False)}. "
            f"{_ACCION_PK.format(donde='en la tabla')}"
        )
    else:
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(tabla) for tabla in por_tabla))
        mensaje = (
            f"Se identificaron {len(mostrados)} Table Scan dentro del procedimiento: "
            f"{detalle}. {_ACCION_PK.format(donde='en cada tabla con Table Scan')}"
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
        # La consulta no va en el mensaje: ya está en la imagen (usuaria, 25 nov.).
        escritas = caso["datos"].get("escritas")
        if escritas is not None:
            texto += f": se escribieron {_cifra(escritas)} páginas en TempDB"
        return texto

    if len(casos) == 1:
        mensaje = (f"Se ha identificado un spill a TempDB en {describir(casos[0])}. Corregir la alerta por spill "
                   f"dentro del procedimiento, ya que puede ocasionar impactos en TempDB y afectar el rendimiento.")
    else:
        detalle = "; ".join("O" + d[4:] for d in (describir(c) for c in casos))  # «el operador…» → «Operador…»
        mensaje = (f"Se identificaron {len(casos)} spills a TempDB: {detalle}. Corregir las "
                   f"alertas por spill dentro del procedimiento, ya que pueden ocasionar impactos en TempDB y afectar "
                   f"el rendimiento.")
    return [_hallazgo("SPILL_TEMPDB_DETECTADO", Severidad.ALTO, mensaje, casos)]


# --- Sobreestimación de memoria ------------------------------------------------

# En un entorno muy transaccional, reservar poca memoria no es un problema: con la alerta Excessive Grant de
# SQL Server se observa a partir de 80 MB reservados y si se usó MENOS del 50 % (decisión de la usuaria, 2 nov.).
# Sin la alerta (usuaria, 25 nov.) ya no va arriba: solo si la reserva es grande (100 MB o más) y usa poco
# (30 % o menos), como riesgo identificado por Genesis, con el mismo texto y en bajo.
MEMORIA_MINIMA_KB = 80 * 1024
PORCENTAJE_MINIMO_USADO = 0.50
MEMORIA_MINIMA_SIN_ALERTA_KB = 100 * 1024
PORCENTAJE_USADO_SIN_ALERTA = 0.30


def _reserva_grande_sin_alerta(memoria: Optional[Dict]) -> bool:
    if not memoria or memoria.get("concedida") is None or memoria.get("usada") is None:
        return False
    return (memoria["concedida"] >= MEMORIA_MINIMA_SIN_ALERTA_KB
            and memoria["usada"] <= memoria["concedida"] * PORCENTAJE_USADO_SIN_ALERTA)


def _memoria(sentencias: List[Dict]) -> List[Hallazgo]:
    """
    Consultas con la memoria reservada muy por encima de la usada. Con la alerta Excessive Grant del XML en el
    operador inicial: observación en medio. Sin la alerta, pero con una reserva grande y poco uso: riesgo
    identificado por Genesis, en bajo (usuaria, 25 nov.).
    """
    casos = []
    sin_alerta = []
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
        usada = (s.get("memoria") or {}).get("usada")
        uso_razonable = concedida is not None and usada is not None and usada >= concedida * PORCENTAJE_MINIMO_USADO
        if alerta and concedida is not None and concedida >= MEMORIA_MINIMA_KB and not uso_razonable:
            casos.append({"consulta": s["numero"], "nodo": raiz, "datos": alerta.get("datos", {})})
        elif alerta is None and _reserva_grande_sin_alerta(s.get("memoria")):
            memoria = s["memoria"]
            sin_alerta.append({"consulta": s["numero"], "nodo": raiz, "datos": {
                "solicitada": _kb(memoria.get("solicitada")), "concedida": _kb(memoria["concedida"]),
                "usada": _kb(memoria["usada"]),
            }})
    if not casos and not sin_alerta:
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

    def mensaje_de(grupo: List[Dict]) -> str:
        # La consulta no va en el mensaje: ya está en la imagen (usuaria, 25 nov.).
        if len(grupo) == 1:
            return (f"Se observa una sobreestimación en la reserva de memoria, ya que "
                    f"{describir(grupo[0])}. Corregir la sobreestimación de memoria, {motivo}")
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(c) for c in grupo))
        return (f"Se identificaron {len(grupo)} sobreestimaciones en la reserva de memoria: {detalle}. "
                f"Corregir las sobreestimaciones de memoria, {motivo}")

    hallazgos = []
    if casos:
        hallazgos.append(_hallazgo("MEMORIA_SOBREESTIMADA", Severidad.MEDIO, mensaje_de(casos), casos))
    if sin_alerta:
        # Sin la alerta de SQL Server: lo identifica Genesis, con el mismo texto y en bajo.
        riesgo = _hallazgo("MEMORIA_SOBREESTIMADA_GENESIS", Severidad.BAJO, mensaje_de(sin_alerta), sin_alerta)
        riesgo.complementario = True  # va en «Riesgos identificados por Genesis»
        hallazgos.append(riesgo)
    return hallazgos


def analizar_plan_negocio(sentencias: List[Dict], limite_s: Optional[float] = None) -> List[Hallazgo]:
    """Hallazgos del plan para el área Negocio, a partir del árbol de construir_diagrama.

    limite_s: límite de tiempo del área en segundos (None = sin límite definido).
    """
    completas = _lectura_completa(sentencias)
    return (
        _tiempo_superado(sentencias, limite_s)
        + _table_scan(sentencias)
        + _conversion_implicita(sentencias)
        + _hallazgo_lectura_completa(completas)
        + _lectura_residual(sentencias, frozenset((c["consulta"], c["nodo"]["id"]) for c in completas))
        + _spill(sentencias)
        + _memoria(sentencias)
        + riesgos_genesis(sentencias)
    )
