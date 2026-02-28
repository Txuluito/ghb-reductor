import streamlit as st
import pandas as pd
import database
import reduccion
import reduccion_por_dosis
import logic
import time
from datetime import datetime

from state import invalidate_config


class ReduccionTab:
    def render(self):
        c1, c2, c3, c4 = st.columns(4)

        c1.number_input("Consumo diario actual (ml/día)", value=float(st.session_state.config.get("plan.ml_dia", 15.0)),
                        step=0.5, key="ml_dia_actual")
        c2.number_input("Intervalo en horas actual (horas)", value=float(st.session_state.config.get("dosis.intervalo_horas", 2.0)),
                        min_value=0.5, max_value=24.0, step=0.25, key="intervalo_dia_actual")
        c3.number_input("Dosis por toma actual (ml)", value=float(st.session_state.config.get("tiempos.ml_dosis", 3.2)), step=0.1,
                        key="ml_dosis_actual")
        c4.number_input("Reducción Diaria deseada (ml)",
                        value=float(st.session_state.config.get("plan.reduccion_diaria", 1)), step=0.05,
                        format="%.2f", key="reduccion_diaria")

        c1, c2 = st.columns(2)

        if c1.button("💾 ACTUALIZAR PLAN"):
            reduccion.replanificar(
                st.session_state.get("ml_dia_actual"),
                st.session_state.get("ml_dosis_actual"),
                st.session_state.get("intervalo_dia_actual"),
                st.session_state.get("reduccion_diaria"))
            st.success("Configuración del plan guardada.")
            invalidate_config()
            st.cache_data.clear()
            st.rerun()
        if c2.button("💾 NUEVO PLAN"):
            reduccion.crear_nuevo_plan(
                st.session_state.get("ml_dia_actual"),
                st.session_state.get("ml_dosis_actual"),
                st.session_state.get("intervalo_dia_actual"),
                st.session_state.get("reduccion_diaria"))
            st.success("Configuración del plan guardada.")
            invalidate_config()
            st.cache_data.clear()
            st.rerun()
