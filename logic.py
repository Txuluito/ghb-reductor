from typing import Any

import logic
import pandas as pd
import numpy as np

from pandas import DataFrame, DatetimeIndex

import database
import streamlit as st

# Usamos caché para no llamar a Google Sheets en cada interacción (TTL = 10 minutos)
ahora = pd.Timestamp.now(tz='Europe/Madrid')

def get_cached_config():
    return database.get_config()

class ReductionPlan:
    """
    Encapsula la lógica y el estado del plan de reducción.
    """
    def __init__(self, df, config):
        self.df = df
        self.config = config
        self._calculate_state()

    def _calculate_state(self):
        """
        Calcula el estado actual del plan basado en la configuración y los datos.
        """
        self.ml_dosis_plan = float(self.config.get("dosis", 3.2))
        self.ml_reduccion_diaria = float(self.config.get("reduction_rate", 0.5))
        self.ml_iniciales_plan = float(self.config.get("plan_start_amount", 15.0))
        plan_start_str = self.config.get("plan_start_date")
        if plan_start_str:
            fecha_inicio_plan_dt = pd.to_datetime(plan_start_str)
            if fecha_inicio_plan_dt.tz is None:
                fecha_inicio_plan_dt = fecha_inicio_plan_dt.tz_localize('Europe/Madrid')
            else:
                fecha_inicio_plan_dt = fecha_inicio_plan_dt.tz_convert('Europe/Madrid')
        else:
            fecha_inicio_plan_dt = ahora
            save_config({
                "plan_start_date": ahora.isoformat(),
                "checkpoint_ingresos": 0.0,
                "checkpoint_fecha": ahora.isoformat()
            })
        self.plan_start_dt = fecha_inicio_plan_dt

        self.checkpoint_ingresos = float(self.config.get("checkpoint_ingresos", 0.0))
        checkpoint_fecha_str = self.config.get("checkpoint_fecha", None)
        checkpoint_fecha = pd.to_datetime(checkpoint_fecha_str) if checkpoint_fecha_str else self.plan_start_dt
        if checkpoint_fecha.tz is None:
            checkpoint_fecha = checkpoint_fecha.tz_localize('Europe/Madrid')

        horas_desde_inicio = (ahora - self.plan_start_dt).total_seconds() / 3600
        dias_flotantes = max(0.0, horas_desde_inicio / 24.0)

        def integral(t_h):
            if t_h < 0: return (self.ml_iniciales_plan / 24.0) * t_h
            t_fin = (self.ml_iniciales_plan / self.ml_reduccion_diaria) * 24 if self.ml_reduccion_diaria > 0 else 999999
            t_eff = min(t_h, t_fin)
            return (self.ml_iniciales_plan / 24.0) * t_eff - (self.ml_reduccion_diaria / 1152.0) * (t_eff ** 2)

        self.ingresos_tramo = integral(horas_desde_inicio) - integral((checkpoint_fecha - self.plan_start_dt).total_seconds() / 3600)

        consumo_total = self.df[self.df['timestamp'] >= self.plan_start_dt]['ml'].sum()
        self.saldo = (self.checkpoint_ingresos + self.ingresos_tramo) - consumo_total
        self.objetivo_actual = max(0.0, self.ml_iniciales_plan - (self.ml_reduccion_diaria * dias_flotantes))



def load_config():
    # Cargamos la configuración desde la caché
    return get_cached_config()

def save_config(data):
    # Guardamos la configuración en Google Sheets
    database.save_config(data)
    # Limpiamos la caché para que la próxima vez se descargue la nueva configuración
    st.cache_data.clear()

def calcular_resumen_bloques(df):
    df_b = df.copy()
    df_b['horas_atras'] = (ahora - df_b['timestamp']).dt.total_seconds() / 3600
    df_b['bloque_n'] = np.floor(df_b['horas_atras'] / 24).astype(int)

    resumen = df_b.groupby('bloque_n').agg(
        total_ml=('ml', 'sum'),
        media_ml=('ml', 'mean'),
        num_tomas=('ml', 'count')
    ).sort_index()
    return resumen

def crear_plan(df, config):
    hoy = ahora.date()
    save_config({"plan_start_date": hoy.strftime('%Y-%m-%d')})
    config['plan_start_date'] = hoy.strftime('%Y-%m-%d')

    df_result = create_tabla_reduccion(df,{},hoy,config)
    database.save_plan_history_data(df_result)
    return df_result


def obtener_plan(df, config):
    # 1. Cargar parámetros del plan
    raw_start = config.get("plan_start_date")
    df_hist = database.get_plan_history_data()

    # Asegurar tipos numéricos
    if 'Objetivo (ml)' in df_hist.columns:
        df_hist['Objetivo (ml)'] = pd.to_numeric(df_hist['Objetivo (ml)'], errors='coerce').fillna(0)
    if 'Reducción Plan' in df_hist.columns:
        df_hist['Reducción Plan'] = pd.to_numeric(df_hist['Reducción Plan'], errors='coerce').fillna(0)

    # Convertimos a diccionario para búsqueda rápida por fecha
    history_cache = {}
    for _, row in df_hist.iterrows():
        history_cache[row['Fecha']] = row

    df_result = create_tabla_reduccion(df,history_cache,raw_start,config)
    return df_result


