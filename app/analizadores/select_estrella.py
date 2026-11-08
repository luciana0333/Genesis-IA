"""SELECT * en una sola observación (compartido por Reportes y Negocio; texto de la usuaria, 7 nov.).

«Se identificó el uso de SELECT * sobre las tablas temporales #TEMPCALEND y #Constante.» y el «Qué hacer» de la
usuaria. SELECT x.* cuenta igual: se nombra la tabla del alias.
"""

from typing import List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo

REGLA = "SELECT_ESTRELLA_PROHIBIDO"

# Texto de la usuaria (7 nov.), igual en Reportes y Negocio.
QUE_HACER_SELECT_ESTRELLA = (
    "Evitar el uso de SELECT *, ya que esta instrucción obtiene todas las columnas de la tabla, incluso aquellas "
    "que no se utilizan. Se recomienda definir explícitamente las columnas necesarias en la consulta."
)


def marcar(hallazgo: Hallazgo, nombre: Optional[str], es_funcion: bool = False) -> Hallazgo:
    """Guarda sobre qué objeto es el SELECT * (para unirlos después en una sola observación)."""
    hallazgo.objeto_estrella = (("funcion" if es_funcion else "tabla"), (nombre or "").strip())
    return hallazgo


def _enumerar(nombres: List[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _es_temporal(nombre: str) -> bool:
    return nombre.lstrip("[").startswith("#")


def mensaje_select_estrella(objetos: List[Tuple[str, str]]) -> str:
    """objetos: [(tipo 'tabla'|'funcion', nombre)] en orden de aparición; sin nombre si no se reconoce."""
    vistos, tablas, funciones = set(), [], []
    for tipo, nombre in objetos:
        if not nombre or nombre.lower() in vistos:
            continue
        vistos.add(nombre.lower())
        (funciones if tipo == "funcion" else tablas).append(nombre)

    partes = []
    if tablas:
        if all(_es_temporal(t) for t in tablas):
            sustantivo = "la tabla temporal" if len(tablas) == 1 else "las tablas temporales"
        else:
            sustantivo = "la tabla" if len(tablas) == 1 else "las tablas"
        partes.append(f"{sustantivo} {_enumerar(tablas)}")
    if funciones:
        partes.append(f"{'la función' if len(funciones) == 1 else 'las funciones'} {_enumerar(funciones)}")
    sobre = f" sobre {' y '.join(partes)}" if partes else ""
    return f"Se identificó el uso de SELECT *{sobre}. {QUE_HACER_SELECT_ESTRELLA}"


def unir_select_estrella(hallazgos: List[Hallazgo]) -> List[Hallazgo]:
    """Todos los SELECT * del procedimiento en una observación, en el lugar del primero, con sus líneas."""
    casos = sorted((h for h in hallazgos if h.regla == REGLA), key=lambda h: h.linea)
    if not casos:
        return hallazgos
    primero = casos[0]
    objetos = [getattr(h, "objeto_estrella", ("tabla", "")) for h in casos]
    primero.mensaje = mensaje_select_estrella(objetos)
    lineas = sorted({h.linea for h in casos})
    if len(lineas) > 1:
        primero.lineas = lineas  # «Ver en el código» recorre cada SELECT *
    resultado, puesto = [], False
    for hallazgo in hallazgos:
        if hallazgo.regla != REGLA:
            resultado.append(hallazgo)
        elif not puesto:
            resultado.append(primero)
            puesto = True
    return resultado
