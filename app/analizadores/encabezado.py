"""«Encabezado del procedimiento» (compartido por Reportes y Negocio; pedido de la usuaria, 8 nov.).

Todo procedimiento lleva al inicio su encabezado de documentación (antes del CREATE/ALTER, o justo después del
AS o del BEGIN):

    /*****************************************************************
    Nombre del PA  | Logistica.PA_Provision_Sel_OrdenesSicmac
    Descripción    | Procedimiento que lista las ordenes del sicmac
    Autor          | LMPE
    Fecha          | 04/08/2025
    ------------------------------------------------------------------
    Control de Cambios
    Fecha    | Autor    | Descripción
    ------------------------------------------------------------------
    exec LOGISTICA.PA_Provision_Sel_OrdenesSicmac @cOpeCod=N'702401'
    *****************************************************************/

Una sola regla: sin encabezado, o con datos que faltan (se nombran solo los que faltan). Se aceptan los nombres
que usa cada equipo (PROPÓSITO, CREADO POR, FECHA CREACIÓN, HISTORIAL DE CAMBIOS...) y la plantilla en inglés de
SSMS (caso de la usuaria, 11 nov.):

    -- Author:      LFCE
    -- Create date: 05-09-2012
    -- Description: Inserta en tablas Datos de las Trx VISA
    -- AAAA-MM-DD - USER -  Descripcion del cambio
    -- 2016-04-29 - KAAY -  Agrega Registro de Usuario a NETLogConciliacion
"""

import re
from typing import List, Optional, Tuple

_PROCEDIMIENTO = re.compile(r"\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\b", re.IGNORECASE)
_COMENTARIO = re.compile(r"/\*[\s\S]*?(?:\*/|$)|--[^\n]*")

# Cada dato con su etiqueta y un valor en la misma línea («Autor | LMPE» o «Autor: LMPE»). La fila de títulos de
# «Control de Cambios» (Fecha | Autor | Descripción) no cuenta como valor: tras la etiqueta viene otra etiqueta.
_DESCRIPCION = r"(?:Descripci[oó]n|Prop[oó]sito|Objetivo|Description)"
_AUTOR = r"(?:Autor|Creado\s+por|Elaborado\s+por|Desarrollado\s+por|Responsable|Author)"
_FECHA = r"(?:Fecha|Date)"
_ETIQUETAS = rf"(?:Nombre|Name|{_DESCRIPCION}|{_AUTOR}|{_FECHA}|Motivo)\b"
_EXEC = r"\bEXEC(?:UTE)?\s+[\w\[]"
_DATOS = (
    # El nombre puede ir en su propia línea o en el EXEC de ejemplo, que lo nombra.
    ("el nombre del procedimiento",
     re.compile(rf"\bNombre\b[^|:\n]*[|:]\s*(?!{_ETIQUETAS})[\w\[]|{_EXEC}", re.IGNORECASE)),
    ("la descripción", re.compile(rf"\b{_DESCRIPCION}\b[^|:\n]*[|:]\s*(?!{_ETIQUETAS})\w", re.IGNORECASE)),
    ("el autor", re.compile(rf"\b{_AUTOR}\b[^|:\n]*[|:]\s*(?!{_ETIQUETAS})\w", re.IGNORECASE)),
    ("la fecha", re.compile(rf"\b{_FECHA}\b[^|:\n]*[|:]\s*[^|\n]*\d", re.IGNORECASE)),
    # El título («Control de Cambios», «Historial de cambios») o, sin título, la fila de títulos de la tabla de
    # cambios en una línea: «Fecha  Autor  Descripción» (o Responsable / Motivo).
    ("el control de cambios",
     re.compile(r"\b(?:Control|Historial)\s+de\s+(?:cambios|modificaciones|versiones)\b"
                # «HISTORIAL DE FECHA» (FluGenSol_InsPropuesta_SP, usuaria, 22 nov.: decía que no tenía control de
                # cambios con unas 80 líneas de historial).
                r"|\bHistorial\s+de\s+fechas?\b"
                r"|\bChange\s+(?:history|log)\b|\bDescripci[oó]n\s+del\s+cambio\b"
                r"|\bFecha\b[^\n]*\b(?:Autor|Responsable|Usuario)\b[^\n]*\b(?:Descripci[oó]n|Motivo|Detalle)\b"
                # Un cambio registrado: «2016-04-29 - KAAY - Agrega Registro…» o «29/04/2016 | KAAY | …».
                r"|\b\d{4}-\d{2}-\d{2}\s*[-|]\s*\w+\s*[-|]\s*\w"
                r"|\b\d{2}/\d{2}/\d{4}\s*[-|]\s*\w+\s*[-|]\s*\w"
                # O separado solo por espacios o tabulaciones, al inicio de la línea: «2019-03-06  IPAL   Se adapta…»,
                # «2016.11.18	BJMS	se cambió…». La fecha al inicio distingue el historial de «FECHA | 03/01/2019».
                r"|^[\s*|/'-]*(?:\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[-/.]\d{2}[-/.]\d{4})[ \t]+\w{2,12}[ \t]+\w",
                re.IGNORECASE | re.MULTILINE)),
    ("el ejemplo de ejecución (EXEC)", re.compile(_EXEC, re.IGNORECASE)),
)

