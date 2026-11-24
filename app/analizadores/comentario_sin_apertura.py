# -*- coding: utf-8 -*-
"""Cierre de comentario (*/) sin su apertura (/*), compartido por el validador y el encabezado (usuaria, 23 nov.).

Caso real PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral: el encabezado empezaba en «PROCEDIMIENTO : …» sin el
/* y terminaba en «*****/». SQL Server no puede crear el procedimiento, pero el validador solo decía «sintaxis
incorrecta cerca de 'PROCEDIMIENTO'» y las buenas prácticas, que no había encabezado (sí lo había).
"""

import re
from typing import List, Optional, Tuple

# Etiquetas con las que suele empezar un encabezado (sin tildes ni mayúsculas que importen).
_ETIQUETA_DE_ENCABEZADO = re.compile(
    r"^[ \t*|'/-]*(?:PROCEDIMIENTO|PROCEDURE|NOMBRE|OBJETO|PROP[OÓ]SITO|DESCRIPCI[OÓ]N|OBJETIVO|AUTOR|CREADO\s+POR|"
    r"FECHA|SISTEMA|M[OÓ]DULO|REPORTE)\b",
    re.IGNORECASE | re.MULTILINE,
)


def cierre_sin_apertura(texto: str) -> Optional[int]:
    """Posición del primer */ que no cierra ningún comentario (fuera de textos entre comillas y de comentarios --).

    Los comentarios /* */ de T-SQL se pueden anidar, así que se cuenta la profundidad.
    """
    i, largo, profundidad = 0, len(texto), 0
    while i < largo:
        par = texto[i:i + 2]
        if profundidad:
            if par == "/*":
                profundidad, i = profundidad + 1, i + 2
            elif par == "*/":
                profundidad, i = profundidad - 1, i + 2
            else:
                i += 1
        elif par == "/*":
            profundidad, i = 1, i + 2
        elif par == "*/":
            return i
        elif par == "--":
            fin = texto.find("\n", i)
            i = largo if fin < 0 else fin
        elif texto[i] == "'":
            fin = i + 1
            while fin < largo:
                if texto[fin] == "'":
                    if texto[fin + 1:fin + 2] == "'":
                        fin += 2
                        continue
                    break
                fin += 1
            i = fin + 1
        else:
            i += 1
    return None


def encabezado_sin_abrir(texto: str) -> Optional[Tuple[int, int]]:
    """(inicio, fin) del encabezado al que le falta el /*: desde su primera etiqueta (PROCEDIMIENTO, PROPOSITO, AUTOR…)
    o, si no tiene, desde el primer texto, hasta el */ inclusive. None si no hay un */ sin apertura."""
    cierre = cierre_sin_apertura(texto)
    if cierre is None:
        return None
    etiqueta = _ETIQUETA_DE_ENCABEZADO.search(texto, 0, cierre)
    if etiqueta:
        inicio = texto.rfind("\n", 0, etiqueta.start()) + 1
    else:
        inicio = len(texto) - len(texto.lstrip())
    return inicio, cierre + 2


def linea_de(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def mensaje_comentario_sin_apertura(texto: str, inicio: int, fin: int, que_no_se_podra: str) -> str:
    """Texto del validador (estilo de la usuaria: qué pasa, qué hacer, ya que…)."""
    primera = texto[inicio:texto.find("\n", inicio) if "\n" in texto[inicio:fin] else fin].strip()
    corta = primera if len(primera) <= 40 else primera[:40].rstrip() + "…"
    linea_inicio, linea_cierre = linea_de(texto, inicio), linea_de(texto, fin - 2)
    es_encabezado = bool(_ETIQUETA_DE_ENCABEZADO.search(texto, inicio, fin))
    if es_encabezado:
        return (f"Se identificó que falta abrir el comentario del encabezado (/*): el texto «{corta}» de la línea "
                f"{linea_inicio} queda fuera del comentario y el cierre */ de la línea {linea_cierre} no tiene "
                f"apertura. Agregar /* al inicio del encabezado, ya que SQL Server no podrá {que_no_se_podra} con "
                f"este error.")
    return (f"Se identificó un cierre de comentario */ en la línea {linea_cierre} sin su apertura /*. Agregar /* donde "
            f"empieza el comentario, ya que SQL Server no podrá {que_no_se_podra} con este error.")


def lineas_del_encabezado(texto: str, inicio: int, fin: int) -> List[int]:
    return [linea_de(texto, inicio), linea_de(texto, fin - 2)]
