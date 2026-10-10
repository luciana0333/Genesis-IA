# -*- coding: utf-8 -*-
"""
diccionario.py
----------------
Analizador especializado en el diccionario de datos
(sp_addextendedproperty) de un procedimiento almacenado.

Recibe DOS textos por separado, tal como se manejan en la revision real:
  - texto_procedimiento: el CREATE/ALTER PROCEDURE con sus parametros
  - texto_diccionario: el script de sp_addextendedproperty que lo documenta

Compara la "realidad" (procedimiento) contra la "documentacion"
(diccionario) y reporta discrepancias.
"""

import re
from typing import List, Set, Tuple, Dict, Optional

from app.analizadores.diccionario_agrupar import agrupar, con_elemento, ubicar
from app.analizadores.ortografia import palabras_mal_escritas
from app.analizadores.propiedades_extendidas import como_llamadas_crudas, leer_propiedades_extendidas
from app.modelos.hallazgo import Hallazgo, Severidad, OrigenAnalisis
from app.reglas.reglas_diccionario_procedimientos import REGLAS_DICCIONARIO_PROCEDIMIENTOS


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "realidad" (el procedimiento)
# ---------------------------------------------------------------------------

def extraer_parametros(texto_procedimiento: str) -> Set[str]:
    """Extrae los parametros declarados en CREATE/ALTER PROCEDURE."""
    patron = re.compile(
        r"(?:CREATE|ALTER)\s+PROCEDURE\s+[\w\.]+\s*\(?(.*?)\)?\s*AS\b",
        re.IGNORECASE | re.DOTALL
    )
    coincidencia = patron.search(texto_procedimiento)
    if not coincidencia:
        coincidencia = re.search(
            r"(?:CREATE|ALTER)\s+PROCEDURE\s+[\w\.]+\s*\((.*?)\)\s*(?:;|\Z)",
            texto_procedimiento,
            re.IGNORECASE | re.DOTALL,
        )
    if not coincidencia:
        return set()
    bloque_parametros = coincidencia.group(1)
    return set(re.findall(r"@\w+", bloque_parametros))


def extraer_tipo_sentencia(texto_procedimiento: str) -> str:
    """Determina si el procedimiento es un CREATE o un ALTER."""
    if re.search(r"\bALTER\s+PROCEDURE\b", texto_procedimiento, re.IGNORECASE):
        return "ALTER"
    if re.search(r"\bCREATE\s+PROCEDURE\b", texto_procedimiento, re.IGNORECASE):
        return "CREATE"
    return "DESCONOCIDO"


