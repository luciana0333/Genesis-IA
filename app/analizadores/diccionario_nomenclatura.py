# -*- coding: utf-8 -*-
"""Nomenclatura del objeto que documenta el diccionario (solo al crearlo).

- Procedimientos: Esquema.PA_Tabla_Acción_Finalidad. Se revisa el prefijo PA_,
  que estén la tabla y la acción, y que la acción sea la del manual (Sel, Upd,
  Ins, Del o un verbo) separada con "_". Las mayúsculas no se exigen al detalle.
- Tablas: nombre sin prefijos como TB_, sin guiones bajos ni espacios y con
  mayúscula inicial.

En un ALTER el objeto ya existe y su nombre no se cambia: solo se revisa el
esquema (regla OBJETO_SIN_ESQUEMA de cada analizador).

Devuelve pares (regla, mensaje); cada analizador arma el hallazgo con su
catálogo y su línea.
"""

import re
from typing import List, Tuple

from app.analizadores.analizador_procedimientos_normales import (
    _ABREVIATURA_ACCION,
    _ACCION_PEGADA,
    _ACCIONES_ABREVIADAS,
    _EJEMPLO_NOMBRE,
    _en_pascal,
)
from app.analizadores.analizador_tablas import _a_pascal_case

_ACCIONES_ESTANDAR = {"sel", "upd", "ins", "del"}
_VERBO = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+(?:ar|er|ir)", re.IGNORECASE)


def nomenclatura_procedimiento(nombre: str) -> List[Tuple[str, str]]:
    segmentos = nombre.split("_")
    if segmentos[0].upper() != "PA":
        return [("PROCEDIMIENTO_SIN_PREFIJO_PA",
                 f"El nombre del procedimiento {nombre} no empieza con PA_. Usar el formato "
                 f"PA_Tabla_Acción_Finalidad, ya que PA identifica a los procedimientos almacenados "
                 f"(ej.: {_EJEMPLO_NOMBRE}).")]

    if len(segmentos) < 3 or not all(segmentos[1:3]):
        return [("PROCEDIMIENTO_NOMBRE_INCOMPLETO",
                 f"El nombre del procedimiento {nombre} no indica la tabla y la acción. Usar el formato "
                 f"PA_Tabla_Acción_Finalidad, ya que así se entiende qué hace el procedimiento "
                 f"(ej.: {_EJEMPLO_NOMBRE}).")]

    tabla, accion, finalidad = segmentos[1], segmentos[2], [p for p in segmentos[3:] if p]

    pegada = _ACCION_PEGADA.match(accion)
    if pegada:
        abreviada = _ABREVIATURA_ACCION[pegada.group(1).lower()]
        sugerido = "_".join(["PA", tabla, abreviada, pegada.group(2)] + finalidad)
        return [("PROCEDIMIENTO_ACCION_SIN_SEPARAR",
                 f"En el nombre {nombre}, la acción {pegada.group(1)} está pegada a la finalidad "
                 f"({accion}). Separar la acción con un guion bajo, ya que el formato es "
                 f"PA_Tabla_Acción_Finalidad (ej.: {sugerido}).")]

    abreviatura = _ACCIONES_ABREVIADAS.get(accion.lower())
    if abreviatura and accion.lower() != abreviatura.lower():
        sugerido = "_".join(["PA", _en_pascal(tabla), abreviatura] + [_en_pascal(x) for x in finalidad])
        return [("PROCEDIMIENTO_ACCION_NO_ABREVIADA",
                 f"La acción del procedimiento {nombre} está escrita como '{accion}'. Usar la abreviatura "
                 f"del manual, {abreviatura}, ya que así se nombran las acciones estándar (ej.: {sugerido}).")]

    if accion.lower() not in _ACCIONES_ESTANDAR and not _VERBO.fullmatch(accion):
        # La acción está más adelante (PA_Garantia_Testimonio_Upd_Estado): la tabla quedó separada con
        # guion bajo. Se sugiere juntarla, no agregar otra acción.
        posicion = next((i for i, parte in enumerate(finalidad) if parte.lower() in _ACCIONES_ESTANDAR), None)
        if posicion is not None:
            partes_tabla = [tabla, accion] + finalidad[:posicion]
            sugerido = "_".join(["PA", "".join(_en_pascal(p) for p in partes_tabla)] + finalidad[posicion:])
            return [("PROCEDIMIENTO_TABLA_SEPARADA",
                     f"En el nombre del procedimiento {nombre}, la tabla está separada con guion bajo "
                     f"({'_'.join(partes_tabla)}). Escribir la tabla sin guion bajo, ya que el formato es "
                     f"PA_Tabla_Acción_Finalidad (ej.: {sugerido}).")]
        sugerido = "_".join(["PA", _en_pascal(tabla), "Sel", _en_pascal(accion)] + [_en_pascal(x) for x in finalidad])
        return [("PROCEDIMIENTO_SIN_ACCION",
                 f"El nombre del procedimiento {nombre} no indica una acción: '{accion}' no es Sel, Upd, "
                 f"Ins, Del ni un verbo. Añadir la acción después de la tabla, ya que así se entiende qué "
                 f"hace el procedimiento (ej.: {sugerido}).")]
    return []


def nomenclatura_tabla(nombre: str) -> List[Tuple[str, str]]:
    prefijo = re.match(r"(?i)(TBL?|T)_", nombre)
    problemas = []
    if prefijo:
        problemas.append(f"lleva el prefijo {prefijo.group(0)}")
    if "_" in nombre[prefijo.end() if prefijo else 0:]:
        problemas.append("usa guiones bajos")
    if " " in nombre:
        problemas.append("tiene espacios")
    sugerido = _a_pascal_case(nombre)
    if not sugerido[:1].isupper():
        sugerido = sugerido[:1].upper() + sugerido[1:]
    if not nombre[:1].isupper() and not prefijo:
        problemas.append("no empieza con mayúscula")
    if not problemas:
        return []
    detalle = " y ".join([", ".join(problemas[:-1]), problemas[-1]]) if len(problemas) > 1 else problemas[0]
    return [("TABLA_NOMBRE_NO_ESTANDAR",
             f"El nombre de la tabla {nombre} {detalle}. Usar un nombre con cada palabra iniciando en "
             f"mayúscula, sin prefijos ni guiones bajos, ya que es la nomenclatura del manual "
             f"(ej.: {sugerido}).")]
