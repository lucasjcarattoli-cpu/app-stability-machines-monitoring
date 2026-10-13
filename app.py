import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import datetime
import plotly.express as px
import io
import sqlite3
import plotly.graph_objects as go

# Configuración inicial de la página (Dark Mode analítico)
st.set_page_config(page_title="Dashboard Varifarma", layout="wide", page_icon="🌡️")

# --- PASO 1: CONEXIÓN SQLALCHEMY + CARGA ROBUSTA DE FECHAS ---
DATABASE_URL = "sqlite:///data/varifarma_monitoreo.db"
engine = create_engine(DATABASE_URL)

@st.cache_data
def cargar_datos():
    query = "SELECT * FROM registros_camaras"
    df = pd.read_sql(query, engine)
    
    # Limpieza y conversión robusta de fechas y horas para evitar desvíos de formato
    df['DATE_clean'] = df['DATE'].astype(str).str.strip()
    df['TIME_clean'] = df['TIME'].astype(str).str.strip()
    
    # Creamos un timestamp unificado forzando el formato Día/Mes/Año
    df['timestamp'] = pd.to_datetime(df['DATE_clean'] + ' ' + df['TIME_clean'], format='mixed', dayfirst=True, errors='coerce')
    df['fecha_dt'] = pd.to_datetime(df['DATE_clean'], format='mixed', dayfirst=True, errors='coerce').dt.normalize()    
    return df

with st.spinner("Cargando base de datos unificada..."):
    df_completo = cargar_datos()

# --- PASO 3: SELECTOR TEMPORAL Y FILTROS (SIDEBAR) ---
st.sidebar.title("🎛️ Panel de Control")

camaras_disponibles = df_completo['camara'].unique()
camara_seleccionada = st.sidebar.selectbox("Cámara a monitorear:", camaras_disponibles)

# --- CONFIGURACIÓN FIJA DE ONGOING SEGÚN LA CÁMARA ---
cam_clean = str(camara_seleccionada).strip().upper()
if "CES05" in cam_clean:
    temp_nominal = 25.0
    hum_nominal = 60.0  # Setpoint estándar Zona II (% HR)
    zona_label = "Zona II (Clima Templado)"
else:  
    temp_nominal = 30.0
    hum_nominal = 75.0  # Setpoint estándar Zona IV (% HR)
    zona_label = "Zona IV (Clima Cálido/Húmedo)"

margen_temp = 2.0
limite_inferior_temp = temp_nominal - margen_temp
limite_superior_temp = temp_nominal + margen_temp

# Tolerancia estándar para humedad (ej: ±5% o ±10% alrededor del setpoint)
margen_hum = 5.0 
limite_inferior_hum = max(0.0, hum_nominal - margen_hum)
limite_superior_hum = min(100.0, hum_nominal + margen_hum)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Condición Ongoing:** `{zona_label}`")
st.sidebar.markdown(f"**Temp. Permitida:** `{limite_inferior_temp}°C` a `{limite_superior_temp}°C`")
st.sidebar.markdown(f"**Humedad Permitida:** `{limite_inferior_hum}%` a `{limite_superior_hum}%`")

st.sidebar.markdown("---")
opcion_fecha = st.sidebar.radio(
    "⏱️ Rango Temporal:",
    ["Histórico Total", "Últimos 7 días", "Último Mes", "Calendario Personalizado"]
)

fecha_max = df_completo['fecha_dt'].max()
fecha_min_db = df_completo['fecha_dt'].min()

if opcion_fecha == "Histórico Total":
    fecha_inicio, fecha_fin = fecha_min_db, fecha_max
elif opcion_fecha == "Últimos 7 días":
    fecha_inicio, fecha_fin = fecha_max - datetime.timedelta(days=7), fecha_max
elif opcion_fecha == "Último Mes":
    fecha_inicio, fecha_fin = fecha_max - datetime.timedelta(days=30), fecha_max
