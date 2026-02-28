import streamlit as st
import pandas as pd
import database
import logic
import reduccion
import reduccion_por_tiempo
from state import invalidate_config
class PlanificacionTiempoTab:
    def render(self):
        if st.session_state.config.get("plan.fecha_inicio_plan"):
            df_seg = reduccion_por_tiempo.obtener_tabla()
            df_seg['Fecha'] = df_seg['Fecha'].dt.strftime('%d/%m/%Y')
            st.dataframe(
                df_seg.style.apply(
                    lambda r: ['background-color: rgba(255, 75, 75, 0.1)'] * len(r) if r['Fecha'] == pd.Timestamp.now(tz='Europe/Madrid').strftime(
                        '%d/%m/%Y') else [''] * len(r), axis=1
                ).format({"Objetivo (ml)": "{:.2f}", "Real (ml)": "{:.2f}", "Reducción Plan": "{:.2f}"}),
                width='stretch', hide_index=True
            )
        else:
            st.warning("No se ha definido plan")
