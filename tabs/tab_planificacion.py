import streamlit as st
import logic
from logic import ahora
import time

class PlanificacionTab:
    def __init__(self, df,config):
        self.df = df
        self.config = config
        self.plan = logic.ReductionPlan(self.df, self.config)

    def render_configurar_plan(self):
        with st.expander("📈 CONFIGURAR PLAN DE REDUCCIÓN"):
            c1, c2, c3, c4 = st.columns(4)

            # Control para la fecha de inicio del plan
            new_start_date = c1.date_input(
                "Fecha de Inicio",
                value=self.plan.plan_start_dt.date()
            )

            # Control para la cantidad inicial
            new_start_amount = c2.number_input(
                "Cantidad Inicial (ml/día)",
                value=self.plan.ml_iniciales_plan,
                step=0.5
            )

            # Control para la reducción diaria
            new_rate = c3.number_input(
                "Reducción Diaria (ml)",
                value=self.plan.ml_reduccion_diaria,
                step=0.05,
                format="%.2f"
            )

            # Control para la dosis por defecto
            new_dosis = c4.number_input(
                "Dosis Defecto (ml)",
                value=self.plan.ml_dosis_plan,
                step=0.1
            )
            if st.button("💾 GUARDAR CONFIGURACIÓN DEL PLAN"):
                logic.save_config({
                    "plan_start_date": new_start_date.isoformat(),  # Guardamos la nueva fecha
                    "plan_start_amount": new_start_amount,
                    "reduction_rate": new_rate,
                    "dosis": new_dosis
                })
                st.success("Configuración del plan guardada.")
                time.sleep(1)
                st.rerun()
            if self.config.get("plan_start_date") and st.button("💾 REINICIAR PLAN / BALANCE A 0"):
                logic.save_config({
                    "plan_start_date": ahora.isoformat(),
                    "checkpoint_ingresos": 0.0,
                    "checkpoint_fecha": ahora.isoformat()
                })
                st.rerun()
            if st.button("💾 CREAR PLAN"):
                logic.save_config({
                    "plan_start_date": ahora.isoformat(),
                    "checkpoint_ingresos": 0.0,
                    "checkpoint_fecha": ahora.isoformat()
                })
                logic.crear_plan(self.df,self.config)
                st.rerun()

    def render(self):
        st.header("📅 Planificación de Reducción")
        self.render_configurar_plan()
        self.render_tabla_plan()

    def render_tabla_plan(self):
        if self.config.get("plan_start_date"):
            col_h1, col_h2 = st.columns([3, 1])
            mostrar_futuro = col_h2.checkbox("Ver futuro", value=False)
            df_seg = logic.obtener_plan(self.df, self.config)
            if not mostrar_futuro:
                df_seg = df_seg[df_seg['Estado'] != "🔮 Futuro"]

            st.dataframe(
                df_seg.style.apply(
                    lambda r: ['background-color: rgba(255, 75, 75, 0.1)'] * len(r) if r['Fecha'] == ahora.strftime(
                        '%d/%m/%Y') else [''] * len(r), axis=1
                ).format({"Objetivo (ml)": "{:.2f}", "Real (ml)": "{:.2f}", "Reducción Plan": "{:.2f}"}),
                width='stretch', hide_index=True
            )
        else:
            st.warning("No se ha definido plan")