# Texto de la usuaria (8 nov.).
QUE_HACER_SIN_ENCABEZADO = (
    "Se recomienda agregar al inicio el encabezado con el nombre del procedimiento, la descripción, el autor, la "
    "fecha, el control de cambios y un ejemplo de ejecución."
)
QUE_HACER_ENCABEZADO_INCOMPLETO = (
    "Se recomienda completar los datos del encabezado, ya que permiten identificar su propósito y facilitan su "
    "mantenimiento."
)


def _inicio_del_cuerpo(limpio: str, desde: int) -> int:
    """Posición de la primera instrucción del cuerpo: tras el AS (fuera de paréntesis) y, si lo hay, el BEGIN."""
    profundidad = 0
    for match in re.finditer(r"[()]|\bAS\b", limpio[desde:], re.IGNORECASE):
        token = match.group(0)
        if token == "(":
            profundidad += 1
        elif token == ")":
            profundidad -= 1
        elif profundidad == 0:
            fin = desde + match.end()
            begin = re.match(r"\s*BEGIN\b", limpio[fin:], re.IGNORECASE)
            if begin:
                fin += begin.end()
            siguiente = re.search(r"\S", limpio[fin:])
            return fin + siguiente.start() if siguiente else len(limpio)
    return len(limpio)


def _enumerar(datos: List[str]) -> str:
    return datos[0] if len(datos) == 1 else f"{', '.join(datos[:-1])} ni {datos[-1]}"


def comentarios_del_encabezado(texto: str, limpio: str) -> List[str]:
    """Los comentarios del encabezado (antes del CREATE/ALTER, o justo después del AS o del BEGIN)."""
    procedimiento = _PROCEDIMIENTO.search(limpio)
    if not procedimiento:
        return []
    zona = texto[:_inicio_del_cuerpo(limpio, procedimiento.end())]
    return [c.group(0) for c in _COMENTARIO.finditer(zona)]


def encabezado_observado(texto: str, limpio: str) -> Optional[Tuple[int, str]]:
    """(posición, mensaje) si el procedimiento no tiene encabezado o le faltan datos; None si está completo.

    `limpio` es el texto sin comentarios con las mismas posiciones. Solo se revisan procedimientos.
    """
    procedimiento = _PROCEDIMIENTO.search(limpio)
    if not procedimiento:
        return None
    zona = texto[:_inicio_del_cuerpo(limpio, procedimiento.end())]
    comentarios = list(_COMENTARIO.finditer(zona))
    encabezado = "\n".join(c.group(0) for c in comentarios)
    if not re.search(r"\w", encabezado):
        return procedimiento.start(), (
            f"Se identificó que el procedimiento no cuenta con un encabezado de documentación. "
            f"{QUE_HACER_SIN_ENCABEZADO}"
        )
    faltan = [dato for dato, patron in _DATOS if not patron.search(encabezado)]
    # Etiqueta casi igual a la esperada («DESCRPICION: VALORIZA EL CHEQUE…»): el dato está, solo mal rotulado. No se
    # dice que falta; se avisa en la misma observación, que es de severidad baja (usuaria, 22 nov.: «muy secundario»).
    mal_escritas = []
    for dato in list(faltan):
        etiqueta = _etiqueta_mal_escrita(encabezado, dato)
        if etiqueta:
            faltan.remove(dato)
            if etiqueta[0] is not None:  # None: variante válida («FECHAS:», «AUTORES:»): el dato está
                mal_escritas.append(etiqueta)
    if not faltan and not mal_escritas:
        return None
    avisos = [f"la etiqueta {escrita} parece mal escrita (¿{correcta}?)" for escrita, correcta in mal_escritas]
    if not faltan:
        corregir = "la etiqueta" if len(avisos) == 1 else "las etiquetas"
        return comentarios[0].start(), (
            f"Se identificó que en el encabezado {_y(avisos)}. Se recomienda corregir {corregir}, ya que el "
            f"encabezado debe ser claro para quien mantenga el procedimiento."
        )
    adicional = f" Además, {_y(avisos)}." if avisos else ""
    return comentarios[0].start(), (
        f"Se identificó que el encabezado del procedimiento no indica {_enumerar(faltan)}.{adicional} "
        f"{QUE_HACER_ENCABEZADO_INCOMPLETO}"
    )


# Etiquetas esperadas por dato, para reconocer una mal escrita (sin tildes, en mayúscula).
_ETIQUETAS_ESPERADAS = {
    "el nombre del procedimiento": [("NOMBRE", "Nombre")],
    "la descripción": [("DESCRIPCION", "Descripción"), ("PROPOSITO", "Propósito"), ("OBJETIVO", "Objetivo")],
    "el autor": [("AUTOR", "Autor"), ("RESPONSABLE", "Responsable")],
    "la fecha": [("FECHA", "Fecha")],
}


