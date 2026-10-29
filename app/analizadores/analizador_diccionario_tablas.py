# -*- coding: utf-8 -*-
"""
analizador_diccionario_tablas.py
------------------------------
Analiza el diccionario de tablas (sp_addextendedproperty) y compara la
"realidad" (CREATE/ALTER TABLE) contra la "documentacion".

El script del diccionario se lee con propiedades_extendidas, por lo que las
sentencias pueden separarse con GO, con ";", con ambos o sin nada.
"""

import difflib
import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple

from app.analizadores.diccionario_agrupar import agrupar, asignar_secciones, con_elemento, ubicar
from app.analizadores.diccionario_nomenclatura import nomenclatura_tabla
from app.analizadores.diccionario_varios import agrupar_varios, nombres_del_script, objetos_sin_script, por_objeto
from app.analizadores.objetos_repetidos import hallazgo_repetidos, quitar_creaciones_repetidas
from app.analizadores.ortografia import (
    ACCION_ORTOGRAFIA, elemento_ortografico, palabras_mal_escritas, redactar_error_ortografico,
)
from app.analizadores.propiedades_extendidas import (
    LlamadaPropiedad,
    como_llamadas_crudas,
    descripcion_mal_escrita,
    leer_propiedades_extendidas,
)
from app.modelos.hallazgo import Hallazgo, Severidad, OrigenAnalisis
from app.reglas.reglas_diccionario_tablas import REGLAS_DICCIONARIO_TABLAS


_IDENTIFICADOR_SQL = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#@]*)"


def _limpiar_identificador_sql(valor: str) -> str:
    """Quita los corchetes de un identificador SQL Server."""
    if valor.startswith("[") and valor.endswith("]"):
        return valor[1:-1]
    return valor


def _nombre_completo(esquema: Optional[str], nombre: str) -> str:
    """Devuelve 'esquema.nombre' si esquema existe, sino solo 'nombre'."""
    return f"{esquema}.{nombre}" if esquema else nombre


_COMENTARIOS_SQL = re.compile(r"--[^\r\n]*|/\*.*?\*/", re.DOTALL)
_PALABRAS_NO_COLUMNA = {
    "CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY",
    "ALTER", "ADD", "DROP", "PERIOD", "DEFAULT",
}


def _sin_comentarios(texto_sql: str) -> str:
    return _COMENTARIOS_SQL.sub(" ", texto_sql or "")


def _separar_por_comas(contenido: str) -> List[str]:
    """Divide por comas de primer nivel (respeta paréntesis y cadenas)."""
    segmentos, actual, profundidad, en_cadena = [], [], 0, False
    for ch in contenido:
        if ch == "'":
            en_cadena = not en_cadena
        elif not en_cadena:
            if ch == "(":
                profundidad += 1
            elif ch == ")":
                profundidad = max(profundidad - 1, 0)
            elif ch == "," and profundidad == 0:
                segmentos.append("".join(actual))
                actual = []
                continue
        actual.append(ch)
    if actual:
        segmentos.append("".join(actual))
    return segmentos


def _primera_columna(segmento: str) -> Optional[str]:
    """Nombre de columna al inicio de una definición, o None si es una restricción."""
    coincidencia = re.match(rf"\s*({_IDENTIFICADOR_SQL})", segmento)
    if not coincidencia:
        return None
    nombre = _limpiar_identificador_sql(coincidencia.group(1))
    return None if nombre.upper() in _PALABRAS_NO_COLUMNA else nombre


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "realidad" (la tabla)
# ---------------------------------------------------------------------------

def extraer_tipo_sentencia(texto_sql: str) -> str:
    """
    CREATE si el script crea la tabla (aunque luego tenga ALTER TABLE para
    agregar restricciones); ALTER si solo la modifica.
    """
    texto = _sin_comentarios(texto_sql)
    if re.search(r"\bCREATE\s+TABLE\b", texto, re.IGNORECASE):
        return "CREATE"
    if re.search(r"\bALTER\s+TABLE\b", texto, re.IGNORECASE):
        return "ALTER"
    return "DESCONOCIDO"


