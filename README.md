# 🌡️ Dashboard de Monitoreo y Forecasting de Estabilidad - Varifarma

Sistema integral para el monitoreo continuo, auditoría de anomalías y predicción térmica de las cámaras de estabilidad CES05 (Zona II) y CES06 (Zona IV) utilizando sensores múltiples y modelos de Machine Learning.

## 📋 Descripción del Proyecto
Esta herramienta automatiza el análisis de datos de los registradores de las cámaras de estabilidad, cruzando variables térmicas y de humedad con la bitácora de incidentes operativos (logbook). El objetivo es garantizar la integridad de los estudios *ongoing*, detectar fallas tempranas de homogeneidad espacial y proyectar el comportamiento futuro mediante Random Forest.

## ✨ Características Principales
* **Visualización Multisensor:** Monitoreo interactivo simultáneo de 4 sensores de temperatura y 4 de humedad, adaptado automáticamente a los límites regulatorios de cada Zona (II y IV).
* **Auditoría Automatizada:** Detección estricta de excursiones térmicas e higrométricas y generación de reportes listos para exportar.
* **Análisis de Homogeneidad (Puntos Críticos):** Cálculo en tiempo real del gradiente espacial (diferencia Max-Min) para anticipar fallas de recirculación de aire.
* **Modelo Predictivo (Forecasting):** Algoritmo Random Forest Regressor que proyecta la temperatura a 7, 14, 21 y 28 días, aislando fallas históricas y contemplando estacionalidad.
* **Backtesting Visual:** Interfaz gráfica para evaluar el margen de error entre las proyecciones del modelo estadístico y la realidad operativa (MAE).

## 🛠️ Stack Tecnológico
* **Lenguaje:** Python 3
* **Frontend / Dashboard:** Streamlit
* **Manipulación de Datos:** Pandas, NumPy
* **Machine Learning:** Scikit-Learn (RandomForestRegressor)
* **Visualización:** Plotly Express & Graph Objects
* **Base de Datos:** SQLite

## 📂 Estructura del Proyecto
```text
├── data/
│   ├── varifarma_monitoreo.db     # Base de datos SQLite unificada
│   └── logbook_eventos.xlsx       # Registro de incidentes y mantenimiento
├── app.py                         # Aplicación principal Streamlit (Dashboard)
├── modelo_forecasting.py          # Script de entrenamiento predictivo
├── inyectar_eventos.py            # ETL para inyectar logbook a la base de datos
└── migrar_camaras_sql.py          # ETL para ingesta de datos crudos

Instrucciones de Uso (Flujo de Trabajo)
1. Actualización de Datos Mensual:
Al recibir los nuevos archivos crudos de los data loggers, ejecutar el script de migración para actualizar la base de datos central:
python migrar_camaras_sql.py

2. Actualización de Incidentes:
Si se agregaron eventos de cortes de luz o mantenimientos al Excel, sincronizarlos con la base:
python inyectar_eventos.py

3. Regeneración del Modelo Predictivo:
Para que el Random Forest asimile los nuevos datos y proyecte el próximo mes:
python modelo_forecasting.py

4. Lanzamiento del Dashboard:
streamlit run app.py