else:
    fechas = st.sidebar.date_input("Seleccioná el rango:", [fecha_min_db, fecha_max])
    if len(fechas) == 2:
        fecha_inicio, fecha_fin = pd.to_datetime(fechas[0]), pd.to_datetime(fechas[1])
    else:
        fecha_inicio, fecha_fin = fecha_min_db, fecha_max

mask = (
    (df_completo['camara'] == camara_seleccionada) & 
    (df_completo['fecha_dt'] >= fecha_inicio) & 
    (df_completo['fecha_dt'] <= fecha_fin)
)
df_filtrado = df_completo.loc[mask].sort_values('timestamp')

# --- ESTRUCTURA MULTI-PAGE (TABS) ---
st.title("🌡️ Panel de Monitoreo - Estabilidad Farmacéutica")
st.markdown(f"**Viendo datos de:** `{fecha_inicio.strftime('%d/%m/%Y')}` al `{fecha_fin.strftime('%d/%m/%Y')}` | **Registros:** `{len(df_filtrado)}`")

tab1, tab2, tab3 = st.tabs(["📊 Monitoreo General", "🚨 Auditoría de Anomalías", "🗄️ Datos Crudos"])

# ==========================================
# PESTAÑA 1: KPIs, Curvas Multisensor e Histograma
# ==========================================
with tab1:
    st.subheader("Indicadores Principales")
    
    if not df_filtrado.empty:
        dias_rango = max((fecha_fin - fecha_inicio).days, 1)
        fecha_prev_inicio = fecha_inicio - datetime.timedelta(days=dias_rango)
        df_previo = df_completo[(df_completo['camara'] == camara_seleccionada) & 
                                (df_completo['fecha_dt'] >= fecha_prev_inicio) & 
                                (df_completo['fecha_dt'] < fecha_inicio)]

        # Definición robusta incluyendo ambas variantes posibles (con y sin guion) para el sensor 3
        sensores_temp = ['CES04TEMP1', 'CES04TEMP2', 'CES04TEMP3', 'CES04-TEMP3', 'CES04TEMP4']
        sensores_hum = ['CES04HUM1', 'CES04HUM2', 'CES04HUM3', 'CES04-HUM3', 'CES04HUM4']
        
        # Filtramos únicamente los que realmente existen en el DataFrame cargado
        sensores_temp_activos = [col for col in sensores_temp if col in df_filtrado.columns]
        sensores_hum_activos = [col for col in sensores_hum if col in df_filtrado.columns]

        temp_actual = df_filtrado[sensores_temp_activos].mean().mean() if sensores_temp_activos else 0
        hum_actual = df_filtrado[sensores_hum_activos].mean().mean() if sensores_hum_activos else 0
        temp_max_actual = df_filtrado[sensores_temp_activos].max().max() if sensores_temp_activos else 0

        temp_prev = df_previo[sensores_temp_activos].mean().mean() if not df_previo.empty and sensores_temp_activos else temp_actual
        hum_prev = df_previo[sensores_hum_activos].mean().mean() if not df_previo.empty and sensores_hum_activos else hum_actual
        temp_max_prev = df_previo[sensores_temp_activos].max().max() if not df_previo.empty and sensores_temp_activos else temp_max_actual

        col1, col2, col3 = st.columns(3)
        col1.metric("🌡️ Temp Promedio", f"{temp_actual:.1f} °C", f"{(temp_actual - temp_prev):.2f} °C", delta_color="inverse")
        col2.metric("💧 Humedad Promedio", f"{hum_actual:.1f} %", f"{(hum_actual - hum_prev):.2f} %", delta_color="off")
        col3.metric("🔥 Pico Máximo Temp", f"{temp_max_actual:.1f} °C", f"{(temp_max_actual - temp_max_prev):.2f} °C", delta_color="inverse")

        # --- SELECTOR DE VARIABLE A VISUALIZAR (TEMPERATURA VS HUMEDAD) ---
        st.markdown("---")
        tipo_vista = st.radio(
            "🔍 Seleccionar Parámetro de Análisis:",
            ["🌡️ Temperatura Multisensor", "💧 Humedad Relativa Multisensor"],
            horizontal=True
        )

        # --- CARGA Y DEPURACIÓN DE EVENTOS DEL LOGBOOK ---
        try:
            conn_ev = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
            query_ev = f"SELECT fecha, hora, categoria, descripcion FROM logbook_eventos WHERE TRIM(camara) = '{camara_seleccionada.strip()}'"
            df_eventos = pd.read_sql(query_ev, conn_ev)
            conn_ev.close()
            
            if not df_eventos.empty:
                df_eventos['fecha_clean'] = df_eventos['fecha'].astype(str).str.replace('~', '', regex=False).str.strip()
                df_eventos['fecha_dt'] = pd.to_datetime(df_eventos['fecha_clean'], format='mixed', dayfirst=True, errors='coerce')
                df_eventos = df_eventos.dropna(subset=['fecha_dt'])
                
                f_ini = pd.to_datetime(fecha_inicio).normalize()
                f_fin = pd.to_datetime(fecha_fin).normalize()
                df_eventos_filtro = df_eventos[(df_eventos['fecha_dt'] >= f_ini) & (df_eventos['fecha_dt'] <= f_fin)]
            else:
                df_eventos_filtro = pd.DataFrame()
        except Exception as e:
            st.warning(f"Error cargando eventos: {e}")
            df_eventos_filtro = pd.DataFrame()

        # --- RENDERIZADO CONDICIONAL SEGÚN LA VISTA SELECCIONADA ---
        if "Temperatura" in tipo_vista:
            st.subheader(f"Curva Térmica Multisensor (Setpoint: {temp_nominal}°C | Rango: {limite_inferior_temp}°C - {limite_superior_temp}°C)")
            
            fig = px.line(df_filtrado, x='timestamp', y=sensores_temp_activos)
            fig.add_hline(y=limite_superior_temp, line_dash="dash", line_color="red", annotation_text=f"Límite Sup ({limite_superior_temp}°C)")
            fig.add_hline(y=limite_inferior_temp, line_dash="dash", line_color="orange", annotation_text=f"Límite Inf ({limite_inferior_temp}°C)")
            
            y_marker_pos = limite_superior_temp + 8.0
            techo_y = limite_superior_temp + 10.0
            piso_y = limite_inferior_temp - 10.0
            y_axis_range = [piso_y, techo_y]
            y_title = "Temperatura (°C)"
            
        else:
            st.subheader(f"Curva de Humedad Relativa Multisensor (Setpoint: {hum_nominal}% | Rango: {limite_inferior_hum}% - {limite_superior_hum}%)")
            
            fig = px.line(df_filtrado, x='timestamp', y=sensores_hum_activos)
            fig.add_hline(y=limite_superior_hum, line_dash="dash", line_color="red", annotation_text=f"Límite Sup ({limite_superior_hum}%)")
            fig.add_hline(y=limite_inferior_hum, line_dash="dash", line_color="orange", annotation_text=f"Límite Inf ({limite_inferior_hum}%)")
            
            y_marker_pos = 95.0
            y_axis_range = [0, 100]
            y_title = "Humedad Relativa (% HR)"

        fig.update_layout(legend_title_text='Sensores')

        # Marcadores flotantes de eventos arriba
        x_puntos = []
        y_puntos = []
        colores_puntos = []
        textos_hover = []

        if not df_eventos_filtro.empty:
            for idx, row in df_eventos_filtro.iterrows():
                f_dt = row['fecha_dt']
                cat = str(row['categoria']).strip()
                desc = str(row['descripcion']).strip()
                
                if desc == "" or desc.lower() == "nan" or desc.lower() == "none":
                    continue
                
                color_punto = "red" if "falla" in cat.lower() else ("green" if "mantenimiento" in cat.lower() else "orange")
                
                x_puntos.append(f_dt)
                y_puntos.append(y_marker_pos)  
                colores_puntos.append(color_punto)
                textos_hover.append(f"<b>{f_dt.strftime('%d/%m/%Y')}</b><br><b>{cat.upper()}</b><br>{desc}<extra></extra>")

            if x_puntos:
                fig.add_trace(go.Scatter(
                    x=x_puntos,
                    y=y_puntos,
                    mode='markers',
                    marker=dict(
                        size=12, 
                        color=colores_puntos, 
                        symbol='circle', 
                        line=dict(width=2, color='white')
                    ),
                    name="Incidencias",
                    hovertemplate=textos_hover
                ))

        fig.update_layout(
            xaxis_title="Fecha", 
            yaxis_title=y_title, 
            yaxis=dict(range=y_axis_range), 
            xaxis=dict(zeroline=False)
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- TABLA RESUMEN DE EVENTOS ---
        if not df_eventos_filtro.empty:
            df_mostrar = df_eventos_filtro.dropna(subset=['descripcion'])
            df_mostrar = df_mostrar[df_mostrar['descripcion'].str.strip() != ""]
            df_mostrar['fecha'] = df_mostrar['fecha_dt'].dt.strftime('%Y-%m-%d')
            
            with st.expander(f"📝 Ver detalle de los {len(df_mostrar)} incidentes en este período", expanded=False):
                st.dataframe(
                    df_mostrar[['fecha', 'categoria', 'descripcion']].rename(columns={'descripcion': 'descripción'}), 
                    use_container_width=True, 
                    hide_index=True
                )

        # Histograma de Distribución
        st.markdown("---")
        st.subheader("📊 Distribución de Frecuencia")
        if "Temperatura" in tipo_vista and sensores_temp_activos:
            df_filtrado['val_prom_hist'] = df_filtrado[sensores_temp_activos].mean(axis=1)
            x_hist_label = "Temperatura Promedio (°C)"
        elif sensores_hum_activos:
            df_filtrado['val_prom_hist'] = df_filtrado[sensores_hum_activos].mean(axis=1)
            x_hist_label = "Humedad Relativa Promedio (% HR)"
        else:
            df_filtrado['val_prom_hist'] = 0
            x_hist_label = "Valor"

        fig_hist = px.histogram(
            df_filtrado, 
            x='val_prom_hist', 
            nbins=40, 
            color_discrete_sequence=['#00d2d3'],
            opacity=0.8
        )
        fig_hist.update_layout(
            xaxis_title=x_hist_label, 
            yaxis_title="Cantidad de Mediciones",
            bargap=0.1
        )
        st.plotly_chart(fig_hist, use_container_width=True)

        # --- ANÁLISIS DE GRADIENTE (TÉRMICO Y HUMEDAD) ---
        st.markdown("---")
        st.subheader("📐 Análisis de Homogeneidad y Gradiente (Puntos Críticos)")
        
        if "Temperatura" in tipo_vista:
            if len(sensores_temp_activos) >= 2:
                # Cálculo de Gradiente Térmico
                df_filtrado['temp_max_camara'] = df_filtrado[sensores_temp_activos].max(axis=1)
                df_filtrado['temp_min_camara'] = df_filtrado[sensores_temp_activos].min(axis=1)
                df_filtrado['gradiente'] = df_filtrado['temp_max_camara'] - df_filtrado['temp_min_camara']
                
                grad_promedio = df_filtrado['gradiente'].mean()
                grad_maximo = df_filtrado['gradiente'].max()
                
                col_g1, col_g2 = st.columns(2)
                col_g1.metric("📊 Gradiente Térmico Promedio", f"{grad_promedio:.2f} °C", help="Diferencia media entre el sensor más caliente y el más frío.")
                col_g2.metric("⚠️ Gradiente Térmico Máximo (Pico)", f"{grad_maximo:.2f} °C", help="Máxima disparidad registrada entre sensores en un mismo instante.")
                
                fig_grad = px.line(
                    df_filtrado, 
                    x='timestamp', 
                    y='gradiente',
                    color_discrete_sequence=['#ff7f0e']
                )
                fig_grad.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="Umbral de Alerta Gradiente (1.0°C)")
                fig_grad.update_layout(
                    xaxis_title="Fecha",
                    yaxis_title="Disparidad Térmica (Máx - Mín en °C)",
                    xaxis=dict(zeroline=False)
                )
                st.plotly_chart(fig_grad, use_container_width=True)
                st.caption("📌 Un gradiente térmico elevado indica problemas de recirculación de aire, filtros sucios o cargas mal distribuidas.")
            else:
                st.info("Se requieren al menos 2 sensores activos de temperatura para calcular el gradiente.")
        
        else:
            if len(sensores_hum_activos) >= 2:
                # Cálculo de Gradiente de Humedad
                df_filtrado['hum_max_camara'] = df_filtrado[sensores_hum_activos].max(axis=1)
                df_filtrado['hum_min_camara'] = df_filtrado[sensores_hum_activos].min(axis=1)
                df_filtrado['gradiente'] = df_filtrado['hum_max_camara'] - df_filtrado['hum_min_camara']
                
                grad_promedio = df_filtrado['gradiente'].mean()
                grad_maximo = df_filtrado['gradiente'].max()
                
                col_g1, col_g2 = st.columns(2)
                col_g1.metric("📊 Gradiente de Humedad Promedio", f"{grad_promedio:.2f} % HR", help="Diferencia media entre el sensor más húmedo y el más seco.")
                col_g2.metric("⚠️ Gradiente de Humedad Máximo (Pico)", f"{grad_maximo:.2f} % HR", help="Máxima disparidad registrada entre sensores en un mismo instante.")
                
                fig_grad = px.line(
                    df_filtrado, 
                    x='timestamp', 
                    y='gradiente',
                    color_discrete_sequence=['#1f77b4'] # Azul para humedad
                )
                fig_grad.add_hline(y=7.0, line_dash="dash", line_color="red", annotation_text="Umbral de Alerta Gradiente (5.0%)")
                fig_grad.update_layout(
                    xaxis_title="Fecha",
                    yaxis_title="Disparidad de Humedad (Máx - Mín en % HR)",
                    xaxis=dict(zeroline=False)
                )
                st.plotly_chart(fig_grad, use_container_width=True)
                st.caption("📌 Un gradiente de humedad elevado indica estancamiento de aire húmedo o problemas en la deshumidificación.")
            else:
                st.info("Se requieren al menos 2 sensores activos de humedad para calcular el gradiente.")
