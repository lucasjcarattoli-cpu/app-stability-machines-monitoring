import sqlite3
import pandas as pd
from pathlib import Path

# Nombre de tu archivo consolidado (asegurate de que se llame así o ajustá el nombre)
archivo_eventos = "data/logbook_eventos.xlsx" # O .csv según lo hayas guardado

if not Path(archivo_eventos).exists():
    # Intentamos buscar si está como csv por las dudas
    archivo_eventos = "data/logbook_eventos.csv"

print(f"📥 Leyendo los registros del logbook desde: {archivo_eventos}")

if archivo_eventos.endswith('.xlsx'):
    df_eventos = pd.read_excel(archivo_eventos)
else:
    df_eventos = pd.read_csv(archivo_eventos)

# Limpiar nombres de columnas por si tienen espacios
df_eventos.columns = df_eventos.columns.str.strip().str.upper()

print(f"📊 Se leyeron {len(df_eventos)} eventos históricos.")

# Conectar a la base de datos SQLite
db_path = "data/varifarma_monitoreo.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Crear la tabla de eventos si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS logbook_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        hora TEXT,
        camara TEXT,
        categoria TEXT,
        descripcion TEXT
    )
''')

# 2. Opcional: Limpiar tabla anterior para evitar duplicados si volvés a correr el script
cursor.execute('DELETE FROM logbook_eventos')

# 3. Insertar los registros uno por uno
for _, row in df_eventos.iterrows():
    fecha = str(row.get('FECHA', '')).strip()
    hora = str(row.get('HORA', '')).strip()
    if hora.lower() == 'nan': hora = ''
    
    camara = str(row.get('CAMARA', 'CES05')).strip()
    categoria = str(row.get('CATEGORIA', 'General')).strip()
    descripcion = str(row.get('DESCRIPCION', '')).strip()

    cursor.execute('''
        INSERT INTO logbook_eventos (fecha, hora, camara, categoria, descripcion)
        VALUES (?, ?, ?, ?, ?)
    ''', (fecha, hora, camara, categoria, descripcion))

conn.commit()
conn.close()

print("✅ ¡Eventos del logbook inyectados exitosamente en la base de datos SQLite!")