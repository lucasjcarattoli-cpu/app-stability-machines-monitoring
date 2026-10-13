import sqlite3
import pandas as pd
from pathlib import Path

nombre_db = "data/varifarma_monitoreo.db"
print(f"Conectando a la base de datos SQLite: {nombre_db}...")
conexion = sqlite3.connect(nombre_db)
cursor = conexion.cursor()

# 1. Reseteo automático: Borramos la tabla anterior para reconstruir todo el histórico unificado
cursor.execute("DROP TABLE IF EXISTS registros_camaras;")
conexion.commit()
print("🧹 Tabla 'registros_camaras' reiniciada para consolidación total.\n")

def procesar_archivo(path_archivo, nombre_camara, es_nuevo_formato=False):
    path = Path(path_archivo)
    if not path.exists():
        print(f"❌ Archivo no encontrado: {path}")
        return
    
    if path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Formato no soportado: {path.suffix}")
        
    # Limpieza específica para el archivo de CES05 de mar-oct 2026 (columna (ms))
    if '(ms)' in df.columns:
        df = df.drop(columns=['(ms)'])
    if 'TIMESTAMP' in df.columns and 'DATE' in df.columns:
        df = df.rename(columns={'TIMESTAMP': 'DATE', 'DATE': 'TIME'})
        
    # Adaptador para los nombres de los sensores de la CES06
    if es_nuevo_formato:
        mapeo_columnas = {
            'CES001TEMP': 'CES04TEMP1', 'CES001HUM': 'CES04HUM1',
            'CES002TEMP': 'CES04TEMP2', 'CES002HUM': 'CES04HUM2',
            'CES003TEMP': 'CES04-TEMP3', 'CES003HUM': 'CES04-HUM3', 
            'CES004TEMP': 'CES04TEMP4', 'CES004HUM': 'CES04HUM4'
        }
        df = df.rename(columns=mapeo_columnas)
        if 'TIME' in df.columns:
            df['TIME'] = df['TIME'].astype(str).str.strip().str[:8]

    df['camara'] = nombre_camara

    # Truco anti-errores: filtramos las columnas para que coincidan con la tabla si ya existe
    cursor.execute("PRAGMA table_info(registros_camaras)")
    columnas_db = [info[1] for info in cursor.fetchall()]
    
    if columnas_db:
        columnas_comunes = [col for col in df.columns if col in columnas_db]
        df = df[columnas_comunes]

    print(f"📂 Procesando {path.name} [{nombre_camara}]... Dimensiones ajustadas: {df.shape}")
    
    df.to_sql('temp_registros', conexion, if_exists='replace', index=False)
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registros_camaras AS 
        SELECT * FROM temp_registros WHERE 1=0;
    ''')
    
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_camara_fecha_hora 
        ON registros_camaras(camara, DATE, TIME);
    ''')
    
    columnas_temp = ", ".join([f'"{col}"' for col in df.columns])
    cursor.execute(f'''
        INSERT OR IGNORE INTO registros_camaras ({columnas_temp})
        SELECT {columnas_temp} FROM temp_registros
    ''')
    
    filas_nuevas = cursor.rowcount
    cursor.execute('DROP TABLE temp_registros')
    conexion.commit()
    
    print(f"    ✅ ¡Inyección exitosa! Se agregaron {filas_nuevas} registros NUEVOS a la base.\n")


# --- EJECUCIÓN DE LA MIGRACIÓN HISTÓRICA UNIFICADA ---

# 1. Cámara CES06
procesar_archivo('data/camara_ces06/sep25-mar-26.xlsx', 'CES06')
procesar_archivo('data/camara_ces06/CES006_mar-oct_26.xlsx', 'CES06', es_nuevo_formato=True)

# 2. Cámara CES05
procesar_archivo('data/camara_ces05/CES005 sep25 - mar26.xlsx', 'CES05')
procesar_archivo('data/camara_ces05/marzo-sept 1.xlsx', 'CES05')
procesar_archivo('data/camara_ces05/mar - oct 2026.xlsx', 'CES05', es_nuevo_formato=True)


# --- VALIDACIONES FINALES ---
cursor.execute("SELECT COUNT(*) FROM registros_camaras;")
total_final = cursor.fetchone()[0]

cursor.execute("""
    SELECT MIN(DATE(SUBSTR(DATE,7,4) || '-' || SUBSTR(DATE,4,2) || '-' || SUBSTR(DATE,1,2))), 
           MAX(DATE(SUBSTR(DATE,7,4) || '-' || SUBSTR(DATE,4,2) || '-' || SUBSTR(DATE,1,2))) 
    FROM registros_camaras;
""")
rango_real = cursor.fetchone()

conexion.close()

print(f"📅 Rango temporal real cubierto: {rango_real[0]} al {rango_real[1]}")
print(f"🎉 ¡Migración completa y unificada de ambas cámaras!")
print(f"📊 Total exacto de registros en la base: {total_final}")