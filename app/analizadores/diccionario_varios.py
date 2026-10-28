# -*- coding: utf-8 -*-
"""Diccionarios de varios objetos a la vez (varias tablas o varios procedimientos).

El script se separa por objeto (cada CREATE/ALTER TABLE o CREATE/ALTER PROCEDURE) y cada
sentencia del diccionario se reparte al objeto que documenta (su @level1name). Así cada
objeto se revisa con las mismas reglas de siempre y la misma columna o el mismo parámetro
en dos objetos distintos no se toma como duplicado.

Para no perder los números de línea, cada objeto se revisa sobre una copia del texto
completo en la que todo lo que no le pertenece se reemplaza por espacios.
"""

import re
from typing import Callable, Dict, List, Optional, Pattern, Tuple

from app.analizadores.diccionario_agrupar import agrupar
from app.analizadores.propiedades_extendidas import leer_propiedades_extendidas

Rango = Tuple[int, int]


def _limpiar(nombre: str) -> str:
    return nombre.strip().strip("[]").upper()


def separar_objetos(texto: str, encabezado: Pattern, nombre_de: Callable) -> List[Tuple[str, List[Rango]]]:
    """
    [(nombre, rangos del texto)] en el orden en que aparecen. Cada objeto va desde su
    encabezado hasta el siguiente; un mismo objeto en dos sentencias (CREATE TABLE y luego
    ALTER TABLE para sus restricciones) junta ambas partes. Lo anterior al primer
    encabezado va con el primer objeto.
    """
    sin_comentarios = re.sub(r"--[^\n]*|/\*[\s\S]*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto)
    encabezados = [(m.start(), nombre_de(m)) for m in encabezado.finditer(sin_comentarios)]
    objetos: Dict[str, Tuple[str, List[Rango]]] = {}
    for i, (inicio, nombre) in enumerate(encabezados):
        fin = encabezados[i + 1][0] if i + 1 < len(encabezados) else len(texto)
        desde = 0 if i == 0 else inicio
        objetos.setdefault(_limpiar(nombre), (nombre, []))[1].append((desde, fin))
    return list(objetos.values())


def repartir_diccionario(texto_diccionario: str, nombres: List[str]) -> List[List[Rango]]:
    """
    Rangos del diccionario de cada objeto (en el orden de `nombres`). Cada sentencia va al
    objeto de su @level1name; si ese nombre no es de ningún objeto (mal escrito o vacío), va
    con la sentencia anterior, para que la revisión de ese objeto diga que el nombre no coincide.
    Lo que no es una sentencia (comentarios del inicio) va con el primer objeto.
    """
    claves = [_limpiar(n) for n in nombres]
    llamadas = leer_propiedades_extendidas(texto_diccionario)
    rangos: List[List[Rango]] = [[] for _ in nombres]
    if not llamadas:
        rangos[0].append((0, len(texto_diccionario)))
        return rangos

    duenos: List[Optional[int]] = [
        claves.index(_limpiar(ll.texto("level1name"))) if _limpiar(ll.texto("level1name")) in claves else None
        for ll in llamadas
    ]
    anterior = next((d for d in duenos if d is not None), 0)
    for i, ll in enumerate(llamadas):
        dueno = duenos[i] if duenos[i] is not None else anterior
        anterior = dueno
        desde = 0 if i == 0 else ll.posicion
        hasta = llamadas[i + 1].posicion if i + 1 < len(llamadas) else len(texto_diccionario)
        rangos[dueno].append((desde, hasta))
    return rangos


def enmascarar(texto: str, rangos: List[Rango]) -> str:
    """El texto con solo los rangos dados; lo demás en espacios (se conservan los saltos de línea)."""
    salida = re.sub(r"[^\n]", " ", texto)
    for desde, hasta in rangos:
        salida = salida[:desde] + texto[desde:hasta] + salida[hasta:]
    return salida


def por_objeto(
    texto_objeto: str, texto_diccionario: str, encabezado: Pattern, nombre_de: Callable
) -> Optional[List[Tuple[str, str, str]]]:
    """
    [(nombre, texto del objeto, texto de su diccionario)] si el script tiene más de un
    objeto; None si tiene uno solo (se revisa como siempre).
    """
    objetos = separar_objetos(texto_objeto, encabezado, nombre_de)
    if len(objetos) < 2:
        return None
    diccionarios = repartir_diccionario(texto_diccionario, [nombre for nombre, _ in objetos])
    return [
        (nombre, enmascarar(texto_objeto, rangos), enmascarar(texto_diccionario, rangos_dicc))
        for (nombre, rangos), rangos_dicc in zip(objetos, diccionarios)
    ]


def _con_objeto(caso: str, objeto: str) -> str:
    """«Descripción del parámetro @x (PA_Y): …»; sin cambios si el caso ya nombra el objeto."""
    if objeto.upper() in caso.upper():
        return caso
    titulo, detalle = caso.split(": ", 1)
    return f"{titulo} ({objeto}): {detalle}"


def agrupar_varios(hallazgos, plantillas: Dict[str, Tuple[str, str]], articulo: str) -> list:
    """
    Una observación por regla en todo el script. Si la regla aparece una vez, el mensaje dice de
    qué objeto es; si aparece varias, los casos van por objeto, nombrándolo una sola vez
    («Cliente : cNombre, cApellido; Proveedor : cNombre»). `articulo`: «la tabla» / «el procedimiento».
    `hallazgo.objeto` dice a qué objeto pertenece cada observación.
    """
    grupos: Dict[str, list] = {}
    for hallazgo in hallazgos:
        grupos.setdefault(hallazgo.regla, []).append(hallazgo)

    resultado = []
    for regla, grupo in grupos.items():
        if len(grupo) == 1:
            hallazgo = grupo[0]
            if hallazgo.objeto.upper() not in hallazgo.mensaje.upper():
                hallazgo.mensaje = f"En {articulo} {hallazgo.objeto}, {hallazgo.mensaje[0].lower()}{hallazgo.mensaje[1:]}"
            resultado.append(hallazgo)
            continue
        resumido = agrupar(grupo, plantillas)[0]
        elementos = [getattr(h, "elemento", None) for h in grupo]
        if regla in plantillas and all(elementos):
            por_objeto: Dict[str, List[str]] = {}
            for h in sorted(grupo, key=lambda h: (h.linea, getattr(h, "posicion", 0))):
                casos = por_objeto.setdefault(h.objeto, [])
                if h.elemento not in casos:
                    casos.append(h.elemento)
            sustantivo, accion = plantillas[regla]
            lineas = resumido.lineas
            donde = ("la línea " if len(lineas) == 1 else "las líneas ") + ", ".join(map(str, lineas))
            casos = "; ".join(
                # Casos que ya traen su detalle («Descripción del parámetro @x: 'a' → 'b'»): uno por
                # viñeta, con el objeto entre paréntesis si el caso no lo nombra.
                "; ".join(_con_objeto(e, objeto) for e in elems) if any(": " in e for e in elems)
                else f"{objeto} : {', '.join(elems)}"
                for objeto, elems in por_objeto.items()
            )
            total = sum(len(elems) for elems in por_objeto.values())
            resumido.mensaje = f"Se identificaron {total} {sustantivo}, en {donde}: {casos}. {accion}"
        resultado.append(resumido)
    return resultado


def unir_faltantes(faltantes: List[Optional[dict]]) -> Optional[dict]:
    """«Generar diccionario faltante» de varios objetos: un solo script, objeto por objeto."""
    partes = [f for f in faltantes if f]
    if not partes:
        return None
    return {
        "script": "\n".join(f["script"] for f in partes),
        "elementos": [e for f in partes for e in f["elementos"]],
    }
