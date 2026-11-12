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

from app.analizadores.descripcion_vs_nombre import contradice
from app.analizadores.diccionario_agrupar import agrupar, asignar_secciones, con_elemento, juntar_ortografia, ubicar
from app.analizadores.diccionario_nomenclatura import nomenclatura_procedimiento
from app.analizadores.nombre_por_prefijo import emparejar_por_prefijo, solo_un_error_por_sentencia
from app.analizadores.diccionario_varios import (
    agrupar_varios, nombres_del_script, objetos_sin_script, por_objeto, sin_otros_objetos,
)
from app.analizadores.objetos_repetidos import hallazgo_repetidos, quitar_creaciones_repetidas
from app.analizadores.palabra_repetida import palabra_repetida_agrupada
from app.analizadores.objeto_programable import FUNCION, POR_CLAVE, PROCEDIMIENTO, actual, restaurar, usar
from app.analizadores.ortografia import (
    ACCION_ORTOGRAFIA, elemento_ortografico, palabras_mal_escritas, redactar_error_ortografico,
)
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

# Encabezado del objeto: CREATE, ALTER o CREATE OR ALTER, PROC/PROCEDURE o FUNCTION, y el nombre con o sin
# esquema y corchetes. Depende del objeto en revisión (objeto_programable).
def _encabezado():
    return actual().encabezado


# Se conserva el nombre para quien lo importe: el de procedimientos.
_ENCABEZADO = PROCEDIMIENTO.encabezado


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
    encabezado = _encabezado().search(limpio)
    if not encabezado:
        return set()
    resto = limpio[encabezado.end():]
    # Procedimiento: hasta su AS. Función: hasta RETURNS (RETURNS @Resultado TABLE … no es un parámetro).
    fin = actual().fin_parametros.search(resto)
    bloque = resto[:fin.start()] if fin else resto
    return set(re.findall(r"(?<![@\w])@\w+", bloque))


def extraer_tipo_sentencia(texto_procedimiento: str) -> str:
    """CREATE o ALTER. CREATE OR ALTER cuenta como CREATE: puede crear un objeto nuevo."""
    encabezado = _encabezado().search(_sin_comentarios_ni_textos(texto_procedimiento))
    if not encabezado:
        return "DESCONOCIDO"
    return "ALTER" if encabezado.group(1).upper() == "ALTER" else "CREATE"


