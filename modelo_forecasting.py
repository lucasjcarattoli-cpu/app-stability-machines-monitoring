import pandas as pd
import sqlite3
import numpy as np
from datetime import timedelta, datetime
from sklearn.ensemble import RandomForestRegressor

print("--- INICIANDO MODELO DE FORECASTING DESDE BASE DE DATOS (CES05 y CES06) ---")

db_path = "data/varifarma_monitoreo.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Recreamos la tabla de control con la columna 'camara' para aislar las predicciones
cursor.execute('DROP TABLE IF EXISTS predicciones_control')
cursor.execute('''
    CREATE TABLE predicciones_control (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camara TEXT,
        fecha_generacion TEXT,
        horizonte_dias INTEGER,
        fecha_objetivo TEXT,
        temperatura_predicha REAL,
        temperatura_real REAL,
        estado TEXT
    )
''')
conn.commit()

# Lista de cámaras a procesar
camaras = ["CES05", "CES06"]
fecha_generacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for camara_id in camaras:
    print(f"\n-----------------------------------------")
    print(f"⚙️ Procesando forecasting para: {camara_id}")
    print(f"-----------------------------------------")

    # 2. Consultamos y agrupamos los datos diarios directamente desde la base de datos para esta cámara
    # (Nota: Asumimos que la columna de temperatura principal se llama CES04TEMP1 o podés ajustarla si varía)
    query_diaria = f"""
        SELECT DATE, AVG(CES04TEMP1) as temp_mean
        FROM registros_camaras
        WHERE TRIM(camara) = '{camara_id}'
        GROUP BY DATE
    """
    df_diario = pd.read_sql(query_diaria, conn)
    
    if df_diario.empty:
        print(f"⚠️ No se encontraron registros para la cámara {camara_id}. Saltando...")
        continue

    # Convertimos las fechas de forma robusta
    df_diario['fecha_dt'] = pd.to_datetime(df_diario['DATE'], format='mixed', dayfirst=True, errors='coerce').dt.normalize()
    df_diario = df_diario.dropna(subset=['fecha_dt']).sort_values('fecha_dt').reset_index(drop=True)
    df_diario['timestamp'] = df_diario['fecha_dt']

    ultima_fecha = df_diario['timestamp'].max()
    print(f"📅 Última fecha real ({camara_id}): {ultima_fecha.strftime('%Y-%m-%d')}")

    # 3. Traemos la bitácora de incidentes específica de esta cámara
    query_ev = f"SELECT fecha, categoria FROM logbook_eventos WHERE TRIM(camara) = '{camara_id}'"
    df_ev = pd.read_sql(query_ev, conn)
    df_ev['fecha_dt'] = pd.to_datetime(df_ev['fecha'].astype(str).str.strip(), format='mixed', dayfirst=True, errors='coerce')

    # 4. Cruzamos los datos para limpiar la serie
    df_modelo = pd.merge(df_diario, df_ev, on='fecha_dt', how='left')
    df_modelo['categoria'] = df_modelo['categoria'].fillna('Normal')

    # --- NIVEL 1: FILTRADO INTELIGENTE ---
    filtro_fallas = df_modelo['categoria'].str.lower().str.contains('falla')
    df_limpio = df_modelo[~filtro_fallas].copy()
    print(f"🧹 Se eliminaron {filtro_fallas.sum()} días de fallas críticas para {camara_id}.")

    if len(df_limpio) < 10:
        print(f"⚠️ Pocos datos limpios para entrenar en {camara_id}. Se omite.")
        continue

    # --- NIVEL 2: INGENIERÍA DE CARACTERÍSTICAS ---
    df_limpio['dias_desde_inicio'] = (df_limpio['timestamp'] - df_limpio['timestamp'].min()).dt.days
    df_limpio['dia_semana'] = df_limpio['timestamp'].dt.dayofweek
    df_limpio['mes'] = df_limpio['timestamp'].dt.month
    df_limpio['flag_mantenimiento'] = np.where(df_limpio['categoria'].str.lower().str.contains('mantenimiento'), 1, 0)
    df_limpio['flag_apertura'] = np.where(df_limpio['categoria'].str.lower().str.contains('apertura'), 1, 0)

    X = df_limpio[['dias_desde_inicio', 'dia_semana', 'mes', 'flag_mantenimiento', 'flag_apertura']]
    y = df_limpio['temp_mean']

    # 5. Entrenamos el modelo Random Forest
    modelo = RandomForestRegressor(n_estimators=100, random_state=42)
    modelo.fit(X, y)
    print(f"✅ Modelo entrenado con éxito para {camara_id}.")

    # 6. Generamos proyecciones (7, 14, 21 y 28 días)
    ultimo_dia_num = df_limpio['dias_desde_inicio'].max()
    horizontes = [7, 14, 21, 28]

    for h in horizontes:
        fecha_futura = ultima_fecha + timedelta(days=h)
        
        X_futuro = pd.DataFrame([{
            'dias_desde_inicio': ultimo_dia_num + h,
            'dia_semana': fecha_futura.dayofweek,
            'mes': fecha_futura.month,
            'flag_mantenimiento': 0,
            'flag_apertura': 0
        }])
        
        prediccion = modelo.predict(X_futuro)[0]
        print(f"   • [{camara_id}] +{h} días ({fecha_futura.strftime('%Y-%m-%d')}): Temp esperada = {prediccion:.2f} °C")
        
        cursor.execute('''
            INSERT INTO predicciones_control (camara, fecha_generacion, horizonte_dias, fecha_objetivo, temperatura_predicha, estado)
            VALUES (?, ?, ?, ?, ?, 'Pendiente')
        ''', (camara_id, fecha_generacion, h, fecha_futura.strftime('%Y-%m-%d'), float(prediccion)))

conn.commit()
conn.close()

print(f"\n💾 ¡Procesamiento completo! Proyecciones generadas y separadas para CES05 y CES06.")