# ==========================================
# PESTAÑA 2: Auditoría de Anomalías (Temp y Humedad)
# ==========================================
with tab2:
    st.subheader("🚨 Reporte de Excursiones (Temperatura y Humedad)")
    st.info(f"Evaluando rangos para **{camara_seleccionada}** ({zona_label}):\n* **Temp:** {limite_inferior_temp}°C a {limite_superior_temp}°C\n* **Humedad:** {limite_inferior_hum}% a {limite_superior_hum}%")
    
    if not df_filtrado.empty:
        mask_temp = pd.Series(False, index=df_filtrado.index)
        for s in sensores_temp_activos:
            mask_temp = mask_temp | (df_filtrado[s] > limite_superior_temp) | (df_filtrado[s] < limite_inferior_temp)

        mask_hum = pd.Series(False, index=df_filtrado.index)
        for s in sensores_hum_activos:
            mask_hum = mask_hum | (df_filtrado[s] > limite_superior_hum) | (df_filtrado[s] < limite_inferior_hum)

        df_exc_temp = df_filtrado[mask_temp]
        df_exc_hum = df_filtrado[mask_hum]

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"### Excursiones de Temperatura (`{len(df_exc_temp)}`)")
            if not df_exc_temp.empty:
                st.dataframe(df_exc_temp[['DATE', 'TIME'] + sensores_temp_activos], use_container_width=True, hide_index=True)
            else:
                st.success("Sin excursiones térmicas.")

        with col_b:
            st.markdown(f"### Excursiones de Humedad (`{len(df_exc_hum)}`)")
            if not df_exc_hum.empty:
                st.dataframe(df_exc_hum[['DATE', 'TIME'] + sensores_hum_activos], use_container_width=True, hide_index=True)
            else:
                st.success("Sin excursiones de humedad.")

