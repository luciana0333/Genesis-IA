# -*- coding: utf-8 -*-
"""Agrupa las observaciones repetidas de los diccionarios (tablas y procedimientos).

Si una regla aparece varias veces se reporta una sola vez: con el sustantivo
de la regla ("Se identificaron 2 parámetros sin documentar") y la lista de
elementos, o con el resumen general si la regla no lista elementos.
"""

import re
from typing import Dict, List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo


def con_elemento(hallazgo: Hallazgo, elemento: str, linea: Optional[int] = None) -> Hallazgo:
    """Marca el elemento (parámetro, columna) al que se refiere el hallazgo."""
    hallazgo.elemento = elemento
    if linea:
        hallazgo.linea = linea
    return hallazgo


def ubicar(hallazgo: Hallazgo, texto: str) -> None:
    """Ubica el hallazgo en la línea donde aparece su elemento (parámetro o columna)."""
    m = re.search(rf"(?<![\w@]){re.escape(hallazgo.elemento)}(?!\w)", texto, re.IGNORECASE)
    if m:
        hallazgo.linea = texto.count("\n", 0, m.start()) + 1
        hallazgo.posicion = m.start()
        hallazgo.seccion = "objeto"  # la línea ahora es del CREATE/ALTER


def asignar_secciones(hallazgos: List[Hallazgo], del_objeto: set, generales: set) -> None:
    """
    Indica en qué cajita está la línea de cada observación, para mostrar su código y llevar a ella:
    «objeto» (el CREATE/ALTER), «diccionario» (el script de sp_addextendedproperty) o «general»
    (se refiere a todo el objeto y no apunta a una línea concreta).
    """
    for hallazgo in hallazgos:
        if getattr(hallazgo, "seccion", None):
            continue
        if hallazgo.regla in del_objeto:
            hallazgo.seccion = "objeto"
        elif hallazgo.regla in generales:
            hallazgo.seccion = "general"
        else:
            hallazgo.seccion = "diccionario"


def _lineas(numeros: List[int]) -> str:
    return ("la línea " if len(numeros) == 1 else "las líneas ") + ", ".join(map(str, numeros))


def agrupar(hallazgos: List[Hallazgo], plantillas: Dict[str, Tuple[str, str]]) -> List[Hallazgo]:
    """plantillas: regla -> (sustantivo en plural, acción para todos)."""
    grupos: Dict[str, List[Hallazgo]] = {}
    for hallazgo in hallazgos:
        grupos.setdefault(hallazgo.regla, []).append(hallazgo)

    resumidos: List[Hallazgo] = []
    for regla, grupo in grupos.items():
        if len(grupo) == 1:
            resumidos.append(grupo[0])
            continue
        # En el orden en que aparecen en el código.
        grupo = sorted(grupo, key=lambda h: (h.linea, getattr(h, "posicion", 0)))
        numeros = sorted({h.linea for h in grupo})
        elementos = [getattr(h, "elemento", None) for h in grupo]
        if regla in plantillas and all(elementos):
            sustantivo, accion = plantillas[regla]
            mensaje = (
                f"Se identificaron {len(grupo)} {sustantivo}, en {_lineas(numeros)}: "
                f"{'; '.join(dict.fromkeys(elementos))}. {accion}"
            )
        else:
            # Cada mensaje es "qué pasa. Qué hacer.": se listan los hechos y la
            # acción se dice una sola vez.
            partes = [re.split(r"(?<=\.)\s+", h.mensaje, maxsplit=1) for h in grupo]
            if all(len(p) == 2 for p in partes):
                hechos = list(dict.fromkeys(p[0][:1].lower() + p[0][1:].rstrip(".") for p in partes))
                detalle = "; ".join(hechos) + ". " + partes[0][1]
            else:
                detalle = " ".join(dict.fromkeys(h.mensaje for h in grupo))
            mensaje = f"Se encontraron {len(grupo)} observaciones de este tipo, en {_lineas(numeros)}: {detalle}"
        resumido = Hallazgo(
            linea=numeros[0],
            origen=grupo[0].origen,
            severidad=grupo[0].severidad,
            regla=regla,
            mensaje=mensaje,
        )
        # Las líneas son de una misma cajita solo si todo el grupo lo es; si no, no se señala ninguna.
        secciones = {getattr(h, "seccion", None) for h in grupo}
        resumido.seccion = secciones.pop() if len(secciones) == 1 else "general"
        resumido.lineas = numeros
        siglas = list(dict.fromkeys(s for h in grupo for s in (getattr(h, "siglas", None) or [])))
        if siglas:
            resumido.siglas = siglas
        resumidos.append(resumido)
    return resumidos
