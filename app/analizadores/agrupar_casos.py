"""Varias observaciones de una misma regla en una sola, sin repetir la frase en cada caso (usuaria, 21 nov.).

Criterio de la usuaria:
  - 2 casos: en el párrafo («Se identificaron las tablas temporales #A y #B con WITH(NOLOCK).»).
  - 3 casos: en viñetas («…las siguientes tablas temporales con WITH(NOLOCK): #A; #B; #C.»).
  - Más de 3: en tabla (la pantalla la arma con `grupos`; el texto copiado sigue siendo la lista).
  - Lo mismo repetido en varias líneas (ORDER BY 1, WHILE…): una sola frase; las líneas van arriba de la tarjeta.

Cada observación trae `elemento` (lo que se nombra: tabla, hint, variable) y, si hace falta, `detalle` (la operación,
qué hace el hint…). El «Qué hacer» se dice una sola vez.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Union

from app.modelos.hallazgo import Hallazgo

CASOS_EN_PARRAFO = 2
CASOS_EN_VINETAS = 3  # desde 4, tabla

Texto = Union[str, Callable[[List[Hallazgo]], str]]


@dataclass(frozen=True)
class Plantilla:
    # Con 2 casos: «…{casos}…» («#A y #B»).
    parrafo: str = ""
    # Desde 3 casos, sin los dos puntos: «Se identificaron las siguientes tablas temporales con WITH(NOLOCK)».
    lista: str = ""
    # El «Qué hacer» para todos (o una función del grupo).
    que_hacer: Texto = ""
    # Encabezados de la tabla (más de 3 casos): qué es cada fila y qué dice la segunda columna.
    fila: str = "Tabla"
    columna: str = "Líneas"
    # La segunda columna es una frase («Qué hace») y no código: va en letra normal.
    columna_en_texto: bool = False
    # Lo mismo repetido (ORDER BY 1, WHILE): una sola frase para todos (o una función del grupo).
    repetido: Optional[Texto] = None
    # Un solo caso con varios detalles (la misma tabla con INSERT y UPDATE): «…la tabla {casos}.».
    uno: str = ""


def _texto(valor: Texto, grupo: List[Hallazgo]) -> str:
    return valor(grupo) if callable(valor) else valor


def _enumerar(elementos: List[str]) -> str:
    return elementos[0] if len(elementos) == 1 else f"{', '.join(elementos[:-1])} y {elementos[-1]}"


def _columna(texto: str, plantilla: Plantilla) -> str:
    """En la tabla, la frase de la segunda columna empieza con mayúscula («Bloquea toda la tabla…»)."""
    return texto[:1].upper() + texto[1:] if plantilla.columna_en_texto else texto


def agrupar_casos(grupo: List[Hallazgo], plantilla: Plantilla) -> Hallazgo:
    """Una sola observación para todo el grupo (de una misma regla), según la cantidad de casos distintos."""
    grupo = sorted(grupo, key=lambda h: (h.linea, getattr(h, "posicion", 0)))
    lineas = sorted({h.linea for h in grupo})
    casos: Dict[str, Dict[str, list]] = {}
    for h in grupo:
        caso = casos.setdefault(getattr(h, "elemento", None) or h.mensaje, {"lineas": [], "detalles": []})
        caso["lineas"].append(h.linea)
        detalle = getattr(h, "detalle", None)
        caso["detalles"].append(detalle)

    def con_detalle(elemento: str) -> str:
        detalles = [d for d in dict.fromkeys(casos[elemento]["detalles"]) if d]
        return f"{elemento} ({', '.join(detalles)})" if detalles else elemento

    grupos = None
    if plantilla.repetido is not None:
        problema = _texto(plantilla.repetido, grupo)
    elif len(casos) == 1:
        elemento = next(iter(casos))
        varios_detalles = len({d for d in casos[elemento]["detalles"] if d}) > 1
        # El mismo caso en varias líneas: su propio mensaje (las líneas van arriba de la tarjeta); si cambia el
        # detalle (INSERT y UPDATE sobre la misma tabla), se dicen todos.
        problema = plantilla.uno.format(casos=con_detalle(elemento)) if varios_detalles and plantilla.uno else None
    elif len(casos) <= CASOS_EN_PARRAFO:
        problema = plantilla.parrafo.format(casos=_enumerar([con_detalle(e) for e in casos]))
    else:
        problema = f"{plantilla.lista}: {'; '.join(con_detalle(e) for e in casos)}."
        if len(casos) > CASOS_EN_VINETAS:
            grupos = [{
                "nombre": elemento,
                "tipo": plantilla.fila,
                # La pantalla arma la tabla con este título (más de 3 casos).
                "tituloDetalle": plantilla.columna,
                **({"detalleEnTexto": True} if plantilla.columna_en_texto else {}),
                "lineas": caso["lineas"],
                **({"etiquetas": [d or "" for d in caso["detalles"]]} if any(caso["detalles"]) else {}),
                "columnas": _columna(", ".join(d for d in dict.fromkeys(caso["detalles"]) if d)
                                     or ", ".join(map(str, sorted(set(caso["lineas"])))), plantilla),
            } for elemento, caso in casos.items()]

    if problema is None:
        mensaje = grupo[0].mensaje
        inicio = getattr(grupo[0], "inicio_que_hacer", None)
    else:
        que_hacer = _texto(plantilla.que_hacer, grupo)
        mensaje = f"{problema} {que_hacer}"
        inicio = len(problema) + 1
    resumen = Hallazgo(
        linea=lineas[0],
        origen=grupo[0].origen,
        severidad=grupo[0].severidad,
        regla=grupo[0].regla,
        mensaje=mensaje,
    )
    if inicio:
        resumen.inicio_que_hacer = inicio
    resumen.lineas = [linea for g in grupos for linea in g["lineas"]] if grupos else lineas
    if grupos:
        resumen.grupos = grupos
    return resumen


def accion_del_primero(grupo: List[Hallazgo]) -> str:
    """El «Qué hacer» del primer caso tal cual (cuando ya sirve para todos; p. ej. trae su ejemplo)."""
    import re

    partes = re.split(r"(?<=[.?])\s+(?=[A-ZÁÉÍÓÚÑ¿(])", grupo[0].mensaje, maxsplit=1)
    return partes[1] if len(partes) == 2 else ""