# ==========================================
# SECCIÓN: FORECASTING Y BACKTESTING
# ==========================================
st.markdown("---")
st.header(f"🔮 Control de Predicciones Semanales - {camara_seleccionada}")
st.markdown("Seguimiento automático de las proyecciones del modelo vs. la realidad operativa de la cámara.")

try:
    conn_pred = sqlite3.connect("data/varifarma_monitoreo.db")
    # Traemos los datos ordenados cronológicamente para poder graficarlos bien
    query_pred = f"""
        SELECT fecha_generacion as 'Generado el', 
               horizonte_dias as 'Horizonte (Días)', 
               fecha_objetivo as 'Fecha a Predecir', 
               temperatura_predicha as 'Temp Esperada', 
               temperatura_real as 'Temp Real', 
               estado as 'Estado' 
        FROM predicciones_control
        WHERE TRIM(camara) = '{camara_seleccionada.strip()}'
        ORDER BY fecha_objetivo ASC
    """
    df_pred = pd.read_sql(query_pred, conn_pred)
    conn_pred.close()

    if not df_pred.empty:
        st.subheader("📈 Backtesting Visual: Modelo vs Realidad")
        
        # Preparamos los datos para el gráfico
        df_grafico = df_pred.copy()
        df_grafico['Fecha_DT'] = pd.to_datetime(df_grafico['Fecha a Predecir'])
        
        # Instanciamos el gráfico
        fig_backtest = go.Figure()
        
        # 1. Línea Naranja Punteada: Lo que el modelo predijo
        fig_backtest.add_trace(go.Scatter(
            x=df_grafico['Fecha_DT'],
            y=df_grafico['Temp Esperada'],
            mode='lines+markers',
            name='Temp. Predicha (Random Forest)',
            line=dict(color='orange', dash='dash')
        ))
        
        # 2. Línea Azul Sólida: La realidad (solo grafica donde ya hay datos reales cargados)
        df_real = df_grafico.dropna(subset=['Temp Real'])
        if not df_real.empty:
            fig_backtest.add_trace(go.Scatter(
                x=df_real['Fecha_DT'],
                y=df_real['Temp Real'],
                mode='lines+markers',
                name='Temp. Real Registrada',
                line=dict(color='deepskyblue', width=3)
            ))
            
        fig_backtest.update_layout(
            xaxis_title="Fecha Objetivo",
            yaxis_title="Temperatura (°C)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_backtest, use_container_width=True)
    
        # Mostramos la tabla formateada debajo (ordenada de lo más nuevo a lo más viejo)
        df_tabla = df_pred.copy()
        df_tabla['Temp Esperada'] = df_tabla['Temp Esperada'].round(2).astype(str) + " °C"
        df_tabla['Temp Real'] = df_tabla['Temp Real'].apply(lambda x: f"{x:.2f} °C" if pd.notnull(x) else "---")
        df_tabla = df_tabla.sort_values(by='Fecha a Predecir', ascending=False)
        
        st.dataframe(df_tabla.drop(columns=['Fecha_DT'], errors='ignore'), use_container_width=True, hide_index=True)
        st.caption("📌 'Pendiente' indica que aún no se han subido registros reales que cubran esa fecha futura.")
    else:
        st.info(f"ℹ️ Aún no hay predicciones registradas para la cámara {camara_seleccionada}.")
except Exception as e:
    st.warning(f"La tabla de predicciones requiere actualización: {e}")

# ==========================================
# PESTAÑA 3: Datos Crudos y Exportación
# ==========================================
with tab3:
    st.subheader("🗄️ Explorador de Base de Datos")
    df_export = df_filtrado.drop(columns=['fecha_dt', 'timestamp'], errors='ignore')
    st.dataframe(df_export, use_container_width=True)
    
    st.markdown("---")
    
    if not df_export.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Auditoria_Camara')
        
        st.download_button(
            label="📥 Descargar Reporte en Excel",
            data=buffer.getvalue(),
            file_name=f"Auditoria_{camara_seleccionada}_{fecha_inicio.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("ℹ️ Seleccioná un rango de fechas con registros para habilitar la descarga del reporte.")