def extraer_esquema_y_nombre(texto_procedimiento: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) del procedimiento, o (None, None)."""
    m = re.search(
        r"(?:CREATE|ALTER)\s+PROC(?:EDURE)?\s+(?:\[?(\w+)\]?\s*\.\s*)?\[?(\w+)\]?",
        texto_procedimiento, re.IGNORECASE
    )
    if m:
        return m.group(1), m.group(2)
    return None, None


def _validar_esquema_declarado(texto_procedimiento: str, esquema: Optional[str], nombre_proc: str) -> List[Hallazgo]:
    """El procedimiento indica su esquema en el CREATE o ALTER."""
    if esquema:
        return []
    m = re.search(r"(?:CREATE|ALTER)\s+PROC", texto_procedimiento, re.IGNORECASE)
    return [Hallazgo(
        linea=_numero_linea(texto_procedimiento, m.start() if m else 0),
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS["OBJETO_SIN_ESQUEMA"].severidad),
        regla="OBJETO_SIN_ESQUEMA",
        mensaje=f"El procedimiento {nombre_proc} no indica su esquema. Anteponer el esquema al nombre, "
                f"ya que así se evita crear o modificar el objeto en un esquema equivocado y el "
                f"diccionario puede documentarlo correctamente (ej.: dbo.{nombre_proc}).",
    )]


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "documentacion" (el script del diccionario)
# ---------------------------------------------------------------------------

def extraer_llamadas_extendedproperty(texto_diccionario: str) -> List[Tuple[int, Dict[str, str]]]:
    """
    Devuelve una lista de (posicion_en_texto, argumentos) por cada
    llamada a sp_addextendedproperty / sp_updateextendedproperty,
    leidas del SCRIPT DEL DICCIONARIO (no del procedimiento).
    """
    # El lector compartido reconoce cada sentencia aunque no haya GO ni ";",
    # y respeta cadenas y comentarios.
    return como_llamadas_crudas(leer_propiedades_extendidas(texto_diccionario))


def _limpiar_valor(valor: str) -> str:
    """Quita comillas y el prefijo N de un valor tipo N'texto' -> texto."""
    return valor.replace("N'", "").replace("'", "").strip()


def _es_sentencia_de_procedimiento(args: Dict[str, str]) -> bool:
    """La llamada documenta al procedimiento en sí (no a un PARAMETER)."""
    level1type = args.get("level1type", "").upper()
    level2type = args.get("level2type", "").upper()
    return "PROCEDURE" in level1type and "PARAMETER" not in level2type


def _es_descripcion_procedimiento_valida(args: Dict[str, str]) -> bool:
    """Indica si la llamada documenta la descripcion del procedimiento,
    excluyendo las entradas de PARAMETER.
    """
    level1type = args.get("level1type", "").upper()
    level2type = args.get("level2type", "").upper()
    if "PROCEDURE" not in level1type:
        return False
    if "PARAMETER" in level2type:
        return False
    return _limpiar_valor(args.get("value", "")) != ""


def _nombre_completo(esquema: Optional[str], nombre: str) -> str:
    """'esquema.nombre' si el objeto declara esquema; si no, solo 'nombre'."""
    return f"{esquema}.{nombre}" if esquema else nombre


def _numero_linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


# ---------------------------------------------------------------------------
# VALIDACIONES INDIVIDUALES
# ---------------------------------------------------------------------------

def _validar_esquema(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema_real: Optional[str],
    texto_diccionario: str
) -> List[Hallazgo]:
    """El @level0name del diccionario debe coincidir con el esquema real
    del procedimiento (ej. Dbo, CCE, RRHH)."""
    hallazgos = []
    if not esquema_real:
        return hallazgos
    for pos, args in llamadas:
        if "level0name" in args:
            valor = _limpiar_valor(args["level0name"])
            if valor and valor.lower() != esquema_real.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="ESQUEMA_NO_COINCIDE",
                    mensaje=f"El diccionario indica el esquema '{valor}', pero el procedimiento está "
                            f"en '{esquema_real}'. Corregir @level0name, ya que si no coinciden el "
                            f"diccionario documenta un objeto que no existe."
                ))
    return hallazgos


def _validar_descripciones_vacias(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str,
) -> List[Hallazgo]:
    """Un parametro puede estar 'documentado' pero con @value vacio ('') -
    eso no cuenta como documentacion real."""
    hallazgos = []
    for pos, args in llamadas:
        es_parametro = "PARAMETER" in args.get("level2type", "").upper()
        if es_parametro and "value" in args:
            valor_desc = _limpiar_valor(args["value"])
            nombre_param = _limpiar_valor(args.get("level2name", "?"))
            if valor_desc == "":
                hallazgos.append(con_elemento(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.MEDIO,
                    regla="DESCRIPCION_VACIA",
                    mensaje=f"El parámetro {nombre_param} está documentado, pero su descripción "
                            f"(@value) está vacía. Se recomienda indicar para qué se usa el parámetro, "
                            f"ya que así el diccionario es útil para quien lo consulte."
                ), nombre_param))
    return hallazgos


def _validar_parametros_faltantes(
    parametros_reales: Set[str],
    llamadas: List[Tuple[int, Dict[str, str]]],
    tipo_sentencia: str,
    esquema: str,
    nombre_proc: str
) -> List[Hallazgo]:
    """
    Compara parametros reales vs documentados. El mensaje cambia segun
    si es CREATE o ALTER, y segun si el diccionario tiene o no llamadas.
    """
    hallazgos = []

    # SQL Server no distingue mayúsculas en los nombres: @nClienteId = @NCLIENTEID.
    parametros_documentados = set()
    for _, args in llamadas:
        if "level2name" in args and "PARAMETER" in args.get("level2type", "").upper():
            parametros_documentados.add(_limpiar_valor(args["level2name"]).upper())

    faltantes = [p for p in parametros_reales if p.upper() not in parametros_documentados]

    for p in sorted(faltantes, key=str.upper):
        if tipo_sentencia == "ALTER":
            # El procedimiento ya existía: el parámetro puede estar documentado
            # de antes. No es error; se pide validar.
            hallazgos.append(con_elemento(Hallazgo(
                linea=1,
                origen=OrigenAnalisis.DICCIONARIO,
                severidad=Severidad.BAJO,
                regla="VALIDAR_DOCUMENTACION_ALTER",
                mensaje=(
                    f"Es un ALTER PROCEDURE y el parámetro {p} no está en el diccionario. "
                    f"Se recomienda validar si ya estaba documentado y, si es nuevo, añadirlo con su descripción."
                ),
            ), p))
            continue

        # En un CREATE el procedimiento es nuevo: todo debe documentarse.
        hallazgos.append(con_elemento(Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.ALTO,
            regla="PARAMETRO_FALTANTE",
            mensaje=(
                f"El parámetro {p} no se encuentra documentado. Se recomienda añadirlo al "
                f"diccionario del procedimiento con su descripción, ya que todo parámetro de un "
                f"procedimiento nuevo debe estar documentado."
            ),
        ), p))

    return hallazgos


def _validar_alter_sin_diccionario(
    tipo_sentencia: str,
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_proc: str
) -> List[Hallazgo]:
    """
    Caso especial: es un ALTER y el script de diccionario esta vacio
    (no se proporciono, o no tiene ninguna llamada a sp_addextendedproperty).
    No asumimos error - pedimos validacion manual.
    """
    if tipo_sentencia == "ALTER" and not llamadas:
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="ALTER_SIN_DICCIONARIO",
            mensaje=(
                f"Se modifica el procedimiento {_nombre_completo(esquema, nombre_proc)} (ALTER), pero no "
                f"se pegó ningún diccionario. Se recomienda documentar los parámetros que se "
                f"agreguen o cambien."
            )
        )]
    return []


def _validar_nombre_procedimiento(
    llamadas: List[Tuple[int, Dict[str, str]]],
    nombre_proc: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """El @level1name debe coincidir exactamente con el nombre real."""
    hallazgos = []
    for pos, args in llamadas:
        if "level1name" in args and "PROCEDURE" in args.get("level1type", "").upper():
            valor = _limpiar_valor(args["level1name"])
            if valor.lower() != nombre_proc.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="NOMBRE_NO_COINCIDE",
                    mensaje=f"El diccionario indica el nombre '{valor}', pero el procedimiento "
                            f"se llama '{nombre_proc}'. Corregir @level1name, ya que si no coinciden "
                            f"el diccionario documenta un objeto que no existe."
                ))
    return hallazgos


def _validar_valores_sin_comillas(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str
) -> List[Hallazgo]:
    """Los valores de nombre deben ir entre comillas N'...'."""
    hallazgos = []
    for pos, args in llamadas:
        for clave in ("level0name", "level1name", "level2name"):
            if clave in args:
                valor = args[clave]
                if not (valor.startswith("N'") or valor.startswith("'")):
                    hallazgos.append(Hallazgo(
                        linea=_numero_linea(texto_diccionario, pos),
                        origen=OrigenAnalisis.DICCIONARIO,
                        severidad=Severidad.CRITICO,
                        regla="VALOR_SIN_COMILLAS",
                        mensaje=f"El nombre @{clave}={valor} no está entre comillas. "
                                f"Escribirlo como N'...', ya que sin comillas la sentencia falla."
                    ))
    return hallazgos


def _validar_procedimiento_documentado(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_proc: str,
    tipo_sentencia: str,
) -> List[Hallazgo]:
    """Debe existir al menos una descripcion valida a nivel PROCEDURE,
    no solo descripciones de PARAMETER. Es alto en un CREATE.
    """
    if any(_es_descripcion_procedimiento_valida(a) for _, a in llamadas):
        return []

    # La sentencia existe pero con @value vacío: está documentado, sin descripción.
    if any(_es_sentencia_de_procedimiento(a) for _, a in llamadas):
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="DESCRIPCION_PROCEDIMIENTO_VACIA",
            mensaje=f"El procedimiento {_nombre_completo(esquema, nombre_proc)} está documentado, pero no "
                    f"tiene una descripción (@value está vacío). Se recomienda indicar para qué "
                    f"sirve el procedimiento."
        )]

    if tipo_sentencia == "ALTER":
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="VALIDAR_DOCUMENTACION_ALTER",
            mensaje=f"Es un ALTER PROCEDURE y el diccionario no incluye la descripción del "
                    f"procedimiento {_nombre_completo(esquema, nombre_proc)}. Se recomienda validar que ya "
                    f"esté documentado y, si no lo está, añadir su descripción."
        )]

    return [Hallazgo(
        linea=1,
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad.ALTO,
        regla="PROCEDIMIENTO_SIN_DESCRIPCION",
        mensaje=f"El procedimiento {_nombre_completo(esquema, nombre_proc)} no se encuentra "
                f"documentado. Añadir la descripción del procedimiento al diccionario, ya que todo "
                f"procedimiento nuevo debe estar documentado."
    )]


def _texto_de_valor(crudo: str) -> str:
    """N'texto con l''apostrofe' -> texto con l'apostrofe."""
    valor = crudo.strip()
    if valor[:2].upper() == "N'":
        valor = valor[1:]
    if len(valor) >= 2 and valor.startswith("'") and valor.endswith("'"):
        valor = valor[1:-1]
    return valor.replace("''", "'")


