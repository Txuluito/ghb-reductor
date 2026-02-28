import streamlit as st
import pandas as pd
import reduccion_por_dosis

class PlanificacionDosisTab:
    def render(self):
        if not st.session_state.config.get("plan.fecha_inicio_plan"):
            st.info("Configura el plan para comenzar.")
            return
        df_plan = reduccion_por_dosis.obtener_tabla()
        df_plan['Fecha'] = df_plan['Fecha'].dt.strftime('%d/%m/%Y')

        def highlight_row(row):
            if row["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%d/%m/%Y'):
                return ['background-color: rgba(255, 255, 0, 0.1)'] * len(row)
            return [''] * len(row)

        # Ocultar la columna Fecha original si solo queremos mostrar la formateada, o usar la formateada

        # Asegurarse de que las columnas son numéricas antes de formatearlas
        cols_to_numeric = ["Objetivo (ml)", "Real (ml)"]
        if "Dosis" in df_plan.columns:
            cols_to_numeric.append("Dosis")

        for col in cols_to_numeric:
            if col in df_plan.columns:
                df_plan[col] = pd.to_numeric(df_plan[col], errors='coerce')

        # Verificar que la columna "Dosis" exista antes de formatearla
        format_dict = {
            "Objetivo (ml)": "{:.2f}",
            "Real (ml)": "{:.2f}"
        }
        if "Dosis" in df_plan.columns:
            format_dict["Dosis"] = "{:.2f}"

        st.dataframe(
            df_plan.style.format(format_dict).apply(highlight_row, axis=1),
            width='stretch',
            hide_index=True
        )
