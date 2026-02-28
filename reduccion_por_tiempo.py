from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from pandas import DataFrame

from database import get_plan_history_data, save_plan_history_data, save_config


def mlAcumulados():
    if st.session_state.config.get("plan.checkpoint_fecha"):
        # Lógica original para plan por tiempo (reducción continua)
        ml_reduccion_diaria = float(st.session_state.config.get("plan.reduccion_diaria", 0.5))
        checkpoint_ml = float(st.session_state.config.get("tiempos.checkpoint_ml"))
        checkpoint_fecha = pd.to_datetime(st.session_state.config.get("plan.checkpoint_fecha"))

        if checkpoint_fecha.tzinfo is None or checkpoint_fecha.tzinfo.utcoffset(pd.Timestamp.now(tz='Europe/Madrid')) is None:
            checkpoint_fecha = checkpoint_fecha.tz_convert('Europe/Madrid')

        horas_desde_checkpoint = (pd.Timestamp.now(tz='Europe/Madrid') - checkpoint_fecha).total_seconds() / 3600
        def integral(t_h):
            if t_h < 0: return (checkpoint_ml / 24.0) * t_h
            t_fin = (checkpoint_ml / ml_reduccion_diaria) * 24 if ml_reduccion_diaria > 0 else 999999
            t_eff = min(t_h, t_fin)
            return (checkpoint_ml / 24.0) * t_eff - (ml_reduccion_diaria / 1152.0) * (t_eff ** 2)

        integ= integral(horas_desde_checkpoint)

        print(f"[mlAcumulados] -> checkpoint_ml: {checkpoint_ml},integral: {integ}, checkpoint_fecha: {checkpoint_fecha}, ml_reduccion_diaria: {ml_reduccion_diaria}")
        return  float(checkpoint_ml + integ)

    else:
        return float(0)
def crear_tabla(ml_dosis_actual, reduccion_diaria, ml_dia_actual):

    tabla = []
    fecha_dia = datetime.now()
    objetivo_dia = ml_dia_actual

    while objetivo_dia > 0:
        # Intervalo (minutos) = 24h / (Objetivo / Dosis)
        intervalo_teorico = int((24 * 60) / (objetivo_dia / ml_dosis_actual)) if (objetivo_dia > 0 and ml_dosis_actual > 0) else 0
        intervalo_horas = f"{intervalo_teorico // 60}h {intervalo_teorico % 60}m" if intervalo_teorico > 0 else "---"

        tabla.append({
            "Fecha": fecha_dia.strftime("%Y-%m-%d"),
            "Objetivo (ml)": round(objetivo_dia, 2),
            "Reducción Diaria": round(reduccion_diaria, 2),
            "Dosis": round(ml_dosis_actual, 2),
            "Intervalo": intervalo_horas,
            "Real (ml)": 0,
            "Estado": "",
        })
        objetivo_dia = max(0, objetivo_dia - reduccion_diaria)
        fecha_dia += timedelta(days=1)
        ml_dosis_actual = round(ml_dosis_actual, 2)
    return pd.DataFrame(tabla)
def obtener_tabla():
    """
    (LEE DATOS de 'PlanHistory')
    Obtiene los datos del plan, los convierte a tipos correctos y calcula el estado.
    """
    df = get_plan_history_data(sheet_name="Plan Tiempo") # <- CORREGIDO
    if df.empty:
        return pd.DataFrame()

    for col in ['Objetivo (ml)', 'Real (ml)', 'Reducción Diaria', 'Dosis']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Manejo robusto de fechas
    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # Si las fechas ya tienen zona horaria (tz-aware), convertimos directamente
    if df['Fecha'].dt.tz is not None:
         df['Fecha'] = df['Fecha'].dt.tz_convert('Europe/Madrid')
    else:
         # Si no tienen zona horaria (tz-naive), las localizamos primero
         # Asumimos que vienen en UTC o sin zona, las tratamos como UTC y luego Madrid
         df['Fecha'] = df['Fecha'].dt.tz_localize('UTC').dt.tz_convert('Europe/Madrid')

    # fecha_actual_str = datetime.now().strftime("%Y-%m-%d")
    hoy = datetime.now().date() # Obtener la fecha de HOY (objeto date) una sola vez
    def calcular_estado(row):
        if row["Fecha"].date() < hoy:
            # Ciclo cerrado (días anteriores)
            if row['Real (ml)'] <= row['Objetivo (ml)'] + 0.5:
                return "✅ Sí"
            else:
                return "❌ No"
        elif row["Fecha"].date() == hoy:
            # Ciclo en curso (hoy)
            return "⏳ En curso"
        else:
            # Días futuros
            return "🔮 Futuro"


    df['Estado'] = df.apply(calcular_estado, axis=1)
    df['Dosis'] = df['Dosis'].map('{:.2f}'.format)
    return df
def replanificar(dosis_media, reduccion_diaria, ml_dia_actual):
    df_existente = obtener_tabla()
    fecha_actual_str = datetime.now().strftime("%Y-%m-%d")
    
    df_conservada = df_existente[df_existente["Fecha"] < fecha_actual_str]
    df_nuevo = crear_tabla(dosis_media, reduccion_diaria, ml_dia_actual)
    
    df_final = pd.concat([df_conservada, df_nuevo], ignore_index=True)

    save_plan_history_data(df_final, sheet_name="Plan Tiempo") # <- CORREGIDO
    print(f"Plan replanificado en la hoja 'PlanHistory'.")
    return df_final
def add_toma(fecha_toma, ml_toma) -> DataFrame:
    ml_bote=mlAcumulados()
    nuevo_checkpoint_ml = ml_bote - ml_toma
    # Actualizar tabla local
    df_plan = obtener_tabla()

    # Usar string formateado para comparar fechas sin problemas de hora/zona
    # Asumimos que fecha_toma viene como objeto date o datetime
    if isinstance(fecha_toma, datetime):
        fecha_toma_str = fecha_toma.strftime('%Y-%m-%d')
    else:
        fecha_toma_str = str(fecha_toma)

    # Crear columna temporal de string para matching
    df_plan["Fecha_Str"] = df_plan["Fecha"].dt.strftime('%Y-%m-%d')

    if fecha_toma_str in df_plan["Fecha_Str"].values:
        idx = df_plan[df_plan['Fecha_Str'] == fecha_toma_str].index
        df_plan.loc[idx, 'Real (ml)'] += ml_toma

        # Guardar sin columnas auxiliares ni Estado
        cols_to_drop = ['Fecha_Str', 'Estado']
        df_to_save = df_plan.drop(columns=[c for c in cols_to_drop if c in df_plan.columns])

        save_plan_history_data(df_to_save, sheet_name="Plan Dosis")

        save_config({
            "plan.checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
            "checkpoint_ml": nuevo_checkpoint_ml
        })
        print(f"Toma guardada. Checkpoint actualizado.")
    else:
        print(f"ERROR: La fecha {fecha_toma_str} no se encontró en el plan.")
    return df_plan