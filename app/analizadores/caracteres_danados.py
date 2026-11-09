"""«Caracteres especiales dañados» (compartido por Reportes y Negocio; texto de la usuaria, 8 nov.).

Un texto entre comillas con caracteres dañados se graba así en la base:

    EXEC InsMov_SP @cMovNro, '900098', 'Regularizaci�n de Cheque Intermoneda', …

Se detecta el carácter de reemplazo (�) y la otra señal del mismo problema de codificación: una tilde o ñ guardada
con una codificación y leída con otra (DepÃ³sito, aÃ±o). Solo en textos: los comentarios no se almacenan.
"""

import re
from typing import Callable, List, Optional, Tuple

# El carácter de reemplazo (U+FFFD) o una tilde/ñ mal leída: «Ã» (U+00C3) seguida de un carácter de U+0080 a U+00BF
# o de los que Windows-1252 pone en ese lugar (Ã³ Ã± Ã‰…), o «Â» (U+00C2) delante de uno de U+00A0 a U+00BF.
_DANADO = re.compile(
    "\ufffd"
    "|\u00c3[\u0080-\u00bf\u2018-\u201e\u2020-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]"
    "|\u00c2(?=[\u00a0-\u00bf])"
)
_LARGO_MAXIMO = 70


def _textos_con_posicion(texto: str) -> List[Tuple[int, str]]:
    """[(posición de la comilla, contenido)] de cada texto entre comillas, sin entrar en los comentarios."""
    resultado, i, n = [], 0, len(texto)
    while i < n:
        if texto.startswith("--", i):
            fin = texto.find("\n", i)
            i = n if fin < 0 else fin
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            i = n if fin < 0 else fin + 2
        elif texto[i] == "'":
            j = i + 1
            while j < n:
                if texto[j] == "'":
                    if texto.startswith("''", j):
                        j += 2
                        continue
                    break
                j += 1
            resultado.append((i, texto[i + 1:j]))
            i = j + 1
        else:
            i += 1
    return resultado


def _recortar(contenido: str) -> str:
    contenido = re.sub(r"\s+", " ", contenido).strip()
    return contenido if len(contenido) <= _LARGO_MAXIMO else contenido[:_LARGO_MAXIMO - 1] + "…"


def caracteres_danados(texto: str, linea_de: Callable[[int], int]) -> Optional[Tuple[int, str, List[int]]]:
    """Una sola observación con los textos dañados: (posición, mensaje, líneas) o None."""
    casos = [(posicion, contenido) for posicion, contenido in _textos_con_posicion(texto) if _DANADO.search(contenido)]
    if not casos:
        return None
    textos = list(dict.fromkeys(f"'{_recortar(contenido)}'" for _, contenido in casos))
    simbolos = list(dict.fromkeys(m.group(0) for _, contenido in casos for m in _DANADO.finditer(contenido)))
    marca = "�" if "�" in simbolos else ", ".join(simbolos[:3])
    if len(textos) == 1:
        problema = (f"Se identificaron caracteres dañados ({marca}) en el texto {textos[0]}, que se almacenará de esa "
                    f"manera en la base de datos.")
    else:
        lista = f"{', '.join(textos[:-1])} y {textos[-1]}"
        problema = (f"Se identificaron caracteres dañados ({marca}) en los textos {lista}, que se almacenarán de esa "
                    f"manera en la base de datos.")
    # «Qué hacer»: texto de la usuaria (8 nov.).
    mensaje = (f"{problema} Se recomienda corregir los caracteres afectados y guardar el archivo con la codificación "
               f"adecuada, para evitar que los textos se almacenen de forma incorrecta.")
    return casos[0][0], mensaje, sorted({linea_de(posicion) for posicion, _ in casos})