def create_tabla_reduccion(df,history_cache: dict[Any, Any],raw_start,config) -> DataFrame:
    hoy = ahora.date()
    start_date = pd.to_datetime(str(raw_start).strip()).date()
    start_amount = float(config.get("plan_start_amount", 15.0))
    rate = float(config.get("reduction_rate", 0.1))
    dosis_media = float(config.get("dosis", 3.0))

    # 2. Agrupar consumo real por día
    df_real = df.copy()
    df_real['fecha_date'] = df_real['timestamp'].dt.date
    diario_real = df_real.groupby('fecha_date')['ml'].sum()

    if rate > 0:
        dias_estimados = int(start_amount / rate) + 1
        end_date = start_date + pd.Timedelta(days=dias_estimados)
    else:
        end_date = hoy + pd.Timedelta(days=30)  # Proyección por defecto si no hay reducción

    fechas = pd.date_range(start=start_date, end=max(end_date, hoy), freq='D')
    data_rows = []
    for i, fecha in enumerate(fechas):
        fecha_date = fecha.date()
        fecha_str = fecha_date.strftime('%d/%m/%Y')

        # Cálculos del Plan
        # Si es un día pasado y existe en caché, usamos el dato guardado (congelamos historia)
        if fecha_date < hoy and fecha_str in history_cache:
            objetivo = float(history_cache[fecha_str]['Objetivo (ml)'])
            reduccion_hoy = float(history_cache[fecha_str]['Reducción Plan'])
        else:
            objetivo = max(0.0, start_amount - ((i + 1) * rate))
            reduccion_hoy = rate

        # Intervalo teórico (minutos) = 24h / (Objetivo / Dosis)
        intervalo_teorico = int((24 * 60) / (objetivo / dosis_media)) if (objetivo > 0 and dosis_media > 0) else 0
        intervalo_str = f"{intervalo_teorico // 60}h {intervalo_teorico % 60}m" if intervalo_teorico > 0 else "---"

        # Datos Reales
        consumo_real = diario_real.get(fecha_date, 0.0)

        if fecha_date < hoy:
            # Ciclo cerrado (días anteriores)
            estado = "✅ Sí" if consumo_real <= (objetivo + 0.5) else "❌ No"
        elif fecha_date == hoy:
            # Ciclo en curso (hoy)
            estado = "⏳ En curso" if consumo_real <= (objetivo + 0.5) else "⚠️ Excedido"
        else:
            # Días futuros
            estado = "🔮 Futuro"

        data_rows.append({
            "Fecha": fecha_str,
            "Objetivo (ml)": round(objetivo, 2),
            "Real (ml)": round(consumo_real, 2),
            "Reducción Plan": round(reduccion_hoy, 2),
            "Intervalo Teórico": intervalo_str,
            "Estado": estado
        })

    df_result = pd.DataFrame(data_rows)
    # Convertir a datetime para ordenar correctamente y no alfabéticamente
    df_result['fecha_dt'] = pd.to_datetime(df_result['Fecha'], format='%d/%m/%Y')
    df_result = df_result.sort_values('fecha_dt', ascending=True).drop(columns=['fecha_dt'])
    return df_result


def obtener_media_3d(resumen):
    if len(resumen) >= 4:
        return resumen.iloc[1:4]['total_ml'].mean()
    elif len(resumen) >= 2:
        return resumen.iloc[1]['total_ml']
    return 15.0  # Valor por defecto
def calcular_concentracion_dinamica(df_final, df_excel, ka_val, hl_val):
    k_el = np.log(2) / hl_val
    timeline = df_final.index
    concentracion = np.zeros(len(timeline))

    for _, row in df_excel.iterrows():
        # Calcular tiempo transcurrido desde cada toma en horas
        t = (timeline - row['timestamp']).total_seconds() / 3600
        mask = t >= 0

        # Evitar división por cero si ka == k_el
        curr_ka = ka_val if ka_val != k_el else ka_val + 0.01

        factor_escala = curr_ka / (curr_ka - k_el)
        curva = row['ml'] * factor_escala * (np.exp(-k_el * t[mask]) - np.exp(-curr_ka * t[mask]))
        concentracion[mask] += curva

    res = pd.Series(concentracion, index=timeline)
    res[res < 0.05] = 0  # Limpiar ruido visual bajo
    return res
def rellenar_datos_sin_frecuencia(df_fit, df_excel):
    # Determinar el punto de inicio
    if df_fit.empty:
        inicio = df_excel['timestamp'].min() if not df_excel.empty else ahora
    else:
        inicio = df_fit.index.max()

    if ahora.floor('1min') > inicio:
        rango = pd.date_range(start=inicio + pd.Timedelta(minutes=1), end=ahora.floor('1min'), freq='1min')
        df_relleno = pd.DataFrame(index=rango)
        return pd.concat([df_fit, df_relleno]).sort_index()
    return df_fit