def _sin_tildes(texto: str) -> str:
    return texto.upper().translate(str.maketrans("ÁÉÍÓÚÜ", "AEIOUU"))


def _etiqueta_mal_escrita(encabezado: str, dato: str) -> Optional[Tuple[Optional[str], str]]:
    """(como está escrita, la correcta) si una línea del encabezado empieza con una etiqueta casi igual a la
    esperada y tiene un valor después de «:» o «|» (DESCRPICION: VALORIZA…); (None, la correcta) si es una variante
    bien escrita (FECHAS: …). Solo palabras de 5 letras o más."""
    import difflib
    for linea in encabezado.splitlines():
        rotulo = re.match(r"^[\s*|/'-]*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{5,})\s*[:|]\s*\S", linea)
        if not rotulo:
            continue
        palabra = _sin_tildes(rotulo.group(1))
        for esperada, correcta in _ETIQUETAS_ESPERADAS.get(dato, []):
            if palabra.startswith(esperada):  # plural o variante («FECHAS», «AUTORES»): está bien escrita
                return None, correcta
            if difflib.SequenceMatcher(None, palabra, esperada).ratio() >= 0.8:
                return rotulo.group(1), correcta
    return None


def _y(partes: List[str]) -> str:
    return partes[0] if len(partes) == 1 else f"{', '.join(partes[:-1])} y {partes[-1]}"


# --- Nombre del encabezado distinto al del procedimiento (usuaria, 19 nov.; Reportes y Negocio) ----------------------
_REFERENCIA = r"(?:\[[^\]\n]+\]|[\w$#]+)(?:\s*\.\s*(?:\[[^\]\n]+\]|[\w$#]+)){0,2}"
# «PROCEDIMIENTO: DBO.PA_X», «NOMBRE | [DUN].[PA_X]», «Nombre del PA | Logistica.PA_X»: la etiqueta al inicio de la
# línea (así «PROPÓSITO | PROCEDIMIENTO ALMACENADO QUE…» no cuenta) y un nombre de objeto como valor.
_NOMBRE_EN_ENCABEZADO = re.compile(
    rf"^[\s*|/-]*(?:Nombre(?:\s+del\s+(?:PA|procedimiento|SP))?|Procedimiento|Procedure|Objeto|Name)\s*[|:]\s*"
    rf"(?P<nombre>{_REFERENCIA})",
    re.IGNORECASE | re.MULTILINE,
)
_NOMBRE_DEL_OBJETO = re.compile(rf"\s+(?P<nombre>{_REFERENCIA})")


def _partes(nombre: str) -> List[str]:
    """[esquema, nombre] sin corchetes ni espacios, en minúscula (la base, si viene, no se compara)."""
    partes = [p.strip().strip("[]").strip().lower() for p in nombre.split(".")]
    return partes[-2:]


def nombre_del_encabezado_distinto(texto: str, limpio: str) -> Optional[Tuple[int, str, str]]:
    """(posición, nombre del encabezado, nombre del procedimiento) si el encabezado nombra otro objeto; None si
    coinciden o el encabezado no indica nombre. Mayúsculas, corchetes y la base no cuentan; el esquema solo si los
    dos lo indican (PA_X contra DBO.PA_X es el mismo)."""
    procedimiento = _PROCEDIMIENTO.search(limpio)
    objeto = _NOMBRE_DEL_OBJETO.match(limpio, procedimiento.end()) if procedimiento else None
    if not objeto:
        return None
    zona = texto[:_inicio_del_cuerpo(limpio, procedimiento.end())]
    for comentario in _COMENTARIO.finditer(zona):
        for indicado in _NOMBRE_EN_ENCABEZADO.finditer(comentario.group(0)):
            nombre = indicado.group("nombre")
            if "_" not in nombre and "." not in nombre:
                continue  # «NOMBRE: Juan»: no es un nombre de objeto
            del_encabezado, del_objeto = _partes(nombre), _partes(objeto.group("nombre"))
            iguales = del_encabezado[-1] == del_objeto[-1] and (
                len(del_encabezado) < 2 or len(del_objeto) < 2 or del_encabezado[0] == del_objeto[0])
            if iguales:
                return None
            return (comentario.start() + indicado.start("nombre"), re.sub(r"\s+", "", nombre),
                    re.sub(r"\s+", "", texto[objeto.start("nombre"):objeto.end("nombre")]))
    return None


def mensaje_nombre_encabezado_distinto(del_encabezado: str, del_objeto: str) -> str:
    # Texto de la usuaria (19 nov.).
    return (f"Se identificó que el encabezado indica el nombre {del_encabezado}, mientras que el procedimiento se crea "
            f"como {del_objeto}. Se recomienda actualizar el nombre indicado en el encabezado para que coincida con el "
            f"procedimiento creado y mantener la documentación alineada con el objeto.")