def _validar_ortografia(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str,
    esquema: str,
    nombre_proc: str,
    parametros_reales: Set[str],
) -> List[Hallazgo]:
    """Palabras mal escritas en las descripciones (sin exigir tildes)."""
    nombres_objeto = {esquema or "", nombre_proc, *parametros_reales}
    hallazgos = []
    for pos, args in llamadas:
        if "PROCEDURE" not in args.get("level1type", "").upper() or "value" not in args:
            continue
        descripcion = _texto_de_valor(args["value"])
        if not descripcion.strip():
            continue
        if "PARAMETER" in args.get("level2type", "").upper():
            objeto = f"del parámetro {_limpiar_valor(args.get('level2name', '?'))}"
        else:
            objeto = f"del procedimiento {_nombre_completo(esquema, nombre_proc)}"
        errores = palabras_mal_escritas(descripcion, nombres_objeto)
        if not errores:
            continue
        detalle = ", ".join(
            f"'{palabra}' (¿quiso decir '{opciones[0]}'?)" if opciones else f"'{palabra}'"
            for palabra, opciones in errores
        )
        texto = "una palabra mal escrita" if len(errores) == 1 else "palabras mal escritas"
        hallazgos.append(Hallazgo(
            linea=_numero_linea(texto_diccionario, pos),
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="ERROR_ORTOGRAFICO",
            mensaje=f"La descripción {objeto} tiene {texto}: {detalle}. Se recomienda corregirla, "
                    f"ya que el diccionario es la documentación oficial del objeto.",
        ))
    return hallazgos


