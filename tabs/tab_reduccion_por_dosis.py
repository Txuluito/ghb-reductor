import streamlit as st
import pandas as pd
import reduccion_por_dosis

class PlanificacionDosisTab:
    def render(self):
        if not st.session_state.config.get("plan_fijo_start_date"):
            st.info("Configura el plan para comenzar.")
            return

        df_plan = reduccion_por_dosis.obtener_tabla()

        if df_plan.empty:
            st.warning("No hay datos para mostrar.")
            return

        # Formatear la fecha para visualización si es necesario
        df_plan['Fecha_Display'] = df_plan['Fecha'].dt.strftime("%d/%m/%Y")

        # Resaltar fila de hoy
        hoy_str = pd.Timestamp.now(tz='Europe/Madrid').ahora.strftime("%d/%m/%Y")

        def highlight_row(row):
            if row["Fecha"].strftime("%d/%m/%Y") == hoy_str:
                return ['background-color: rgba(255, 255, 0, 0.1)'] * len(row)
            return [''] * len(row)

        # Ocultar la columna Fecha original si solo queremos mostrar la formateada, o usar la formateada
        st.dataframe(
            df_plan.style.format({
                "Dosis Obj (ml)": "{:.3f}",
                "Objetivo (ml)": "{:.2f}",
                "Real (ml)": "{:.2f}"
            }).apply(highlight_row, axis=1),
            use_container_width=True,
            hide_index=True,
            height=500
        )
