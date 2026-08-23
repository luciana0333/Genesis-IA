import streamlit as st
from typing import Any, Dict

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas


st.set_page_config(page_title="Genesis Auditor - Diccionario", layout="wide")

st.title("Genesis Auditor — Diccionario de Datos")

col1, col2 = st.columns([1, 2])

with col1:
    tipo = st.selectbox("Tipo de objeto", ["TABLA", "PROCEDIMIENTO"], index=0)
    nombre_obj = st.text_input("Nombre del objeto (opcional)")
    run = st.button("Analizar")

with col2:
    st.subheader("SQL del objeto")
    sql_input = st.text_area("SQL", height=220, placeholder="Pegue aquí el CREATE/ALTER o el body del procedimiento...")
    st.subheader("Script del diccionario (sp_addextendedproperty)")
    dict_input = st.text_area("Diccionario", height=220, placeholder="Pegue aquí el script que contiene sp_addextendedproperty...")

if run:
    if not sql_input.strip() or not dict_input.strip():
        st.error("Debe proveer el SQL del objeto y el script del diccionario.")
    else:
        with st.spinner("Analizando..."):
            try:
                if tipo == "PROCEDIMIENTO":
                    hallazgos = verificar_diccionario(sql_input, dict_input)
                else:
                    hallazgos = verificar_diccionario_tablas(sql_input, dict_input)

                if not hallazgos:
                    st.success("No se encontraron hallazgos.")
                else:
                    rows = []
                    for h in hallazgos:
                        rows.append({
                            "linea": h.linea,
                            "origen": h.origen.value,
                            "severidad": h.severidad.value.name,
                            "regla": h.regla,
                            "mensaje": h.mensaje,
                        })
                    st.table(rows)
            except Exception as e:
                st.exception(e)