def extraer_esquema_y_nombre(texto_sql: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) de la tabla (prioriza el CREATE), o (None, None)."""
    texto = _sin_comentarios(texto_sql)
    for verbo in ("CREATE", "ALTER"):
        # Hasta tres partes (Base.Esquema.Tabla): la tabla es la última y el esquema la anterior.
        m = re.search(
            rf"\b{verbo}\s+TABLE\s+({_IDENTIFICADOR_SQL}(?:\s*\.\s*{_IDENTIFICADOR_SQL}){{0,2}})",
            texto,
            re.IGNORECASE,
        )
        if m:
            partes = [_limpiar_identificador_sql(p.strip()) for p in re.findall(_IDENTIFICADOR_SQL, m.group(1))]
            return (partes[-2] if len(partes) > 1 else None), partes[-1]
    return None, None


def _columnas_create(texto: str) -> Set[str]:
    """Columnas definidas entre los paréntesis del CREATE TABLE."""
    m = re.search(
        rf"\bCREATE\s+TABLE\s+{_IDENTIFICADOR_SQL}(?:\s*\.\s*{_IDENTIFICADOR_SQL}){{0,2}}\s*\(",
        texto,
        re.IGNORECASE,
    )
    if not m:
        return set()
    inicio, profundidad, fin = m.end(), 0, len(texto)
    for i in range(inicio, len(texto)):
        if texto[i] == "(":
            profundidad += 1
        elif texto[i] == ")":
            if profundidad == 0:
                fin = i
                break
            profundidad -= 1
    columnas = (_primera_columna(s) for s in _separar_por_comas(texto[inicio:fin]))
    return {c for c in columnas if c}


def extraer_columnas_alter(texto_sql: str) -> Tuple[Set[str], Set[str]]:
    """
    Columnas de los ALTER TABLE del script: (agregadas con ADD, modificadas
    con ALTER COLUMN). ADD admite varias columnas separadas por comas y
    descarta ADD CONSTRAINT / PRIMARY KEY / etc.
    """
    texto = _sin_comentarios(texto_sql)
    agregadas: Set[str] = set()
    modificadas: Set[str] = set()
    sentencias = re.finditer(
        r"\bALTER\s+TABLE\b(.*?)(?=;|\bGO\b|\bALTER\s+TABLE\b|\bCREATE\b|\Z)",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    for sentencia in sentencias:
        cuerpo = sentencia.group(1)
        m_alter = re.search(rf"\bALTER\s+COLUMN\s+({_IDENTIFICADOR_SQL})", cuerpo, re.IGNORECASE)
        if m_alter:
            modificadas.add(_limpiar_identificador_sql(m_alter.group(1)))
            continue
        m_add = re.search(r"\bADD\b(?:\s+COLUMN\b)?", cuerpo, re.IGNORECASE)
        if m_add:
            for segmento in _separar_por_comas(cuerpo[m_add.end():]):
                columna = _primera_columna(segmento)
                if columna:
                    agregadas.add(columna)
    return agregadas, modificadas


def extraer_columnas(texto_sql: str) -> Set[str]:
    """
    Columnas que el script crea o modifica: las del CREATE TABLE más las
    agregadas o modificadas en ALTER TABLE.
    """
    texto = _sin_comentarios(texto_sql)
    agregadas, modificadas = extraer_columnas_alter(texto)
    return _columnas_create(texto) | agregadas | modificadas


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "documentacion" (diccionario)
# ---------------------------------------------------------------------------

_PARAMETROS_OBLIGATORIOS = ("name", "value", "level0type", "level0name", "level1type", "level1name")
_PARAMETROS_DE_NOMBRE = ("level0name", "level1name", "level2name")


def extraer_llamadas_extendedproperty(texto_diccionario: str) -> List[Tuple[int, Dict[str, str]]]:
    """Compatibilidad: llamadas como [(posicion, {parametro: valor_crudo})]."""
    return como_llamadas_crudas(leer_propiedades_extendidas(texto_diccionario))


def _es_descripcion(llamada: LlamadaPropiedad) -> bool:
    """Solo las propiedades MS_Description son descripciones del diccionario."""
    nombre = llamada.texto("name")
    return nombre == "" or nombre.upper() == "MS_DESCRIPTION"


def _es_de_tabla(llamada: LlamadaPropiedad) -> bool:
    return llamada.texto("level1type").upper() == "TABLE" and not llamada.tiene("level2type")


def _es_de_columna(llamada: LlamadaPropiedad) -> bool:
    return llamada.texto("level2type").upper() == "COLUMN" and bool(llamada.texto("level2name"))


def _normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes ni espacios repetidos: para comparar descripciones."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def _hallazgo(linea: int, regla: str, mensaje: str) -> Hallazgo:
    """Crea el hallazgo con la severidad definida en el catálogo de reglas."""
    return Hallazgo(
        linea=linea,
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_TABLAS[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )


# ---------------------------------------------------------------------------
# VALIDACIONES
# ---------------------------------------------------------------------------

def _validar_sintaxis(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """Errores de escritura del script: SQL Server no lo podría ejecutar."""
    return [
        _hallazgo(linea, "SINTAXIS_DICCIONARIO", mensaje)
        for llamada in llamadas
        for linea, mensaje in llamada.errores
    ]


def _validar_parametros(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """Cada sentencia debe traer los parámetros obligatorios y niveles válidos."""
    hallazgos = []
    for llamada in llamadas:
        faltantes = [f"@{p}" for p in _PARAMETROS_OBLIGATORIOS if not llamada.tiene(p)]
        if llamada.tiene("level2type") != llamada.tiene("level2name"):
            faltantes.append("@level2name" if llamada.tiene("level2type") else "@level2type")
        if faltantes:
            hallazgos.append(_hallazgo(
                llamada.linea, "PARAMETROS_INCOMPLETOS",
                f"Se comprobó que a la sentencia le faltan datos obligatorios: {', '.join(faltantes)}. Completar "
                f"los datos faltantes, ya que sin ellos la sentencia no se ejecuta.",
            ))

        tipo0 = llamada.texto("level0type").upper()
        tipo1 = llamada.texto("level1type").upper()
        if tipo0 and tipo0 != "SCHEMA":
            hallazgos.append(_hallazgo(
                llamada.linea, "TIPO_NIVEL_INCORRECTO",
                f"La sentencia indica '{llamada.texto('level0type')}' como tipo del esquema, pero debe ser "
                f"'SCHEMA'. Usar el tipo «N'SCHEMA'», ya que con otro tipo la sentencia falla.",
            ))
        if tipo1 and tipo1 != "TABLE":
            hallazgos.append(_hallazgo(
                llamada.linea, "TIPO_NIVEL_INCORRECTO",
                f"La sentencia indica el tipo de objeto '{llamada.texto('level1type')}', pero lo que se "
                f"documenta es una tabla. Usar el tipo «N'TABLE'», ya que con otro tipo la sentencia falla.",
            ))
    return hallazgos


def _validar_tabla_documentada(
    llamadas: List[LlamadaPropiedad], esquema: Optional[str], nombre_tabla: str
) -> List[Hallazgo]:
    """La propia tabla debe tener su descripción (sentencia sin @level2type) y no vacía."""
    sentencias_tabla = [
        ll for ll in llamadas
        if _es_de_tabla(ll) and _es_descripcion(ll)
        and ll.texto("level1name").upper() == nombre_tabla.upper()
    ]
    if any(ll.texto("value") for ll in sentencias_tabla):
        return []
    full = _nombre_completo(esquema, nombre_tabla)
    if sentencias_tabla:
        return [_hallazgo(
            sentencias_tabla[0].linea, "DESCRIPCION_TABLA_VACIA",
            f"Se identificó que el diccionario de la tabla {full} está documentado, pero su descripción "
            f"se encuentra vacía. Incluir la descripción respectiva que indique la finalidad de la tabla, "
            f"para así contar con una documentación completa.",
        )]
    return [_hallazgo(
        1, "TABLA_SIN_DESCRIPCION",
        f"La tabla {full} no se encuentra documentada. Añadir la descripción de la tabla al "
        f"diccionario, ya que toda tabla nueva debe estar documentada.",
    )]


def _linea_tabla(texto_tabla: str) -> int:
    """Línea del CREATE o ALTER TABLE: ahí van los hallazgos del nombre de la tabla."""
    m = re.search(r"\b(?:CREATE|ALTER)\s+TABLE\b", _sin_comentarios(texto_tabla), re.IGNORECASE)
    return texto_tabla.count("\n", 0, m.start()) + 1 if m else 1


def _validar_esquema_declarado(texto_tabla: str, esquema: Optional[str], nombre_tabla: str) -> List[Hallazgo]:
    """La tabla indica su esquema en el CREATE o ALTER."""
    if esquema:
        return []
    return [_hallazgo(
        _linea_tabla(texto_tabla), "OBJETO_SIN_ESQUEMA",
        f"La tabla {nombre_tabla} no indica su esquema. Anteponer el esquema al nombre, ya que así se "
        f"evita crear o modificar la tabla en un esquema equivocado y el diccionario puede "
        f"documentarla correctamente (ej.: dbo.{nombre_tabla}).",
    )]


def _validar_esquema(llamadas: List[LlamadaPropiedad], esquema_real: Optional[str]) -> List[Hallazgo]:
    # Si la tabla no declara esquema en el SQL, no hay contra qué comparar.
    if not esquema_real:
        return []
    return [
        _hallazgo(
            ll.linea, "ESQUEMA_NO_COINCIDE",
            f"El diccionario indica el esquema '{ll.texto('level0name')}', pero la tabla está en "
            f"'{esquema_real}'. Corregir el esquema en el diccionario por '{esquema_real}', ya que "
            f"no coincide con el esquema de la tabla y la documentación quedaría en un objeto que "
            f"no existe.",
        )
        for ll in llamadas
        if ll.texto("level0name") and ll.texto("level0name").lower() != esquema_real.lower()
    ]


def _validar_nombres_vacios(
    llamadas: List[LlamadaPropiedad], esquema: Optional[str], nombre_tabla: str, texto_diccionario: str
) -> List[Hallazgo]:
    """@level0name, @level1name o @level2name vacíos (N''): el diccionario no indica el objeto."""
    hallazgos = []
    for ll in llamadas:
        for clave, que, ejemplo in (
            ("level0name", "el esquema de la tabla", esquema or "dbo"),
            ("level1name", "el nombre de la tabla", nombre_tabla or "Tabla"),
            ("level2name", "el nombre de la columna", "cColumna"),
        ):
            if ll.tiene(clave) and ll.texto(clave) == "":
                # La línea es la del parámetro vacío, no la del inicio del EXEC.
                donde = re.compile(r"@" + clave + r"\s*=", re.IGNORECASE).search(texto_diccionario, ll.posicion)
                linea = texto_diccionario.count("\n", 0, donde.start()) + 1 if donde else ll.linea
                hallazgos.append(_hallazgo(
                    linea, "NOMBRE_VACIO",
                    f"La sentencia no indica {que}. Colocar {que} (ej.: «@{clave}=N'{ejemplo}'»), "
                    f"ya que sin él la descripción no quedará asociada a ningún objeto.",
                ))
    return hallazgos


def _validar_nombre_tabla(llamadas: List[LlamadaPropiedad], nombre_tabla: str) -> List[Hallazgo]:
    return [
        _hallazgo(
            ll.linea, "NOMBRE_TABLA_NO_COINCIDE",
            f"El diccionario indica el nombre '{ll.texto('level1name')}', pero la tabla se llama "
            f"'{nombre_tabla}'. Corregir el nombre en el diccionario por '{nombre_tabla}', ya que "
            f"no coincide con el nombre de la tabla y la documentación quedaría en un objeto que "
            f"no existe.",
        )
        for ll in llamadas
        if ll.texto("level1type").upper() == "TABLE"
        and ll.texto("level1name")
        and ll.texto("level1name").upper() != nombre_tabla.upper()
    ]


def _columnas_documentadas(llamadas: List[LlamadaPropiedad]) -> Set[str]:
    return {
        ll.texto("level2name").upper()
        for ll in llamadas
        if _es_de_columna(ll) and _es_descripcion(ll)
    }


def _validar_columnas_faltantes(
    columnas_reales: Set[str],
    llamadas: List[LlamadaPropiedad],
    tipo_sentencia: str,
    esquema: Optional[str],
    nombre_tabla: str,
) -> List[Hallazgo]:
    """
    Recibe las columnas que deben documentarse: en un CREATE, todas; en un
    ALTER, solo las nuevas (ADD).
    """
    documentadas = _columnas_documentadas(llamadas)
    # Una sola entrada por columna (sin distinguir mayúsculas), con su nombre original.
    reales = {c.upper(): c for c in sorted(columnas_reales)}
    hallazgos = []
    for clave in sorted(set(reales) - documentadas):
        columna = reales[clave]
        if tipo_sentencia == "ALTER":
            mensaje = (
                f"La columna {columna} se agrega en el ALTER TABLE, pero no se encuentra documentada. "
                f"Se recomienda añadirla al diccionario de la tabla con su descripción, ya que toda "
                f"columna nueva debe estar documentada."
            )
        else:
            mensaje = (
                f"La columna {columna} no se encuentra documentada. Se recomienda añadirla al "
                f"diccionario de la tabla con su descripción, ya que toda columna nueva debe estar "
                f"documentada."
            )
        hallazgos.append(con_elemento(_hallazgo(1, "COLUMNA_FALTANTE", mensaje), columna))
    return hallazgos


def _validar_documentacion_existente_en_alter(
    llamadas: List[LlamadaPropiedad],
    tipo_sentencia: str,
    esquema: Optional[str],
    nombre_tabla: str,
    columnas_agregadas: Set[str],
) -> List[Hallazgo]:
    """
    En un ALTER la tabla (y sus columnas previas) ya existen y seguramente ya
    están documentadas. Agregarles de nuevo la descripción no es un error del
    diccionario, pero sp_addextendedproperty fallaría si ya la tienen: se
    pide validar.
    """
    if tipo_sentencia != "ALTER":
        return []
    nuevas = {c.upper() for c in columnas_agregadas}
    full = _nombre_completo(esquema, nombre_tabla)
    hallazgos = []
    for ll in llamadas:
        if ll.operacion != "add" or not _es_descripcion(ll):
            continue
        if _es_de_tabla(ll):
            objeto = f"tabla {full}"
        elif _es_de_columna(ll) and ll.texto("level2name").upper() not in nuevas:
            objeto = f"columna {ll.texto('level2name')}"
        else:
            continue
        hallazgos.append(con_elemento(_hallazgo(
            ll.linea, "DOCUMENTACION_EXISTENTE_EN_ALTER",
            f"El diccionario agrega la descripción de la {objeto}, la cual ya existe y podría estar "
            f"documentada. Verificar si ya cuenta con descripción en el diccionario, ya que de ser así la "
            f"ejecución del script fallará. En ese caso, retirar la sentencia o reemplazarla por una de "
            f"actualización (sp_updateextendedproperty).",
        ), objeto))
    return hallazgos


def _validar_actualizacion_sin_descripcion_previa(
    llamadas: List[LlamadaPropiedad],
    tipo_sentencia: str,
    esquema: Optional[str],
    nombre_tabla: str,
    columnas_agregadas: Set[str],
) -> List[Hallazgo]:
    """
    sp_updateextendedproperty solo modifica una descripción que ya existe: sobre
    una tabla nueva (CREATE) o una columna nueva (CREATE o ADD) la ejecución falla.
    En un ALTER COLUMN o al completar el diccionario de una tabla existente es lo correcto.
    """
    es_create = tipo_sentencia == "CREATE"
    nuevas = {c.upper() for c in columnas_agregadas}
    hallazgos = []
    for ll in llamadas:
        if ll.operacion != "update" or not _es_descripcion(ll):
            continue
        if _es_de_tabla(ll) and es_create:
            objeto = f"tabla {_nombre_completo(esquema, nombre_tabla)}"
        elif _es_de_columna(ll) and (es_create or ll.texto("level2name").upper() in nuevas):
            objeto = f"columna {ll.texto('level2name')}"
        else:
            continue
        hallazgos.append(con_elemento(_hallazgo(
            ll.linea, "ACTUALIZACION_SIN_DESCRIPCION_PREVIA",
            f"Se detectó que la {objeto} se documenta con sp_updateextendedproperty, pero es nueva y aún "
            f"no cuenta con una descripción. Emplear sp_addextendedproperty en su lugar, ya que la "
            f"actualización fallará al no existir la propiedad.",
        ), objeto))
    return hallazgos


def _sugerencia_columna(nombre: str, columnas_reales: Set[str]) -> str:
    """' (¿quiso decir 'bActivo'?)' si hay una columna real con nombre parecido."""
    por_clave = {c.upper(): c for c in columnas_reales}
    parecidas = difflib.get_close_matches(nombre.upper(), list(por_clave), n=1, cutoff=0.75)
    if parecidas:
        return f" (¿quiso decir '{por_clave[parecidas[0]]}'?)"
    return ""


def _validar_columnas_inexistentes(
    columnas_reales: Set[str], llamadas: List[LlamadaPropiedad], tipo_sentencia: str, nombre_tabla: str
) -> List[Hallazgo]:
    """
    En un CREATE, documentar una columna que no existe suele ser un error de
    tipeo. En un ALTER no se valida: la tabla tiene columnas previas que el
    script no muestra.
    """
    if tipo_sentencia != "CREATE":
        return []
    reales = {c.upper() for c in columnas_reales}
    return [
        con_elemento(_hallazgo(
            ll.linea, "COLUMNA_NO_EXISTE",
            f"Se verificó que la columna {ll.texto('level2name')} está documentada, pero no existe en la "
            f"tabla {nombre_tabla}{_sugerencia_columna(ll.texto('level2name'), columnas_reales)}. Corregir el "
            f"nombre de la columna en el diccionario o retirar la sentencia, ya que SQL Server no la ejecutará.",
        ), ll.texto('level2name'))
        for ll in llamadas
        if _es_de_columna(ll) and ll.texto("level2name").upper() not in reales
    ]


def _validar_duplicados(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """
    Agregar dos veces la misma descripción falla en SQL Server ("property
    already exists"). Solo aplica a sp_addextendedproperty.
    """
    vistos: Dict[Tuple[str, str], int] = {}
    hallazgos = []
    for ll in llamadas:
        if ll.operacion != "add" or not _es_descripcion(ll):
            continue
        if _es_de_columna(ll):
            clave = ("columna", ll.texto("level2name").upper())
            objeto = f"la columna {ll.texto('level2name')}"
        elif _es_de_tabla(ll):
            clave = ("tabla", ll.texto("level1name").upper())
            objeto = f"la tabla {ll.texto('level1name')}"
        else:
            continue
        if clave in vistos:
            hallazgos.append(con_elemento(_hallazgo(
                ll.linea, "DOCUMENTACION_DUPLICADA",
                f"Se identificó que {objeto} se encuentra documentada dos veces, siendo la primera "
                f"declaración en la línea {vistos[clave]}. Se recomienda retirar una de las declaraciones "
                f"duplicadas, ya que SQL Server genera un error al intentar registrar nuevamente la misma "
                f"propiedad.",
            ), f"{objeto.split(' ', 1)[1]} (primera declaración en la línea {vistos[clave]})"))
        else:
            vistos[clave] = ll.linea
    return hallazgos


def _validar_descripcion_tabla(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """
    La descripción de la tabla debe explicar su propósito. Se marca cuando es
    idéntica a la de una columna (copiar y pegar) o cuando describe un
    identificador en lugar de la tabla.
    """
    descripciones_columnas = {
        _normalizar_texto(ll.texto("value")): ll.texto("level2name")
        for ll in llamadas
        if _es_de_columna(ll) and _es_descripcion(ll) and ll.texto("value")
    }
    hallazgos = []
    for ll in llamadas:
        if not (_es_de_tabla(ll) and _es_descripcion(ll) and ll.texto("value")):
            continue
        descripcion = _normalizar_texto(ll.texto("value"))
        if descripcion in descripciones_columnas:
            hallazgos.append(_hallazgo(
                ll.linea, "DESCRIPCION_TABLA_INADECUADA",
                f"La descripción de la tabla es la misma que la de la columna "
                f"{descripciones_columnas[descripcion]}. Se recomienda escribir una descripción que "
                f"explique para qué sirve la tabla.",
            ))
        elif descripcion.startswith("identificador"):
            hallazgos.append(_hallazgo(
                ll.linea, "DESCRIPCION_TABLA_INADECUADA",
                "La descripción de la tabla parece de una columna (empieza con 'Identificador'). Se "
                "recomienda describir para qué sirve la tabla.",
            ))
    return hallazgos


def _validar_nombre_propiedad(llamadas: List[LlamadaPropiedad], esquema: Optional[str], nombre_tabla: str) -> List[Hallazgo]:
    """
    @name parecido a MS_Description pero mal escrito: la descripción se guarda,
    pero no se reconoce como la del diccionario.
    """
    hallazgos = []
    for ll in llamadas:
        nombre = ll.texto("name")
        if not descripcion_mal_escrita(nombre):
            continue
        if _es_de_columna(ll):
            objeto = f"columna {ll.texto('level2name')}"
        elif _es_de_tabla(ll):
            objeto = f"tabla {_nombre_completo(esquema, nombre_tabla)}"
        else:
            continue
        hallazgos.append(con_elemento(_hallazgo(
            ll.linea, "NOMBRE_PROPIEDAD_INCORRECTO",
            f"La propiedad de la {objeto} se registra como '{nombre}', por lo que no se reconocerá como su "
            f"descripción. Usar «N'MS_Description'» como nombre de la propiedad, ya que es el nombre estándar "
            f"de las descripciones del diccionario.",
        ), f"{objeto} ('{nombre}')"))
    return hallazgos


def _enumerar_columnas(nombres: List[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _validar_descripciones_repetidas(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """
    Varias columnas con la misma descripción: suele ser copiar y pegar, y así no
    se distingue qué guarda cada una. La misma columna repetida la marca
    DOCUMENTACION_DUPLICADA.
    """
    grupos: Dict[str, List[LlamadaPropiedad]] = {}
    for ll in llamadas:
        if _es_de_columna(ll) and _es_descripcion(ll) and ll.texto("value").strip():
            grupos.setdefault(_normalizar_texto(ll.texto("value")), []).append(ll)
    hallazgos = []
    for grupo in grupos.values():
        columnas = list(dict.fromkeys(ll.texto("level2name") for ll in grupo))
        columnas = list({c.upper(): c for c in columnas}.values())
        if len(columnas) < 2:
            continue
        hallazgos.append(_hallazgo(
            grupo[1].linea, "DESCRIPCION_REPETIDA",
            f"Las columnas {_enumerar_columnas(columnas)} tienen la misma descripción: "
            f"'{grupo[0].texto('value')}'. Diferenciar la descripción de cada columna según el dato que "
            f"almacena, ya que una descripción repetida no permite distinguirlas.",
        ))
    return hallazgos


def _linea_valor(ll: LlamadaPropiedad, texto_diccionario: str) -> int:
    """Línea del @value de la llamada (donde está el texto revisado), no la del EXEC."""
    valor = re.compile(r"@value\s*=", re.IGNORECASE).search(texto_diccionario, ll.posicion)
    return texto_diccionario.count("\n", 0, valor.start()) + 1 if valor else ll.linea


def _validar_ortografia(
    llamadas: List[LlamadaPropiedad],
    esquema: Optional[str],
    nombre_tabla: str,
    columnas_reales: Set[str],
    texto_diccionario: str = "",
) -> List[Hallazgo]:
    """Palabras mal escritas en las descripciones (sin exigir tildes)."""
    nombres_objeto = {esquema or "", nombre_tabla, *columnas_reales}
    hallazgos = []
    for ll in llamadas:
        if not (_es_descripcion(ll) and ll.texto("value")):
            continue
        if _es_de_columna(ll):
            objeto = f"de la columna {ll.texto('level2name')}"
        elif _es_de_tabla(ll):
            objeto = f"de la tabla {_nombre_completo(esquema, nombre_tabla)}"
        else:
            continue
        errores = palabras_mal_escritas(ll.texto("value"), nombres_objeto | {ll.texto("level2name")})
        if not errores:
            continue
        hallazgos.append(con_elemento(_hallazgo(
            _linea_valor(ll, texto_diccionario), "ERROR_ORTOGRAFICO",
            redactar_error_ortografico(objeto, errores, "de la tabla"),
        ), elemento_ortografico(objeto, errores)))
    return hallazgos


def _validar_descripciones_vacias(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    return [
        con_elemento(_hallazgo(
            ll.linea, "DESCRIPCION_COLUMNA_VACIA",
            f"La columna {ll.texto('level2name')} figura en el diccionario, pero no cuenta con una "
            f"descripción. Completar la descripción indicando el dato que almacena la "
            f"columna, de modo que su uso quede claro para quien consulte la tabla.",
        ), ll.texto('level2name'))
        for ll in llamadas
        if _es_de_columna(ll) and _es_descripcion(ll) and ll.tiene("value") and ll.texto("value") == ""
    ]


def _validar_valores_sin_comillas(llamadas: List[LlamadaPropiedad]) -> List[Hallazgo]:
    """Estándar del equipo: los nombres van como N'...'. Un hallazgo por sentencia."""
    hallazgos = []
    for ll in llamadas:
        sin_comillas = [
            ll.argumentos[p].crudo
            for p in _PARAMETROS_DE_NOMBRE
            if ll.tiene(p) and not ll.argumentos[p].entre_comillas
        ]
        if sin_comillas:
            varios = len(sin_comillas) > 1
            hallazgos.append(_hallazgo(
                ll.linea, "VALOR_SIN_COMILLAS",
                f"Se detectó que {'los nombres' if varios else 'el nombre'} {', '.join(sin_comillas)} "
                f"{'no están' if varios else 'no está'} entre comillas. Colocar{'los' if varios else 'lo'} entre "
                f"comillas simples con la N delante (ej.: «N'{sin_comillas[0]}'»), ya que sin ellas la sentencia "
                f"no se ejecuta.",
            ))
    return hallazgos


# Lo que puede ir después de ADD sin ser una columna nueva.
_ADD_SIN_COLUMNA = {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "DEFAULT", "INDEX", "PERIOD"}


def _alter_solo_restricciones(texto_tabla: str) -> bool:
    """
    True si todos los ALTER TABLE del script solo agregan o quitan restricciones (ADD CONSTRAINT PK_...,
    DROP CONSTRAINT, WITH CHECK...) o quitan columnas: no hay columnas nuevas ni modificadas que documentar.
    """
    texto = _sin_comentarios(texto_tabla or "")
    cuerpos = [
        m.group(1) for m in re.finditer(
            r"\bALTER\s+TABLE\s+\S+(.*?)(?=;|\bGO\b|\bALTER\s+TABLE\b|\bCREATE\b|\bCOMMIT\b|\bEND\b|\Z)",
            texto, re.IGNORECASE | re.DOTALL,
        )
    ]
    if not cuerpos:
        return False
    for cuerpo in cuerpos:
        accion = re.match(r"\s*(?:WITH\s+(?:NO)?CHECK\s+)?(\w+)(?:\s+(\w+))?", cuerpo)
        if not accion:
            return False
        verbo, siguiente = accion.group(1).upper(), (accion.group(2) or "").upper()
        if verbo == "ADD" and siguiente not in _ADD_SIN_COLUMNA:
            return False  # ADD de una columna
        if verbo == "ALTER":
            return False  # ALTER COLUMN
        if verbo not in {"ADD", "DROP", "CHECK", "NOCHECK", "ENABLE", "DISABLE", "SET", "REBUILD", "SWITCH"}:
            return False
    return True


def _validar_alter_sin_diccionario(
    tipo_sentencia: str,
    llamadas: List[LlamadaPropiedad],
    esquema: Optional[str],
    nombre_tabla: str,
    columnas_alter: Set[str],
    texto_tabla: str = "",
) -> List[Hallazgo]:
    """
    Aviso general solo si el ALTER no tiene ADD ni ALTER COLUMN reconocibles:
    esas columnas ya tienen su propia observación. Un ALTER que solo agrega o quita
    restricciones (PK, FK, DEFAULT, CHECK...) o quita columnas no cambia lo que se documenta.
    """
    if _alter_solo_restricciones(texto_tabla):
        return []
    if tipo_sentencia == "ALTER" and not llamadas and not columnas_alter:
        full = _nombre_completo(esquema, nombre_tabla)
        return [_hallazgo(
            1, "ALTER_SIN_DICCIONARIO",
            f"Se detectó que la tabla {full} se modifica (ALTER TABLE), pero no se adjuntó su diccionario. "
            f"Incluir la documentación de las columnas que se agreguen o modifiquen, para mantener el "
            f"diccionario actualizado.",
        )]
    return []


def _validar_columnas_modificadas(
    llamadas: List[LlamadaPropiedad], tipo_sentencia: str, columnas_modificadas: Set[str]
) -> List[Hallazgo]:
    """
    ALTER COLUMN: la columna ya existía y puede estar documentada de antes.
    No es error que no venga en el diccionario; se pide validar.
    """
    if tipo_sentencia != "ALTER":
        return []
    documentadas = _columnas_documentadas(llamadas)
    return [
        con_elemento(_hallazgo(
            1, "VALIDAR_COLUMNA_MODIFICADA",
            f"La columna {columna} se modifica (ALTER COLUMN) y no se encuentra en el "
            f"diccionario, aunque podría estar documentada previamente. Verificar si ya cuenta con "
            f"descripción en el diccionario y, de no tenerla, incluir la descripción respectiva.",
        ), columna)
        for columna in sorted(columnas_modificadas, key=str.upper)
        if columna.upper() not in documentadas
    ]


# ---------------------------------------------------------------------------
# ORQUESTADOR
# ---------------------------------------------------------------------------

# En qué cajita está la línea de cada observación (las demás son del script del diccionario).
# COLUMNA_FALTANTE pasa al CREATE/ALTER cuando se encuentra la columna (ver ubicar).
_REGLAS_DEL_OBJETO = {"OBJETO_SIN_ESQUEMA", "TABLA_NOMBRE_NO_ESTANDAR"}
_REGLAS_GENERALES = {"TABLA_SIN_DESCRIPCION", "ALTER_SIN_DICCIONARIO", "VALIDAR_COLUMNA_MODIFICADA", "COLUMNA_FALTANTE"}

# Reglas que, repetidas, se reportan una vez con la lista de elementos.
_PLANTILLAS_AGRUPADAS = {
    "COLUMNA_FALTANTE": (
        "columnas sin documentar",
        "Se recomienda añadir las columnas faltantes al diccionario de la tabla, cada una con su "
        "descripción, ya que toda columna nueva debe estar documentada.",
    ),
    "DESCRIPCION_COLUMNA_VACIA": (
        "columnas con la descripción vacía",
        "Completar la descripción indicando el dato que almacena cada columna, de modo que su uso quede "
        "claro para quien consulte la tabla.",
    ),
    "COLUMNA_NO_EXISTE": (
        "columnas documentadas que no existen en la tabla",
        "Corregir el nombre de cada columna en el diccionario o retirar esas sentencias, ya que SQL Server no "
        "las ejecutará.",
    ),
    "ERROR_ORTOGRAFICO": (
        "descripciones con errores de escritura",
        ACCION_ORTOGRAFIA,
    ),
    "DOCUMENTACION_EXISTENTE_EN_ALTER": (
        "descripciones que se agregan a objetos que ya existen",
        "Verificar si ya cuentan con descripción en el diccionario, ya que de ser así la ejecución del script "
        "fallará. En ese caso, retirar esas sentencias o reemplazarlas por sentencias de actualización "
        "(sp_updateextendedproperty).",
    ),
    "VALIDAR_COLUMNA_MODIFICADA": (
        "columnas modificadas que no se encuentran en el diccionario",
        "Verificar si ya cuentan con descripción en el diccionario, al tratarse de columnas existentes "
        "(ALTER COLUMN), y, de no tenerla, incluir la descripción respectiva de cada una.",
    ),
    "ACTUALIZACION_SIN_DESCRIPCION_PREVIA": (
        "actualizaciones sin descripción previa",
        "Emplear sp_addextendedproperty en esas sentencias, ya que la actualización fallará al no "
        "existir la propiedad.",
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


# Encabezado de cada tabla del script (CREATE/ALTER TABLE Esquema.Tabla).
_ENCABEZADO_TABLA = re.compile(
    rf"\b(?:CREATE|ALTER)\s+TABLE\s+({_IDENTIFICADOR_SQL}(?:\s*\.\s*{_IDENTIFICADOR_SQL}){{0,2}})",
    re.IGNORECASE,
)


def _nombre_del_encabezado(m: re.Match) -> str:
    return _limpiar_identificador_sql(re.findall(_IDENTIFICADOR_SQL, m.group(1))[-1])


def verificar_diccionario_tablas(texto_tabla: str, texto_diccionario: str) -> List[Hallazgo]:
    """
    Compara CREATE/ALTER TABLE con el diccionario de datos. Con varias tablas en el script,
    cada una se revisa con su parte del diccionario y las observaciones se juntan por regla.
    """
    # Una tabla creada dos veces se avisa una vez y se revisa solo su primera copia.
    texto_tabla, repetidas = quitar_creaciones_repetidas(texto_tabla, "tabla")
    duplicada = hallazgo_repetidos(
        repetidas, "tabla", "TABLA_DUPLICADA", REGLAS_DICCIONARIO_TABLAS["TABLA_DUPLICADA"].severidad,
        OrigenAnalisis.DICCIONARIO,
    )
    if duplicada:
        duplicada.seccion = "objeto"
    varias = por_objeto(texto_tabla, texto_diccionario, _ENCABEZADO_TABLA, _nombre_del_encabezado)
    if varias is None:
        hallazgos = agrupar(_revisar_tabla(texto_tabla, texto_diccionario), _PLANTILLAS_AGRUPADAS)
    else:
        hallazgos = []
        for nombre, texto, diccionario in varias:
            for hallazgo in _revisar_tabla(texto, diccionario):
                hallazgo.objeto = nombre
                hallazgos.append(hallazgo)
        hallazgos = agrupar_varios(hallazgos, _PLANTILLAS_AGRUPADAS, "la tabla")
        hallazgos += _tablas_fuera_del_script(
            texto_diccionario, nombres_del_script(texto_tabla, _ENCABEZADO_TABLA, _nombre_del_encabezado)
        )
    return ([duplicada] if duplicada else []) + hallazgos


def _tablas_fuera_del_script(texto_diccionario: str, nombres: List[str]) -> List[Hallazgo]:
    """El diccionario documenta tablas cuyo CREATE/ALTER no está en el script: se avisa una vez."""
    faltantes = objetos_sin_script(texto_diccionario, nombres)
    if not faltantes:
        return []
    lineas = sorted({linea for _, de_una in faltantes for linea in de_una})
    lista = "; ".join(nombre for nombre, _ in faltantes)
    unica = len(faltantes) == 1
    hallazgo = Hallazgo(
        linea=lineas[0],
        origen=OrigenAnalisis.DICCIONARIO,
        severidad=Severidad(REGLAS_DICCIONARIO_TABLAS["TABLA_FUERA_DEL_SCRIPT"].severidad),
        regla="TABLA_FUERA_DEL_SCRIPT",
        mensaje=(
            f"Se identificó documentación de la tabla {lista}, que no está en el script de las tablas. "
            if unica else
            f"Se identificaron {len(faltantes)} tablas documentadas que no están en el script de las tablas: {lista}. "
        ) + (
            f"Se recomienda adjuntar el CREATE TABLE de {'esa tabla' if unica else 'cada una'} para revisar su "
            f"documentación, o retirar esas sentencias si no corresponden a este pase."
        ),
    )
    hallazgo.lineas = lineas
    hallazgo.seccion = "diccionario"
    return [hallazgo]


def diccionario_por_tabla(texto_tabla: str, texto_diccionario: str):
    """[(texto de la tabla, su diccionario)] — una sola entrada si el script tiene una tabla."""
    texto_tabla, _ = quitar_creaciones_repetidas(texto_tabla, "tabla")
    varias = por_objeto(texto_tabla, texto_diccionario, _ENCABEZADO_TABLA, _nombre_del_encabezado)
    return [(texto_tabla, texto_diccionario)] if varias is None else [(t, d) for _, t, d in varias]


def _revisar_tabla(texto_tabla: str, texto_diccionario: str) -> List[Hallazgo]:
    """Observaciones (sin agrupar) de una tabla y su diccionario."""
    esquema, nombre_tabla = extraer_esquema_y_nombre(texto_tabla)
    if nombre_tabla is None:
        return []

    tipo_sentencia = extraer_tipo_sentencia(texto_tabla)
    columnas_reales = extraer_columnas(texto_tabla)
    columnas_agregadas, columnas_modificadas = extraer_columnas_alter(texto_tabla)
    llamadas = leer_propiedades_extendidas(texto_diccionario)

    # CREATE: la tabla es nueva y todo debe documentarse.
    # ALTER: la tabla ya existe; solo se exigen las columnas nuevas (ADD).
    es_create = tipo_sentencia == "CREATE"
    columnas_requeridas = columnas_reales if es_create else columnas_agregadas

    hallazgos: List[Hallazgo] = []
    hallazgos += _validar_sintaxis(llamadas)
    hallazgos += _validar_parametros(llamadas)
    hallazgos += _validar_alter_sin_diccionario(
        tipo_sentencia, llamadas, esquema, nombre_tabla, columnas_agregadas | columnas_modificadas, texto_tabla
    )
    hallazgos += _validar_columnas_modificadas(llamadas, tipo_sentencia, columnas_modificadas)
    if es_create:
        hallazgos += _validar_tabla_documentada(llamadas, esquema, nombre_tabla)
    hallazgos += _validar_descripcion_tabla(llamadas)
    hallazgos += _validar_columnas_faltantes(columnas_requeridas, llamadas, tipo_sentencia, esquema, nombre_tabla)
    hallazgos += _validar_columnas_inexistentes(columnas_reales, llamadas, tipo_sentencia, nombre_tabla)
    hallazgos += _validar_documentacion_existente_en_alter(
        llamadas, tipo_sentencia, esquema, nombre_tabla, columnas_agregadas
    )
    hallazgos += _validar_actualizacion_sin_descripcion_previa(
        llamadas, tipo_sentencia, esquema, nombre_tabla, columnas_agregadas
    )
    hallazgos += _validar_duplicados(llamadas)
    hallazgos += _validar_esquema_declarado(texto_tabla, esquema, nombre_tabla)
    if tipo_sentencia == "CREATE":
        # Al crear la tabla se revisa su nombre; en un ALTER solo el esquema.
        hallazgos += [
            _hallazgo(_linea_tabla(texto_tabla), regla, mensaje)
            for regla, mensaje in nomenclatura_tabla(nombre_tabla)
        ]
    hallazgos += _validar_esquema(llamadas, esquema)
    vacios = _validar_nombres_vacios(llamadas, esquema, nombre_tabla, texto_diccionario)
    hallazgos += vacios
    # Si la descripción de la tabla tiene @level1name vacío, la tabla sí se documentó (con el
    # nombre vacío): no se marca además como «tabla sin descripción».
    if any("@level1name" in h.mensaje for h in vacios):
        hallazgos = [h for h in hallazgos if h.regla != "TABLA_SIN_DESCRIPCION"]
    hallazgos += _validar_nombre_tabla(llamadas, nombre_tabla)
    hallazgos += _validar_descripciones_vacias(llamadas)
    hallazgos += _validar_ortografia(llamadas, esquema, nombre_tabla, columnas_reales, texto_diccionario)
    hallazgos += _validar_valores_sin_comillas(llamadas)
    hallazgos += _validar_descripciones_repetidas(llamadas)

    # Propiedad con el nombre mal escrito: sí se documentó, así que no se marca
    # además como «no documentada»; basta con la observación del nombre.
    mal_escritas = _validar_nombre_propiedad(llamadas, esquema, nombre_tabla)
    if mal_escritas:
        objetos = {h.elemento.split(" (")[0].upper() for h in mal_escritas}
        hallazgos = [
            h for h in hallazgos
            if not (h.regla in ("COLUMNA_FALTANTE", "VALIDAR_COLUMNA_MODIFICADA")
                    and f"COLUMNA {getattr(h, 'elemento', '')}".upper() in objetos)
            and not (h.regla == "TABLA_SIN_DESCRIPCION" and any(o.startswith("TABLA ") for o in objetos))
        ]
        hallazgos += mal_escritas

    # Las reglas desactivadas en el catálogo no se reportan.
    # Las columnas faltantes se ubican en su línea del CREATE/ALTER.
    for hallazgo in hallazgos:
        if hallazgo.regla == "COLUMNA_FALTANTE" and getattr(hallazgo, "elemento", None):
            ubicar(hallazgo, texto_tabla)
    asignar_secciones(hallazgos, _REGLAS_DEL_OBJETO, _REGLAS_GENERALES)
    return [h for h in hallazgos if REGLAS_DICCIONARIO_TABLAS[h.regla].activo]
