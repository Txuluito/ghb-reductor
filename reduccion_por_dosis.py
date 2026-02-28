import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

from pandas import DataFrame

from database import get_plan_history_data, save_plan_history_data, get_config, save_config, enviar_toma_api

def mlAcumulados():
    if st.session_state.config.get("plan.checkpoint_fecha"):
        dosis_actual = float(st.session_state.config.get("dosis.ml_dia", 3.0))
        intervalo = float(st.session_state.config.get("dosis.intervalo_horas", 2.0))

        # Tasa de generación (ml/hora) = Dosis / Intervalo
        tasa_generacion = dosis_actual / intervalo if intervalo > 0 else 0

        checkpoint_ml = float(st.session_state.config.get("dosis.checkpoint_ml", 0.0))
        checkpoint_fecha = pd.to_datetime(st.session_state.config.get("plan.checkpoint_fecha"))

        if checkpoint_fecha.tzinfo is None or checkpoint_fecha.tzinfo.utcoffset(pd.Timestamp.now(tz='Europe/Madrid')) is None:
            checkpoint_fecha = checkpoint_fecha.tz_localize('UTC').tz_convert('Europe/Madrid')
        else:
            checkpoint_fecha = checkpoint_fecha.tz_convert('Europe/Madrid')

        horas_pasadas = (pd.Timestamp.now(tz='Europe/Madrid') - checkpoint_fecha).total_seconds() / 3600

        generado = tasa_generacion * horas_pasadas
        return float(checkpoint_ml + generado)
    else:
        return float(0)
def crear_tabla(ml_dosis, reduccion_dosis, intervalo_horas):
    tabla = []
    fecha_dia = datetime.now()
    dosis_actual = float(ml_dosis)
    reduccion_dosis = float(reduccion_dosis)
    tomas_dia = 24.0 / intervalo_horas
    
    # Límite de seguridad
    max_dias = 365
    dias_count = 0

    while dosis_actual >= 0.1 and dias_count < max_dias:
        total_dia = dosis_actual * tomas_dia

        tabla.append({
            "Fecha": fecha_dia.strftime("%Y-%m-%d"),
            "Objetivo (ml)": round(total_dia, 2),
            "Real (ml)": 0.0,
            "Dosis Obj (ml)": round(dosis_actual, 3),
            "Intervalo": f"{intervalo_horas}h",
            "Reducción Dosis": round(reduccion_dosis, 3),
            "Estado": ""
        })
        
        dosis_actual = max(0.0, dosis_actual - reduccion_dosis)
        fecha_dia += timedelta(days=1)
        dias_count += 1
    return pd.DataFrame(tabla)
    save_plan_history_data(pd.DataFrame(tabla), sheet_name="PlanHistoryDosis")

def obtener_tabla():
    """
    (LEE DATOS de 'PlanHistory')
    Obtiene los datos del plan, los convierte a tipos correctos y calcula el estado.
    """
    df = get_plan_history_data(sheet_name="PlanHistoryDosis")
    if df.empty:
        return pd.DataFrame()

    # Asegurar tipos numéricos
    cols_num = ['Objetivo (ml)', 'Real (ml)', 'Dosis Obj (ml)', 'Reducción Dosis']
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
    if 'Fecha' in df.columns:
        # Convertir a datetime
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        # Si no tiene zona horaria, se la ponemos (asumimos UTC o local y convertimos)
        if df['Fecha'].dt.tz is None:
             # Si asumimos que vienen como string "YYYY-MM-DD", al parsear son naive.
             # Las localizamos a Madrid directamente o convertimos si fuera necesario.
             # Para simplificar y ser consistentes con el resto de la app:
             df['Fecha'] = df['Fecha'].dt.tz_localize('Europe/Madrid')
        else:
             df['Fecha'] = df['Fecha'].dt.tz_convert('Europe/Madrid')

    hoy = datetime.now().date()
    
    def calcular_estado(row):
        fecha_row = row["Fecha"].date()
        if fecha_row < hoy:
            # Ciclo cerrado
            if row['Real (ml)'] <= row['Objetivo (ml)'] + 0.5:
                return "✅ Sí"
            else:
                return "❌ No"
        elif fecha_row == hoy:
            # Ciclo en curso
            return "⏳ En curso"
        else:
            # Días futuros
            return "🔮 Futuro"

    if 'Fecha' in df.columns:
        df['Estado'] = df.apply(calcular_estado, axis=1)

    return df
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

        save_plan_history_data(df_to_save, sheet_name="PlanHistoryDosis")

        save_config({
            "plan.checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
            "dosis.checkpoint_ml": nuevo_checkpoint_ml
        })
        print(f"Toma guardada. Checkpoint actualizado.")
    else:
        print(f"ERROR: La fecha {fecha_toma_str} no se encontró en el plan.")
    return df_plan


def replanificar(dosis_media, reduccion_diaria, cantidad_inicial):
    df_existente = obtener_tabla()
    fecha_actual_str = datetime.now().strftime("%Y-%m-%d")

    df_conservada = df_existente[df_existente["Fecha"] < fecha_actual_str]
    df_nuevo = crear_tabla(dosis_media, reduccion_diaria, cantidad_inicial)

    df_final = pd.concat([df_conservada, df_nuevo], ignore_index=True)

    save_plan_history_data(df_final, sheet_name="PlanHistoryDosis")  # <- CORREGIDO

    print(f"Plan replanificado en la hoja 'PlanHistory'.")
    return df_final