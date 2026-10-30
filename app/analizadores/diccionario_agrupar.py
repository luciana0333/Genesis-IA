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


def _enumerar(nombres: List[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


_SINGULAR = {"procedimiento": "del procedimiento", "tabla": "de la tabla", "parámetro": "del parámetro",
             "columna": "de la columna"}
_PLURAL = {"procedimiento": "de los procedimientos", "tabla": "de las tablas", "parámetro": "de los parámetros",
           "columna": "de las columnas"}


def _partes(lugares: List[Tuple[str, str]], con_nombre_del_objeto: bool = True) -> str:
    """«del procedimiento dbo.X y de los parámetros @a y @b»."""
    por_tipo: Dict[str, List[str]] = {}
    for tipo, nombre in lugares:
        nombres = por_tipo.setdefault(tipo, [])
        if nombre not in nombres:
            nombres.append(nombre)
    partes = []
    for tipo, nombres in por_tipo.items():
        if tipo in ("procedimiento", "tabla") and not con_nombre_del_objeto:
            partes.append(_SINGULAR[tipo])  # ya se nombró el objeto: «en PA_X (descripción del procedimiento…)»
        else:
            partes.append(f"{(_SINGULAR if len(nombres) == 1 else _PLURAL)[tipo]} {_enumerar(nombres)}")
    return _enumerar(partes)


def _donde(lugares: List[Tuple[str, str, str]]) -> str:
    """
    Un objeto: «en la descripción del procedimiento dbo.X y de los parámetros @a y @b».
    Varios: «en PA_X (descripción del procedimiento y del parámetro @a) y en PA_Y (descripción del parámetro @b)».
    """
    por_objeto: Dict[str, List[Tuple[str, str]]] = {}
    for tipo, nombre, objeto in lugares:
        por_objeto.setdefault(objeto, []).append((tipo, nombre))
    if len(por_objeto) == 1:
        objeto, de_uno = next(iter(por_objeto.items()))
        # Con varios objetos en el script, un parámetro o columna dice de cuál es.
        de_quien = f" ({objeto})" if objeto and not any(t in ("procedimiento", "tabla") for t, _ in de_uno) else ""
        return f"en la descripción {_partes(de_uno)}{de_quien}"
    return " y ".join(
        f"en {objeto} (descripción {_partes(de_uno, con_nombre_del_objeto=False)})"
        for objeto, de_uno in por_objeto.items()
    )


def juntar_ortografia(hallazgos: List[Hallazgo], accion: str) -> List[Hallazgo]:
    """
    Palabras mal escritas: una línea por palabra con todos los lugares donde aparece, en vez de una por
    descripción («'exoneracion' → 'exoneración' (tilde) en la descripción del procedimiento dbo.X y de los
    parámetros @a, @b y @c»). Usa hallazgo.errores ([(palabra, sugerencias)]) y hallazgo.lugar ((tipo, nombre)).
    """
    from app.analizadores.ortografia import formatear_cambio

    ortografia = [h for h in hallazgos if h.regla == "ERROR_ORTOGRAFICO" and getattr(h, "errores", None)]
    if len(ortografia) < 2:
        return hallazgos
    por_palabra: Dict[Tuple[str, Tuple[str, ...]], List[Tuple[str, str]]] = {}
    for h in sorted(ortografia, key=lambda h: h.linea):
        for palabra, opciones in h.errores:
            por_palabra.setdefault((palabra, tuple(opciones or ())), []).append(
                (*h.lugar, getattr(h, "objeto", "") or ""))
    casos = [
        f"{formatear_cambio(palabra, list(opciones))} {_donde(lugares)}"
        for (palabra, opciones), lugares in por_palabra.items()
    ]
    cantidad = len(casos)
    junta = Hallazgo(
        linea=min(h.linea for h in ortografia),
        origen=ortografia[0].origen,
        severidad=ortografia[0].severidad,
        regla="ERROR_ORTOGRAFICO",
        mensaje=(
            f"Se identificó un error de escritura: {casos[0]}. {accion}" if cantidad == 1 else
            f"Se identificaron {cantidad} palabras mal escritas en las descripciones: {'; '.join(casos)}. {accion}"
        ),
    )
    junta.lineas = sorted({h.linea for h in ortografia})
    junta.seccion = getattr(ortografia[0], "seccion", None) or "diccionario"
    junta.objeto = ""  # ya nombra cada procedimiento o tabla: no se antepone «En el procedimiento…»
    primera = hallazgos.index(ortografia[0])
    resto = [h for h in hallazgos if h not in ortografia]
    return resto[:primera] + [junta] + resto[primera:]


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
            resumido.uso_siglas = {
                sigla: sum(sigla in (getattr(h, "siglas", None) or []) for h in grupo) for sigla in siglas
            }
        resumidos.append(resumido)
    return resumidos
