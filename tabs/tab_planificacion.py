import pandas as pd
import streamlit as st
from duckdb.experimental.spark.sql.functions import hour

import database
import logic
import reduccion_plan
from config import config
from logic import ahora
import time

class PlanificacionTab:
    def __init__(self, df):
        self.df = df

    def render_configurar_plan(self):
        with st.expander("📈 CONFIGURAR PLAN DE REDUCCIÓN"):
            c1, c2, c3 = st.columns(3)

            # Control para la cantidad inicial
            c1.number_input(
                "Cantidad Inicial (ml/día)",
                value=float(config.get("ml_iniciales_plan", 15.0)),
                step=0.5,
                key = "cantidad_inicial"
            )

            # Control para la reducción diaria
            c2.number_input(
                "Reducción Diaria (ml)",
                value=float(config.get("reduccion_diaria", 1)),
                step=0.05,
                format="%.2f",
                key = "reduccion_diaria"
            )

            # Control para la dosis por defecto

            c3.number_input(
                "Dosis Defecto (ml)",
                value= float(config.get("dosis_media", 3.2)),
                step=0.1,
                key = "dosis_media"
            )

            c1, c2, c3 = st.columns(3)

            if c1.button("💾 GUARDAR CONFIGURACIÓN DEL PLAN"):
                logic.mlAcumulados()
                reduccion_plan.replanificar(
                    st.session_state.get("dosis_media"),
                    st.session_state.get("reduccion_diaria"),
                    st.session_state.get("cantidad_inicial"),
                    logic.mlAcumulados())
                st.success("Configuración del plan guardada.")
                st.cache_data.clear()
                st.rerun()
            if config.get("fecha_inicio_plan") and c2.button("💾 REINICIAR PLAN / BALANCE A 0"):
               database.save_config({
                    "fecha_inicio_plan": ahora.isoformat(),
                    "checkpoint_ml": 0.0,
                    "checkpoint_fecha": ahora.isoformat()
               })
               st.cache_data.clear()
               st.rerun()
            if c3.button("💾 CREAR PLAN"):
                reduccion_plan.crear_nuevo_plan(
                    st.session_state.get("dosis_media"),
                    st.session_state.get("reduccion_diaria"),
                    st.session_state.get("cantidad_inicial"),
                    logic.mlAcumulados())
                # logic.crear_plan(self.df,config)
                st.cache_data.clear()
                st.rerun()

    def render(self):
        st.header("📅 Planificación de Reducción")
        self.render_configurar_plan()
        self.render_tabla_plan()

    def render_tabla_plan(self):
        if config.get("fecha_inicio_plan"):
            df_seg = reduccion_plan.obtener_datos_tabla()
            st.dataframe(
                df_seg.style.apply(
                    lambda r: ['background-color: rgba(255, 75, 75, 0.1)'] * len(r) if r['Fecha'] == ahora.strftime(
                        '%d/%m/%Y') else [''] * len(r), axis=1
                ).format({"Objetivo (ml)": "{:.2f}", "Real (ml)": "{:.2f}", "Reducción Plan": "{:.2f}"}),
                width='stretch', hide_index=True
            )
        else:
            st.warning("No se ha definido plan")