# ---------------------------------------------------------------------------
# ORQUESTADOR PRINCIPAL
# ---------------------------------------------------------------------------

# Reglas que, repetidas, se reportan una vez con la lista de elementos.
_PLANTILLAS_AGRUPADAS = {
    "PARAMETRO_FALTANTE": (
        "parámetros sin documentar",
        "Se recomienda añadir los parámetros faltantes al diccionario del procedimiento, cada uno "
        "con su descripción, ya que todo parámetro de un procedimiento nuevo debe estar documentado.",
    ),
    "VALIDAR_DOCUMENTACION_ALTER": (
        "parámetros que no están en el diccionario",
        "Se recomienda validar si ya estaban documentados y, si son nuevos, añadirlos con su descripción.",
    ),
    "DESCRIPCION_VACIA": (
        "parámetros con la descripción vacía",
        "Se recomienda indicar en @value para qué se usa cada parámetro.",
    ),
}


def verificar_diccionario(
    texto_procedimiento: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """
    Funcion principal: compara el procedimiento (realidad) contra el
    script del diccionario (documentacion) y devuelve los hallazgos.
    """
    hallazgos: List[Hallazgo] = []

    esquema, nombre_proc = extraer_esquema_y_nombre(texto_procedimiento)
    if nombre_proc is None:
        return hallazgos

    tipo_sentencia = extraer_tipo_sentencia(texto_procedimiento)
    parametros_reales = extraer_parametros(texto_procedimiento)
    llamadas = extraer_llamadas_extendedproperty(texto_diccionario)

    # Caso especial ALTER sin ningun rastro de diccionario: se corta aqui,
    # no tiene sentido seguir comparando parametro por parametro si no
    # hay nada con que comparar.
    hallazgos += _validar_esquema_declarado(texto_procedimiento, esquema, nombre_proc)
    hallazgos += _validar_alter_sin_diccionario(
        tipo_sentencia, llamadas, esquema, nombre_proc
    )
    if tipo_sentencia == "ALTER" and not llamadas:
        return hallazgos

    hallazgos += _validar_procedimiento_documentado(llamadas, esquema, nombre_proc, tipo_sentencia)
    hallazgos += _validar_parametros_faltantes(
        parametros_reales, llamadas, tipo_sentencia, esquema, nombre_proc
    )
    hallazgos += _validar_nombre_procedimiento(llamadas, nombre_proc, texto_diccionario)
    hallazgos += _validar_esquema(llamadas, esquema, texto_diccionario)
    hallazgos += _validar_descripciones_vacias(llamadas, texto_diccionario)
    hallazgos += _validar_ortografia(llamadas, texto_diccionario, esquema, nombre_proc, parametros_reales)
    if REGLAS_DICCIONARIO_PROCEDIMIENTOS["VALOR_SIN_COMILLAS"].activo:
        hallazgos += _validar_valores_sin_comillas(llamadas, texto_diccionario)

    # Los parámetros se ubican en su línea del CREATE/ALTER.
    for hallazgo in hallazgos:
        if getattr(hallazgo, "elemento", None) and hallazgo.regla != "DESCRIPCION_VACIA":
            ubicar(hallazgo, texto_procedimiento)
    return agrupar(hallazgos, _PLANTILLAS_AGRUPADAS)