def extraer_esquema_y_nombre(texto_procedimiento: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) del procedimiento o de la función, o (None, None)."""
    encabezado = _encabezado().search(_sin_comentarios_ni_textos(texto_procedimiento))
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
    m = _encabezado().search(texto_procedimiento)
    return [Hallazgo(
        linea=_numero_linea(texto_procedimiento, m.start() if m else 0),
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS["OBJETO_SIN_ESQUEMA"].severidad),
        regla="OBJETO_SIN_ESQUEMA",
        mensaje=f"{actual().El} {nombre_proc} no indica su esquema. Anteponer el esquema al nombre, "
                f"ya que así se evita crear o modificar el objeto en un esquema equivocado y el "
                f"diccionario puede documentarlo correctamente (ej.: dbo.{nombre_proc}).",
    )]


def _validar_nomenclatura(texto_procedimiento: str, tipo_sentencia: str, nombre_proc: str) -> List[Hallazgo]:
    """Al crear el procedimiento, su nombre sigue PA_Tabla_Acción_Finalidad (en ALTER no se revisa)."""
    if tipo_sentencia != "CREATE" or not actual().revisa_nomenclatura:
        return []
    m = _encabezado().search(_sin_comentarios_ni_textos(texto_procedimiento))
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
    """N'texto' -> texto: quita solo el prefijo N y las comillas de los extremos ('' dentro es una comilla).

    Antes se quitaba todo «N'» del valor y el final de N'DUN' (la N y la comilla) también se borraba:
    el esquema DUN se leía como DU.
    """
    valor = valor.strip()
    entre_comillas = re.fullmatch(r"N?'(.*)'", valor, re.IGNORECASE | re.DOTALL)
    if entre_comillas:
        return entre_comillas.group(1).replace("''", "'").strip()
    return valor.strip("'").strip()


def _es_sentencia_de_procedimiento(args: Dict[str, str]) -> bool:
    """La llamada documenta al procedimiento en sí (no a un PARAMETER)."""
    level1type = args.get("level1type", "").upper()
    level2type = args.get("level2type", "").upper()
    return actual().tipo_sql in level1type and not level2type


def _es_descripcion_procedimiento_valida(args: Dict[str, str]) -> bool:
    """Indica si la llamada documenta la descripcion del procedimiento,
    excluyendo las entradas de PARAMETER.
    """
    level1type = args.get("level1type", "").upper()
    level2type = args.get("level2type", "").upper()
    if actual().tipo_sql not in level1type:
        return False
    if level2type:  # PARAMETER, o un tipo mal escrito: no es la descripción del procedimiento
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
                    mensaje=f"El diccionario indica el esquema '{valor}', pero {actual().el} está "
                            f"en '{esquema_real}'. Corregir el esquema en el diccionario por "
                            f"'{esquema_real}', ya que no coincide con el esquema {actual().del_} y "
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
                            f"parámetro, de modo que quede claro para quien consulte {actual().el}."
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
        tipo2 = ll.texto("level2type")
        if tipo2 and tipo2.upper() != "PARAMETER":
            hallazgos.append(_hallazgo_catalogo(
                ll.linea, "TIPO_NIVEL_INCORRECTO",
                f"La sentencia indica '{tipo2}' como tipo del parámetro (@level2type), pero debe ser 'PARAMETER'. "
                f"Usar el tipo «N'PARAMETER'», ya que con otro tipo la sentencia falla.",
            ))
    return hallazgos


def _emparejar_parametros(
    hallazgos: List[Hallazgo], texto_diccionario: str, esquema: Optional[str], nombre_proc: str
) -> List[Hallazgo]:
    """Parámetro documentado que no existe + parámetro sin documentar con el mismo nombre salvo el prefijo
    (@cCodAge / @nCodAge): una sola observación. Solo si es del mismo esquema y procedimiento (7 nov.)."""
    inexistentes = {h.elemento: h for h in hallazgos if h.regla == "PARAMETRO_NO_EXISTE"}
    faltantes = {h.elemento: h for h in hallazgos if h.regla == "PARAMETRO_FALTANTE"}
    pares = emparejar_por_prefijo(inexistentes, faltantes)
    llamadas = leer_propiedades_extendidas(texto_diccionario)
    full = _nombre_completo(esquema, nombre_proc)
    quitar, nuevos = set(), []
    for documentado, real in pares.items():
        llamada = next((ll for ll in llamadas if ll.texto("level2name") == documentado), None)
        esquema_doc = llamada.texto("level0name") if llamada else ""
        proc_doc = llamada.texto("level1name") if llamada else ""
        if (esquema and esquema_doc and esquema_doc.upper() != esquema.upper()) or (
                proc_doc and proc_doc.upper() != nombre_proc.upper()):
            continue
        quitar |= {id(inexistentes[documentado]), id(faltantes[real])}
        nuevos.append(con_elemento(_hallazgo_catalogo(
            inexistentes[documentado].linea, "PARAMETRO_NOMBRE_INCORRECTO",
            f"Se identificó que en el diccionario se documenta el parámetro {documentado}, que no existe en el "
            f"{actual().nombre} {full}, pero parece referirse a {real}. Corregir el nombre del parámetro en el "
            f"diccionario (ej.: @level2name = N'{real}'), ya que SQL Server no encuentra el parámetro y el script "
            f"del diccionario falla.",
        ), f"{documentado} → {real}"))
    return [h for h in hallazgos if id(h) not in quitar] + nuevos


def _validar_parametros_inexistentes(texto_diccionario: str, parametros_reales: Set[str], nombre_proc: str) -> List[Hallazgo]:
    """Se documenta un parámetro que el procedimiento no tiene (mal escrito o eliminado)."""
    reales = {p.upper(): p for p in parametros_reales}
    propiedades = leer_propiedades_extendidas(texto_diccionario)
    # «¿Quiso decir…?» solo propone parámetros que aún no están documentados.
    documentados = {ll.texto("level2name").upper() for ll in propiedades if ll.texto("level2type")}
    sin_documentar = [clave for clave in reales if clave not in documentados]
    hallazgos = []
    for ll in propiedades:
        if not ll.texto("level2type"):
            continue
        nombre = ll.texto("level2name")
        if not nombre or nombre.upper() in reales:
            continue
        parecido = difflib.get_close_matches(nombre.upper(), sin_documentar, n=1, cutoff=0.75)
        sugerencia = f" (¿quiso decir '{reales[parecido[0]]}'?)" if parecido else ""
        hallazgos.append(con_elemento(_hallazgo_catalogo(
            ll.linea, "PARAMETRO_NO_EXISTE",
            f"Se verificó que el parámetro {nombre} está documentado, pero no existe en {actual().el} "
            f"{nombre_proc}{sugerencia}. Corregir el nombre del parámetro en el diccionario o retirar la sentencia, "
            f"ya que SQL Server no encuentra el parámetro y el script del diccionario falla.",
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
            de_objeto = f"del {objeto}"
        else:
            objeto = f"{actual().nombre} {_nombre_completo(esquema, nombre_proc)}"
            de_objeto = f"{actual().del_} {_nombre_completo(esquema, nombre_proc)}"
        hallazgos.append(con_elemento(_hallazgo_catalogo(
            ll.linea, "NOMBRE_PROPIEDAD_INCORRECTO",
            f"La propiedad {de_objeto} se registra como '{nombre}', por lo que no se reconocerá como "
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
            clave, objeto = ("objeto", nombre.upper()), f"{actual().nombre} {nombre}"
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
            mensaje=f"Se identificó que {'el' if objeto.startswith('parámetro') else actual().el.split()[0]} "
                    f"{objeto} se encuentra "
                    f"{'documentado' if objeto.startswith('parámetro') else actual().documentado} dos veces, "
                    f"siendo la primera "
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
        if "level2name" in args and args.get("level2type", ""):
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
                    f"documentado previamente al tratarse de una modificación {actual().del_} ({actual().alter}). "
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
                f"El parámetro {p} {actual().del_} {_nombre_completo(esquema, nombre_proc)} no se encuentra "
                f"documentado. Se recomienda añadirlo al "
                f"diccionario {actual().del_} con su descripción, ya que todo parámetro de "
                f"{actual().un_nuevo} debe estar documentado."
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
                f"Se detectó que {actual().el} {_nombre_completo(esquema, nombre_proc)} se modifica "
                f"({actual().alter}), pero no se adjuntó su diccionario. Incluir la documentación de los "
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
        if "level1name" in args and actual().tipo_sql in args.get("level1type", "").upper():
            valor = _limpiar_valor(args["level1name"])
            # Vacío (N'') no es «no coincide»: lo marca _validar_nombres_vacios.
            if valor and valor.lower() != nombre_proc.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="NOMBRE_NO_COINCIDE",
                    mensaje=f"El diccionario indica el nombre '{valor}', pero {actual().el} "
                            f"se llama '{nombre_proc}'. Corregir el nombre en el diccionario por "
                            f"'{nombre_proc}', ya que no coincide con el nombre {actual().del_} y "
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
            ("level0name", f"el esquema {actual().del_}", esquema or "dbo"),
            ("level1name", f"el nombre {actual().del_}", nombre_proc or actual().ejemplo_nombre),
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
            mensaje=f"Se comprobó que el diccionario {actual().del_} {_nombre_completo(esquema, nombre_proc)} "
                    f"está documentado, pero su descripción se encuentra vacía. Incluir la descripción respectiva "
                    f"que indique la finalidad {actual().del_}, para así contar con una documentación completa."
        )]

    if tipo_sentencia == "ALTER":
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="VALIDAR_DOCUMENTACION_ALTER",
            mensaje=f"El diccionario no incluye la descripción {actual().del_} "
                    f"{_nombre_completo(esquema, nombre_proc)}, aunque podría estar {actual().documentado} "
                    f"previamente al tratarse de una modificación ({actual().alter}). Verificar si ya cuenta con "
                    f"descripción en "
                    f"el diccionario y, de no tenerla, incluir la descripción respectiva."
        )]

    return [Hallazgo(
        linea=1,
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad.ALTO,
        regla="PROCEDIMIENTO_SIN_DESCRIPCION",
        mensaje=f"{actual().El} {_nombre_completo(esquema, nombre_proc)} no se encuentra "
                f"{actual().documentado}. Añadir la descripción {actual().del_} al diccionario, ya que "
                f"{actual().todo_nuevo} debe estar {actual().documentado}."
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
        if actual().tipo_sql not in args.get("level1type", "").upper() or "value" not in args:
            continue
        descripcion = _texto_de_valor(args["value"])
        if not descripcion.strip():
            continue
        if "PARAMETER" in args.get("level2type", "").upper():
            lugar = ("parámetro", _limpiar_valor(args.get("level2name", "?")))
        else:
            lugar = (actual().nombre, _nombre_completo(esquema, nombre_proc))
        objeto = (f"del {lugar[0]} {lugar[1]}" if lugar[0] == "parámetro"
                  else f"{actual().del_} {lugar[1]}")
        errores = palabras_mal_escritas(descripcion, nombres_objeto)
        if not errores:
            continue
        hallazgos.append(con_elemento(Hallazgo(
            # La línea es la del @value (donde está el texto con el error), no la del EXEC.
            linea=_numero_linea(texto_diccionario, _posicion_valor(texto_diccionario, pos)),
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="ERROR_ORTOGRAFICO",
            mensaje=redactar_error_ortografico(objeto, errores, actual().del_),
        ), elemento_ortografico(objeto, errores)))
        # Para juntar la misma palabra de varias descripciones en una sola línea (juntar_ortografia).
        hallazgos[-1].errores, hallazgos[-1].lugar = errores, lugar
    return hallazgos


def _validar_palabras_repetidas(
    llamadas: List[Tuple[int, Dict[str, str]]], texto_diccionario: str, esquema: str, nombre_proc: str
) -> List[Hallazgo]:
    """«…el repositorio de de RRHH…»: una sola observación con todas las del diccionario (usuaria, 11 nov.)."""
    descripciones = [
        (_numero_linea(texto_diccionario, _posicion_valor(texto_diccionario, pos)), _texto_de_valor(args["value"]))
        for pos, args in llamadas
        if actual().tipo_sql in args.get("level1type", "").upper() and "value" in args
    ]
    agrupado = palabra_repetida_agrupada(descripciones)
    if not agrupado:
        return []
    linea, mensaje, lineas = agrupado
    hallazgo = Hallazgo(
        linea=linea,
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS["PALABRA_REPETIDA"].severidad),
        regla="PALABRA_REPETIDA",
        mensaje=mensaje,
    )
    if len(lineas) > 1:
        hallazgo.lineas = lineas
    return [hallazgo]


def _validar_descripcion_vs_nombre(
    llamadas: List[Tuple[int, Dict[str, str]]], texto_diccionario: str
) -> List[Hallazgo]:
    """@nCodMonedaTotal descrito como «Monto total…»: la descripción y el nombre hablan de datos distintos."""
    hallazgos = []
    for pos, args in llamadas:
        if "PARAMETER" not in args.get("level2type", "").upper() or "value" not in args:
            continue
        parametro = _limpiar_valor(args.get("level2name", ""))
        distinto = contradice(parametro, _texto_de_valor(args["value"]))
        if not distinto:
            continue
        segun_descripcion, segun_nombre = distinto
        hallazgos.append(con_elemento(Hallazgo(
            linea=_numero_linea(texto_diccionario, _posicion_valor(texto_diccionario, pos)),
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="DESCRIPCION_NO_COINCIDE_CON_NOMBRE",
            mensaje=(
                f"La descripción del parámetro {parametro} habla de {segun_descripcion}, pero su nombre indica "
                f"{segun_nombre}. Se recomienda revisar la descripción o el nombre del parámetro, ya que deben "
                f"referirse al mismo dato."
            ),
        ), f"{parametro} (la descripción habla de {segun_descripcion} y el nombre indica {segun_nombre})"))
    return hallazgos


# ---------------------------------------------------------------------------
# ORQUESTADOR PRINCIPAL
# ---------------------------------------------------------------------------

# En qué cajita está la línea de cada observación (las demás son del script del diccionario).
# Las que nombran un parámetro pasan al CREATE/ALTER cuando se encuentra (ver ubicar).
_REGLAS_DEL_OBJETO = {
    "OBJETO_SIN_ESQUEMA", "PROCEDIMIENTO_SIN_PREFIJO_PA", "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
    "PROCEDIMIENTO_ACCION_SIN_SEPARAR", "PROCEDIMIENTO_ACCION_NO_ABREVIADA", "PROCEDIMIENTO_SIN_ACCION",
    "PROCEDIMIENTO_TABLA_SEPARADA",
}
_REGLAS_GENERALES = {
    "PROCEDIMIENTO_SIN_DESCRIPCION", "DESCRIPCION_PROCEDIMIENTO_VACIA", "VALIDAR_DOCUMENTACION_ALTER",
    "ALTER_SIN_DICCIONARIO", "PARAMETRO_FALTANTE",
}

# Reglas que, repetidas, se reportan una vez con la lista de elementos (según el objeto en revisión).
def _plantillas_agrupadas() -> Dict[str, Tuple[str, str]]:
    o = actual()
    return {
        "PARAMETRO_FALTANTE": (
            "parámetros sin documentar",
            f"Se recomienda añadir los parámetros faltantes al diccionario {o.del_}, cada uno "
            f"con su descripción, ya que todo parámetro de {o.un_nuevo} debe estar documentado.",
        ),
        "VALIDAR_DOCUMENTACION_ALTER": (
            "parámetros que no se encuentran en el diccionario",
            f"Verificar si ya cuentan con descripción en el diccionario, al tratarse de una modificación "
            f"{o.del_} ({o.alter}), y, de no tenerla, incluir la descripción respectiva de cada uno.",
        ),
        "DESCRIPCION_VACIA": (
            "parámetros con la descripción vacía",
            f"Completar la descripción indicando para qué se usa cada parámetro, de modo que quede claro para "
            f"quien consulte {o.el}.",
        ),
        "PARAMETRO_NO_EXISTE": (
            f"parámetros documentados que no existen en {o.el}",
            "Corregir el nombre de cada parámetro en el diccionario o retirar esas sentencias, ya que SQL Server "
            "no encuentra esos parámetros y el script del diccionario falla.",
        ),
        "PARAMETRO_NOMBRE_INCORRECTO": (
            f"parámetros documentados con un nombre que no existe en {o.el}",
            "Corregir el nombre de cada parámetro en el diccionario, ya que SQL Server no encuentra esos "
            "parámetros y el script del diccionario falla.",
        ),
        **_PLANTILLAS_COMUNES,
    }


# Las que no nombran al objeto.
_PLANTILLAS_COMUNES = {
    "ERROR_ORTOGRAFICO": (
        "descripciones con errores de escritura",
        ACCION_ORTOGRAFIA,
    ),
    "DESCRIPCION_NO_COINCIDE_CON_NOMBRE": (
        "parámetros cuya descripción no coincide con su nombre",
        "Se recomienda revisar la descripción o el nombre de cada parámetro, ya que deben referirse al mismo dato.",
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


def _nombre_del_encabezado(m: re.Match) -> str:
    return m.group(0).split(".")[-1].split()[-1].strip().strip("[]")


# Con una función, las reglas que nombran al procedimiento llevan su propio código (y su título en pantalla).
_CODIGOS_DE_FUNCION = {
    "PROCEDIMIENTO_SIN_DESCRIPCION": "FUNCION_SIN_DESCRIPCION",
    "DESCRIPCION_PROCEDIMIENTO_VACIA": "DESCRIPCION_FUNCION_VACIA",
    "PROCEDIMIENTO_DUPLICADO": "FUNCION_DUPLICADA",
    "PROCEDIMIENTO_FUERA_DEL_SCRIPT": "FUNCION_FUERA_DEL_SCRIPT",
    "NOMBRE_NO_COINCIDE": "NOMBRE_FUNCION_NO_COINCIDE",
}


def verificar_diccionario(
    texto_procedimiento: str,
    texto_diccionario: str,
    objeto: str = "procedimiento",
) -> List[Hallazgo]:
    """Diccionario de un procedimiento (por defecto) o de una función (objeto="funcion"): mismas reglas."""
    token = usar(POR_CLAVE.get(objeto, PROCEDIMIENTO))
    try:
        hallazgos = _verificar_diccionario(texto_procedimiento, texto_diccionario)
    finally:
        restaurar(token)
    if objeto == FUNCION.clave:
        for hallazgo in hallazgos:
            hallazgo.regla = _CODIGOS_DE_FUNCION.get(hallazgo.regla, hallazgo.regla)
    return hallazgos


def _verificar_diccionario(
    texto_procedimiento: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """
    Funcion principal: compara el procedimiento (realidad) contra el
    script del diccionario (documentacion) y devuelve los hallazgos.
    Con varios procedimientos en el script (por ejemplo, solo el encabezado
    de cada uno con sus parámetros), cada uno se revisa con su parte del
    diccionario y las observaciones se juntan por regla.
    """
    # Un procedimiento creado dos veces se avisa una vez y se revisa solo su primera copia.
    texto_procedimiento, repetidos = quitar_creaciones_repetidas(texto_procedimiento, actual().clave)
    duplicado = hallazgo_repetidos(
        repetidos, actual().clave, "PROCEDIMIENTO_DUPLICADO",
        REGLAS_DICCIONARIO_PROCEDIMIENTOS["PROCEDIMIENTO_DUPLICADO"].severidad, OrigenAnalisis.DICCIONARIO,
    )
    if duplicado:
        duplicado.seccion = "objeto"
    varios = por_objeto(texto_procedimiento, texto_diccionario, _encabezado(), _nombre_del_encabezado)
    if varios is None:
        # Si el diccionario documenta además otros procedimientos (que no vinieron en el script), se
        # revisa solo lo de este y los otros se avisan una vez como «procedimiento fuera del script».
        nombres = nombres_del_script(texto_procedimiento, _encabezado(), _nombre_del_encabezado)
        propio = sin_otros_objetos(texto_diccionario, nombres[0]) if len(nombres) == 1 else None
        hallazgos = agrupar(
            juntar_ortografia(_revisar_procedimiento(texto_procedimiento, propio or texto_diccionario),
                              ACCION_ORTOGRAFIA),
            _plantillas_agrupadas(),
        )
        if propio is not None:
            hallazgos += _procedimientos_fuera_del_script(texto_diccionario, nombres)
    else:
        hallazgos = []
        for nombre, texto, diccionario in varios:
            for hallazgo in _revisar_procedimiento(texto, diccionario):
                hallazgo.objeto = nombre
                hallazgos.append(hallazgo)
        hallazgos = agrupar_varios(juntar_ortografia(hallazgos, ACCION_ORTOGRAFIA), _plantillas_agrupadas(),
                                   actual().el)
        hallazgos += _procedimientos_fuera_del_script(
            texto_diccionario, nombres_del_script(texto_procedimiento, _encabezado(), _nombre_del_encabezado)
        )
    hallazgos += _documentacion_existente_en_alter(texto_procedimiento, texto_diccionario)
    return ([duplicado] if duplicado else []) + hallazgos


def _enumerar(elementos: List[str]) -> str:
    return elementos[0] if len(elementos) == 1 else f"{', '.join(elementos[:-1])} y {elementos[-1]}"


def _documentacion_existente_en_alter(texto_procedimiento: str, texto_diccionario: str) -> List[Hallazgo]:
    """
    En un ALTER PROCEDURE el procedimiento y sus parámetros ya existen: agregarles la descripción
    (sp_addextendedproperty) falla si ya estaban documentados. Igual que en el diccionario de tablas,
    se pide validar. Va en una sola observación para todo el script (CREATE OR ALTER cuenta como CREATE).
    """
    alterados: Dict[str, str] = {}
    o = actual()
    for encabezado in _encabezado().finditer(_sin_comentarios_ni_textos(texto_procedimiento)):
        if encabezado.group(1).upper() != "ALTER":
            continue
        esquema, nombre = extraer_esquema_y_nombre(encabezado.group(0))
        alterados.setdefault(nombre.upper(), _nombre_completo(esquema, nombre))

    por_procedimiento: Dict[str, Dict[str, list]] = {}
    lineas = set()
    for ll in leer_propiedades_extendidas(texto_diccionario):
        if ll.operacion != "add" or ll.texto("name").upper() != "MS_DESCRIPTION":
            continue
        nombre = alterados.get(ll.texto("level1name").upper())
        if not nombre or o.tipo_sql not in ll.texto("level1type").upper():
            continue
        partes = por_procedimiento.setdefault(nombre, {"procedimiento": [], "parametros": []})
        if "PARAMETER" in ll.texto("level2type").upper():
            if ll.texto("level2name") not in partes["parametros"]:
                partes["parametros"].append(ll.texto("level2name"))
        elif not ll.texto("level2type"):
            partes["procedimiento"].append(ll.linea)
        else:
            continue
        lineas.add(ll.linea)
    if not por_procedimiento:
        return []

    def detalle(partes: Dict[str, list]) -> str:
        """«el procedimiento y 12 parámetros»; con 1 o 2 parámetros se nombran: «el parámetro @cDoi»."""
        parametros = partes["parametros"]
        if len(parametros) > 2:
            de_parametros = f"{len(parametros)} parámetros"
        elif parametros:
            de_parametros = (f"el parámetro {parametros[0]}" if len(parametros) == 1
                             else f"los parámetros {_enumerar(parametros)}")
        else:
            return o.el
        return f"{o.el} y {de_parametros}" if partes["procedimiento"] else de_parametros

    accion = ("Verificar si ya cuentan con descripción en el diccionario, ya que de ser así la ejecución del "
              "script fallará. En ese caso, retirar esas sentencias o reemplazarlas por sentencias de "
              "actualización (sp_updateextendedproperty).")
    if len(lineas) == 1:
        accion = accion.replace("cuentan", "cuenta").replace("esas sentencias", "la sentencia").replace(
            "reemplazarlas por sentencias", "reemplazarla por una")
    if len(por_procedimiento) == 1:
        nombre, partes = next(iter(por_procedimiento.items()))
        if not partes["parametros"]:
            mensaje = (f"Se identificó que el diccionario agrega la descripción {o.del_} {nombre}, que ya "
                       f"existe (ALTER). {accion}")
        else:
            mensaje = (f"Se identificó que el diccionario agrega descripciones {o.al} {nombre}, que ya "
                       f"existe (ALTER): {detalle(partes)}. {accion}")
    else:
        casos = "; ".join(f"{nombre}: {detalle(partes)}" for nombre, partes in por_procedimiento.items())
        mensaje = (f"Se identificaron {len(por_procedimiento)} {o.plural} que ya existen (ALTER) a los que el "
                   f"diccionario agrega descripciones: {casos}. {accion}")
    orden = sorted(lineas)
    hallazgo = Hallazgo(
        linea=orden[0],
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS["DOCUMENTACION_EXISTENTE_EN_ALTER"].severidad),
        regla="DOCUMENTACION_EXISTENTE_EN_ALTER",
        mensaje=mensaje,
    )
    if len(orden) > 1:
        hallazgo.lineas = orden
    hallazgo.seccion = "diccionario"
    return [hallazgo]


def _procedimientos_fuera_del_script(texto_diccionario: str, nombres: List[str]) -> List[Hallazgo]:
    """El diccionario documenta procedimientos cuyo CREATE/ALTER no está en el script: se avisa una vez."""
    faltantes = objetos_sin_script(texto_diccionario, nombres)
    if not faltantes:
        return []
    lineas = sorted({linea for _, de_uno in faltantes for linea in de_uno})
    lista = "; ".join(nombre for nombre, _ in faltantes)
    unico = len(faltantes) == 1
    o = actual()
    hallazgo = Hallazgo(
        linea=lineas[0],
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_PROCEDIMIENTOS["PROCEDIMIENTO_FUERA_DEL_SCRIPT"].severidad),
        regla="PROCEDIMIENTO_FUERA_DEL_SCRIPT",
        mensaje=(
            f"Se identificó documentación {o.del_} {lista}, que no está en el script de los {o.plural}. "
            if unico else
            f"Se identificaron {len(faltantes)} {o.plural} {'documentados' if o is PROCEDIMIENTO else 'documentadas'} "
            f"que no están en el script de los {o.plural}: {lista}. "
        ) + (
            f"Se recomienda adjuntar el {o.create} de {o.ese if unico else ('cada uno' if o is PROCEDIMIENTO else 'cada una')} para "
            f"revisar su documentación, o retirar esas sentencias si no corresponden a este pase."
        ),
    )
    hallazgo.lineas = lineas
    hallazgo.seccion = "diccionario"
    return [hallazgo]


def diccionario_por_procedimiento(texto_procedimiento: str, texto_diccionario: str, objeto: str = "procedimiento"):
    """[(texto del objeto, su diccionario)] — una sola entrada si el script tiene uno."""
    token = usar(POR_CLAVE.get(objeto, PROCEDIMIENTO))
    try:
        texto_procedimiento, _ = quitar_creaciones_repetidas(texto_procedimiento, actual().clave)
        varios = por_objeto(texto_procedimiento, texto_diccionario, _encabezado(), _nombre_del_encabezado)
    finally:
        restaurar(token)
    return [(texto_procedimiento, texto_diccionario)] if varios is None else [(t, d) for _, t, d in varios]


def _revisar_procedimiento(texto_procedimiento: str, texto_diccionario: str) -> List[Hallazgo]:
    """Observaciones (sin agrupar) de un procedimiento y su diccionario."""
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
        asignar_secciones(hallazgos, _REGLAS_DEL_OBJETO, _REGLAS_GENERALES)
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
    hallazgos = _emparejar_parametros(hallazgos, texto_diccionario, esquema, nombre_proc)
    hallazgos = solo_un_error_por_sentencia(hallazgos, {"PARAMETRO_NO_EXISTE", "PARAMETRO_NOMBRE_INCORRECTO"})
    hallazgos += _validar_nombre_propiedad(texto_diccionario, esquema, nombre_proc)
    hallazgos += _validar_ortografia(llamadas, texto_diccionario, esquema, nombre_proc, parametros_reales)
    hallazgos += _validar_palabras_repetidas(llamadas, texto_diccionario, esquema, nombre_proc)
    hallazgos += _validar_descripcion_vs_nombre(llamadas, texto_diccionario)
    if REGLAS_DICCIONARIO_PROCEDIMIENTOS["VALOR_SIN_COMILLAS"].activo:
        hallazgos += _validar_valores_sin_comillas(llamadas, texto_diccionario)

    # Los parámetros se ubican en su línea del CREATE/ALTER.
    for hallazgo in hallazgos:
        if getattr(hallazgo, "elemento", None) and hallazgo.regla not in ("DESCRIPCION_VACIA", "NOMBRE_PROPIEDAD_INCORRECTO", "PALABRA_REPETIDA"):
            ubicar(hallazgo, texto_procedimiento)
    asignar_secciones(hallazgos, _REGLAS_DEL_OBJETO, _REGLAS_GENERALES)
    return hallazgos