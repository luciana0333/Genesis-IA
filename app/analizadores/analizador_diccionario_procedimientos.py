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

import difflib
import re
from typing import List, Set, Tuple, Dict, Optional

from app.analizadores.diccionario_agrupar import agrupar, con_elemento, ubicar
from app.analizadores.diccionario_nomenclatura import nomenclatura_procedimiento
from app.analizadores.ortografia import elemento_ortografico, palabras_mal_escritas, redactar_error_ortografico
from app.analizadores.propiedades_extendidas import (
    como_llamadas_crudas,
    descripcion_mal_escrita,
    leer_propiedades_extendidas,
)
from app.modelos.hallazgo import Hallazgo, Severidad, OrigenAnalisis
from app.reglas.reglas_diccionario_procedimientos import REGLAS_DICCIONARIO_PROCEDIMIENTOS


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "realidad" (el procedimiento)
# ---------------------------------------------------------------------------

# Encabezado del procedimiento: CREATE, ALTER o CREATE OR ALTER, PROC o PROCEDURE,
# y el nombre con o sin esquema y corchetes.
_ENCABEZADO = re.compile(
    r"\b(CREATE(?:\s+OR\s+ALTER)?|ALTER)\s+PROC(?:EDURE)?\s+"
    r"(?:\[[^\]]+\]|[\w$#]+)(?:\s*\.\s*(?:\[[^\]]+\]|[\w$#]+)){0,2}",
    re.IGNORECASE,
)


def _sin_comentarios_ni_textos(texto: str) -> str:
    """Reemplaza comentarios y textos entre comillas por espacios (conserva posiciones)."""
    return re.sub(
        r"--[^\n]*|/\*[\s\S]*?\*/|N?'(?:[^']|'')*'",
        lambda m: re.sub(r"[^\n]", " ", m.group(0)),
        texto,
    )


def extraer_parametros(texto_procedimiento: str) -> Set[str]:
    """Parámetros declarados entre el nombre del procedimiento y su AS."""
    limpio = _sin_comentarios_ni_textos(texto_procedimiento)
    encabezado = _ENCABEZADO.search(limpio)
    if not encabezado:
        return set()
    resto = limpio[encabezado.end():]
    fin = re.search(r"\bAS\b", resto, re.IGNORECASE)
    bloque = resto[:fin.start()] if fin else resto
    return set(re.findall(r"(?<![@\w])@\w+", bloque))


def extraer_tipo_sentencia(texto_procedimiento: str) -> str:
    """CREATE o ALTER. CREATE OR ALTER cuenta como CREATE: puede crear un procedimiento nuevo."""
    encabezado = _ENCABEZADO.search(_sin_comentarios_ni_textos(texto_procedimiento))
    if not encabezado:
        return "DESCONOCIDO"
    return "ALTER" if encabezado.group(1).upper() == "ALTER" else "CREATE"


