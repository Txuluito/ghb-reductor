import streamlit as st
import database
import logic
from logic import ahora
import time

class TomaTab:
    def __init__(self, df,config):
        self.df = df
        self.config = config
        self.plan = logic.ReductionPlan(self.df, self.config)

    def mostrar_registro(self):
        with st.expander("➕ REGISTRAR TOMA", expanded=False):
            c1, c2, c3 = st.columns(3)
            cant = c1.number_input("Dosis Consumida (ml):", 0.1, 10.0, self.plan.ml_dosis_plan, help="Introduce la cantidad exacta que has consumido en esta toma.")
            f_sel = c2.date_input("Fecha:", ahora.date())
            h_sel = c3.time_input("Hora:", ahora.time())

            if st.button("🚀 ENVIAR REGISTRO", use_container_width=True):
                logic.save_config({
                    "checkpoint_ingresos": self.plan.checkpoint_ingresos + self.plan.ingresos_tramo,
                    "checkpoint_fecha": ahora.isoformat(),
                    "dosis": cant
                })
                try:
                    res = database.enviar_toma_api(f_sel.strftime('%d/%m/%Y'), h_sel.strftime('%H:%M:%S'), cant, self.plan.saldo - cant)
                    if res.status_code == 200:
                        st.success("Registrado")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    def mostrar_metricas(self):
        ultima_toma = self.df['timestamp'].max() if not self.df.empty else ahora
        pasado_mins = (ahora - ultima_toma).total_seconds() / 60
        tasa_gen = self.plan.objetivo_actual / 24.0

        mins_espera = ((self.plan.ml_dosis_plan - self.plan.saldo) / tasa_gen * 60) if self.plan.saldo < self.plan.ml_dosis_plan and tasa_gen > 0 else 0
        int_teorico = int((self.plan.ml_dosis_plan / tasa_gen) * 60) if tasa_gen > 0 else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Dosis", f"{self.plan.ml_dosis_plan:.2f} ml")
        m2.metric("Última hace", f"{int(pasado_mins // 60)}h {int(pasado_mins % 60)}m")
        m3.metric("Intervalo", f"{int_teorico // 60}h {int_teorico % 60}m")

        if mins_espera > 0:
            m4.metric("Siguiente en", f"{int(mins_espera // 60)}h {int(mins_espera % 60)}m", delta="Esperando", delta_color="inverse")
        else:
            m4.metric("Siguiente", "¡LISTO!", delta="Disponible")

        m5.metric("Saldo", f"{self.plan.saldo:.2f} ml", delta_color="normal" if self.plan.saldo >= 0 else "inverse")