def extraer_esquema_y_nombre(texto_procedimiento: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) del procedimiento, o (None, None)."""
    encabezado = _ENCABEZADO.search(_sin_comentarios_ni_textos(texto_procedimiento))
    if not encabezado:
        return None, None
    # Hasta tres partes (Base.Esquema.Nombre): el nombre es la última y el esquema la anterior.
    nombre_completo = encabezado.group(0)[re.match(r"\S+(?:\s+OR\s+ALTER)?\s+\S+\s+", encabezado.group(0), re.IGNORECASE).end():]
    partes = [p.strip().strip("[]") for p in nombre_completo.split(".")]
    return (partes[-2] if len(partes) > 1 else None), partes[-1]


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


def _validar_nomenclatura(texto_procedimiento: str, tipo_sentencia: str, nombre_proc: str) -> List[Hallazgo]:
    """Al crear el procedimiento, su nombre sigue PA_Tabla_Acción_Finalidad (en ALTER no se revisa)."""
    if tipo_sentencia != "CREATE":
        return []
    m = _ENCABEZADO.search(_sin_comentarios_ni_textos(texto_procedimiento))
    linea = _numero_linea(texto_procedimiento, m.start() if m else 0)
    return [
        Hallazgo(
            linea=linea,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS[regla].severidad),
            regla=regla,
            mensaje=mensaje,
        )
        for regla, mensaje in nomenclatura_procedimiento(nombre_proc)
    ]


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
                            f"en '{esquema_real}'. Corregir el esquema en el diccionario por "
                            f"'{esquema_real}', ya que no coincide con el esquema del procedimiento y "
                            f"la documentación quedaría en un objeto que no existe."
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
                    mensaje=f"El parámetro {nombre_param} figura en el diccionario, pero no cuenta con una "
                            f"descripción. Completar la descripción indicando para qué se usa el "
                            f"parámetro, de modo que quede claro para quien consulte el procedimiento."
                ), nombre_param))
    return hallazgos


_PARAMETROS_OBLIGATORIOS = ("name", "value", "level0type", "level0name", "level1type", "level1name")


def _hallazgo_catalogo(linea: int, regla: str, mensaje: str) -> Hallazgo:
    """Hallazgo con la severidad definida en el catálogo de reglas."""
    return Hallazgo(
        linea=linea,
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )


def _validar_sentencias(texto_diccionario: str) -> List[Hallazgo]:
    """Sentencias mal escritas o a las que les faltan datos obligatorios: SQL Server no las ejecuta."""
    hallazgos = []
    for ll in leer_propiedades_extendidas(texto_diccionario):
        hallazgos += [_hallazgo_catalogo(linea, "SINTAXIS_DICCIONARIO", mensaje) for linea, mensaje in ll.errores]
        faltantes = [f"@{p}" for p in _PARAMETROS_OBLIGATORIOS if not ll.tiene(p)]
        if ll.tiene("level2type") != ll.tiene("level2name"):
            faltantes.append("@level2name" if ll.tiene("level2type") else "@level2type")
        if faltantes:
            hallazgos.append(_hallazgo_catalogo(
                ll.linea, "PARAMETROS_INCOMPLETOS",
                f"Se comprobó que a la sentencia le faltan datos obligatorios: {', '.join(faltantes)}. Completar "
                f"los datos faltantes, ya que sin ellos la sentencia no se ejecuta.",
            ))
    return hallazgos


def _validar_parametros_inexistentes(texto_diccionario: str, parametros_reales: Set[str], nombre_proc: str) -> List[Hallazgo]:
    """Se documenta un parámetro que el procedimiento no tiene (mal escrito o eliminado)."""
    reales = {p.upper(): p for p in parametros_reales}
    hallazgos = []
    for ll in leer_propiedades_extendidas(texto_diccionario):
        if "PARAMETER" not in ll.texto("level2type").upper():
            continue
        nombre = ll.texto("level2name")
        if not nombre or nombre.upper() in reales:
            continue
        parecido = difflib.get_close_matches(nombre.upper(), list(reales), n=1, cutoff=0.75)
        sugerencia = f" (¿quiso decir '{reales[parecido[0]]}'?)" if parecido else ""
        hallazgos.append(con_elemento(_hallazgo_catalogo(
            ll.linea, "PARAMETRO_NO_EXISTE",
            f"Se verificó que el parámetro {nombre} está documentado, pero no existe en el procedimiento "
            f"{nombre_proc}{sugerencia}. Corregir el nombre del parámetro en el diccionario o retirar la sentencia, "
            f"ya que SQL Server no la ejecutará.",
        ), nombre))
    return hallazgos


def _validar_nombre_propiedad(texto_diccionario: str, esquema: Optional[str], nombre_proc: str) -> List[Hallazgo]:
    """
    @name parecido a MS_Description pero mal escrito: la descripción se guarda,
    pero no se reconoce como la del diccionario.
    """
    hallazgos = []
    for ll in leer_propiedades_extendidas(texto_diccionario):
        nombre = ll.texto("name")
        if not descripcion_mal_escrita(nombre):
            continue
        if "PARAMETER" in ll.texto("level2type").upper():
            objeto = f"parámetro {ll.texto('level2name')}"
        else:
            objeto = f"procedimiento {_nombre_completo(esquema, nombre_proc)}"
        hallazgos.append(con_elemento(_hallazgo_catalogo(
            ll.linea, "NOMBRE_PROPIEDAD_INCORRECTO",
            f"La propiedad del {objeto} se registra como '{nombre}', por lo que no se reconocerá como "
            f"su descripción. Usar «N'MS_Description'» como nombre de la propiedad, ya que es el nombre estándar "
            f"de las descripciones del diccionario.",
        ), f"{objeto} ('{nombre}')"))
    return hallazgos


def _validar_duplicados(texto_diccionario: str) -> List[Hallazgo]:
    """
    Agregar dos veces la misma descripción falla en SQL Server ("property
    already exists"). Solo aplica a sp_addextendedproperty.
    """
    vistos: Dict[Tuple[str, str], int] = {}
    hallazgos = []
    for ll in leer_propiedades_extendidas(texto_diccionario):
        if ll.operacion != "add" or ll.texto("name").upper() != "MS_DESCRIPTION":
            continue
        if "PARAMETER" in ll.texto("level2type").upper():
            nombre = ll.texto("level2name")
            clave, objeto = ("parametro", nombre.upper()), f"parámetro {nombre}"
        elif ll.texto("level1name") and not ll.texto("level2type"):
            nombre = ll.texto("level1name")
            clave, objeto = ("procedimiento", nombre.upper()), f"procedimiento {nombre}"
        else:
            continue
        if clave not in vistos:
            vistos[clave] = ll.linea
            continue
        hallazgos.append(con_elemento(Hallazgo(
            linea=ll.linea,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS["DOCUMENTACION_DUPLICADA"].severidad),
            regla="DOCUMENTACION_DUPLICADA",
            mensaje=f"Se identificó que el {objeto} se encuentra documentado dos veces, siendo la primera "
                    f"declaración en la línea {vistos[clave]}. Se recomienda retirar una de las declaraciones "
                    f"duplicadas, ya que SQL Server genera un error al intentar registrar nuevamente la misma "
                    f"propiedad.",
        ), f"{objeto} (primera declaración en la línea {vistos[clave]})"))
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
                    f"El parámetro {p} no se encuentra en el diccionario, aunque podría estar "
                    f"documentado previamente al tratarse de una modificación del procedimiento (ALTER PROCEDURE). "
                    f"Verificar si ya cuenta con descripción en el diccionario y, de no tenerla, incluir la "
                    f"descripción respectiva."
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
                f"Se detectó que el procedimiento {_nombre_completo(esquema, nombre_proc)} se modifica "
                f"(ALTER PROCEDURE), pero no se adjuntó su diccionario. Incluir la documentación de los "
                f"parámetros que se agreguen o modifiquen, para mantener el diccionario actualizado."
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
            # Vacío (N'') no es «no coincide»: lo marca _validar_nombres_vacios.
            if valor and valor.lower() != nombre_proc.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="NOMBRE_NO_COINCIDE",
                    mensaje=f"El diccionario indica el nombre '{valor}', pero el procedimiento "
                            f"se llama '{nombre_proc}'. Corregir el nombre en el diccionario por "
                            f"'{nombre_proc}', ya que no coincide con el nombre del procedimiento y "
                            f"la documentación quedaría en un objeto que no existe."
                ))
    return hallazgos


def _posicion_valor(texto_diccionario: str, pos: int) -> int:
    """Posición del @value de la llamada que empieza en `pos` (o `pos` si no se encuentra)."""
    valor = re.compile(r"@value\s*=", re.IGNORECASE).search(texto_diccionario, pos)
    return valor.start() if valor else pos


def _validar_nombres_vacios(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str,
    esquema: Optional[str],
    nombre_proc: str,
) -> List[Hallazgo]:
    """@level0name, @level1name o @level2name vacíos (N''): el diccionario no indica el objeto."""
    hallazgos = []
    for pos, args in llamadas:
        for clave, que, ejemplo in (
            ("level0name", "el esquema del procedimiento", esquema or "dbo"),
            ("level1name", "el nombre del procedimiento", nombre_proc or "PA_Tabla_Sel_Finalidad"),
            ("level2name", "el nombre del parámetro", "@nParametro"),
        ):
            if clave in args and _limpiar_valor(args[clave]) == "":
                # La línea es la del parámetro vacío, no la del inicio del EXEC.
                donde = re.compile(r"@" + clave + r"\s*=", re.IGNORECASE).search(texto_diccionario, pos)
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, donde.start() if donde else pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS["NOMBRE_VACIO"].severidad),
                    regla="NOMBRE_VACIO",
                    mensaje=f"La sentencia no indica {que}. Colocar {que} "
                            f"(ej.: «@{clave}=N'{ejemplo}'»), ya que sin él la descripción no quedará asociada a "
                            f"ningún objeto.",
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
                        mensaje=f"Se detectó que el nombre {valor} no está entre comillas. Colocarlo entre "
                                f"comillas simples con la N delante (ej.: «N'{valor}'»), ya que sin ellas la "
                                f"sentencia no se ejecuta."
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
            mensaje=f"Se comprobó que el diccionario del procedimiento {_nombre_completo(esquema, nombre_proc)} "
                    f"está documentado, pero su descripción se encuentra vacía. Incluir la descripción respectiva "
                    f"que indique la finalidad del procedimiento, para así contar con una documentación completa."
        )]

    if tipo_sentencia == "ALTER":
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="VALIDAR_DOCUMENTACION_ALTER",
            mensaje=f"El diccionario no incluye la descripción del procedimiento "
                    f"{_nombre_completo(esquema, nombre_proc)}, aunque podría estar documentado previamente al "
                    f"tratarse de una modificación (ALTER PROCEDURE). Verificar si ya cuenta con descripción en "
                    f"el diccionario y, de no tenerla, incluir la descripción respectiva."
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
        hallazgos.append(con_elemento(Hallazgo(
            # La línea es la del @value (donde está el texto con el error), no la del EXEC.
            linea=_numero_linea(texto_diccionario, _posicion_valor(texto_diccionario, pos)),
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="ERROR_ORTOGRAFICO",
            mensaje=redactar_error_ortografico(objeto, errores, "del procedimiento"),
        ), elemento_ortografico(objeto, errores)))
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
        "parámetros que no se encuentran en el diccionario",
        "Verificar si ya cuentan con descripción en el diccionario, al tratarse de una modificación del "
        "procedimiento (ALTER PROCEDURE), y, de no tenerla, incluir la descripción respectiva de cada uno.",
    ),
    "DESCRIPCION_VACIA": (
        "parámetros con la descripción vacía",
        "Completar la descripción indicando para qué se usa cada parámetro, de modo que quede claro para "
        "quien consulte el procedimiento.",
    ),
    "ERROR_ORTOGRAFICO": (
        "descripciones con errores de escritura",
        "Se recomienda corregir cada palabra por la sugerida (o revisar su escritura si no hay sugerencia), ya que el diccionario es la documentación oficial del procedimiento.",
    ),
    "PARAMETRO_NO_EXISTE": (
        "parámetros documentados que no existen en el procedimiento",
        "Corregir el nombre de cada parámetro en el diccionario o retirar esas sentencias, ya que SQL Server "
        "no las ejecutará.",
    ),
    "NOMBRE_PROPIEDAD_INCORRECTO": (
        "propiedades con el nombre mal escrito",
        "Usar «N'MS_Description'» como nombre de la propiedad en esas sentencias, ya que es el nombre estándar "
        "de las descripciones del diccionario.",
    ),
    "DOCUMENTACION_DUPLICADA": (
        "declaraciones duplicadas",
        "Se recomienda retirar las declaraciones duplicadas y dejar una sola por cada una, ya que SQL Server "
        "genera un error al intentar registrar nuevamente la misma propiedad.",
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
    hallazgos += _validar_nomenclatura(texto_procedimiento, tipo_sentencia, nombre_proc)
    hallazgos += _validar_alter_sin_diccionario(
        tipo_sentencia, llamadas, esquema, nombre_proc
    )
    if tipo_sentencia == "ALTER" and not llamadas:
        return hallazgos

    hallazgos += _validar_procedimiento_documentado(llamadas, esquema, nombre_proc, tipo_sentencia)
    hallazgos += _validar_parametros_faltantes(
        parametros_reales, llamadas, tipo_sentencia, esquema, nombre_proc
    )
    hallazgos += _validar_nombres_vacios(llamadas, texto_diccionario, esquema, nombre_proc)
    hallazgos += _validar_nombre_procedimiento(llamadas, nombre_proc, texto_diccionario)
    hallazgos += _validar_esquema(llamadas, esquema, texto_diccionario)
    hallazgos += _validar_descripciones_vacias(llamadas, texto_diccionario)
    hallazgos += _validar_duplicados(texto_diccionario)
    hallazgos += _validar_sentencias(texto_diccionario)
    hallazgos += _validar_parametros_inexistentes(texto_diccionario, parametros_reales, nombre_proc)
    hallazgos += _validar_nombre_propiedad(texto_diccionario, esquema, nombre_proc)
    hallazgos += _validar_ortografia(llamadas, texto_diccionario, esquema, nombre_proc, parametros_reales)
    if REGLAS_DICCIONARIO_PROCEDIMIENTOS["VALOR_SIN_COMILLAS"].activo:
        hallazgos += _validar_valores_sin_comillas(llamadas, texto_diccionario)

    # Los parámetros se ubican en su línea del CREATE/ALTER.
    for hallazgo in hallazgos:
        if getattr(hallazgo, "elemento", None) and hallazgo.regla not in ("DESCRIPCION_VACIA", "NOMBRE_PROPIEDAD_INCORRECTO"):
            ubicar(hallazgo, texto_procedimiento)
    return agrupar(hallazgos, _PLANTILLAS_AGRUPADAS)