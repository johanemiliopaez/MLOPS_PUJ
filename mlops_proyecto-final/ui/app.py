import streamlit as st
import requests
import pandas as pd
from sqlalchemy import create_engine, text
import os
#Prueba cambio
# --- CONFIGURACIÓN DE ENTORNO ---
API_URL = os.getenv("API_URL", "http://fastapi:8000")
DB_URI = os.getenv("DB_URI", "postgresql+psycopg2://mlops_user:mlops_password@postgres:5432/mlops_db")

# Inicialización del motor de base de datos para auditoría
engine = create_engine(DB_URI)

st.set_page_config(page_title="Plataforma MLOps Inmobiliaria", layout="wide")

st.title("🏢 Sistema Inteligente de Valoración Inmobiliaria - MLOps")
st.markdown("Plataforma corporativa automatizada para la estimación de precios de vivienda e historial de ciclo de vida del modelo.")

# Creación de las pestañas obligatorias (RF9)
tab_inferencia, tab_historial = st.tabs(["🎯 Realizar Inferencia", "📊 Historial de MLOps y Auditoría"])

# =====================================================================
# SECCIÓN 1: INTERFAZ DE INFERENCIA
# =====================================================================
with tab_inferencia:
    st.subheader("Estimación de Precio de Propiedades")
    st.markdown("Complete las características estructurales y geográficas de la vivienda para consultar al modelo productivo (Champion) en MLflow.")

    with st.form("real_estate_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Características Estructurales")
            bed = st.number_input("Número de Habitaciones (bed)", min_value=1.0, max_value=10.0, value=3.0, step=1.0)
            bath = st.number_input("Número de Baños (bath)", min_value=1.0, max_value=10.0, value=2.0, step=0.5)
            acre_lot = st.number_input("Tamaño del Terreno en Acres (acre lot)", min_value=0.01, max_value=100.0, value=0.25, step=0.01)
            house_size = st.number_input("Área Habitable en Pies Cuadrados (house size)", min_value=100.0, max_value=20000.0, value=1500.0, step=10.0)
            
        with col2:
            st.markdown("### Ubicación y Estado")
            status = st.selectbox("Estado de la Vivienda (status)", ["ready for sale", "ready to build"])
            city = st.selectbox("Ciudad (city)", ["Bogotá", "Tunja", "Sogamoso", "Pereira", "Medellín", "Cali"])
            state = st.selectbox("Región / Estado (state)", ["Cundinamarca", "Boyacá", "Risaralda", "Antioquia", "Valle del Cauca"])
            
            # Campos opcionales requeridos por la estructura del dataset
            brokered_by = st.number_input("ID de Agencia (brokered by)", min_value=1, value=1, step=1)
            street = st.text_input("Dirección (street)", value="Calle 100 #15-20")
            zip_code = st.text_input("Código Postal (zip code)", value="110111")

        # Botón de envío personalizado con la frase de control solicitada
        submit_button = st.form_submit_button("¡Sale Bien!")

    if submit_button:
        # Estructuración estricta del Payload según el modelo Pydantic de la API
        payload = {
            "bed": float(bed),
            "bath": float(bath),
            "acre_lot": float(acre_lot),
            "house_size": float(house_size),
            "status": status,
            "city": city,
            "state": state,
            "brokered_by": int(brokered_by),
            "street": street,
            "zip_code": zip_code
        }
        
        with st.spinner('Consultando la versión Champion en el servidor de MLflow...'):
            try:
                response = requests.post(f"{API_URL}/predict", json=payload, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    st.success("### 🏡 Valoración Estimada con Éxito")
                    # Mostrar el precio estimado con formato de moneda claro y legible
                    st.metric(
                        label="Precio Estimado de la Propiedad", 
                        value=f"${result['estimated_price']:,.2f} USD"
                    )
                    
                    # Despliegue de metadatos técnicos de trazabilidad (RF8 y RF9)
                    col_meta1, col_meta2, col_meta3 = st.columns(3)
                    with col_meta1:
                        st.caption(f"🆔 **ID de Petición:**\n{result['request_id']}")
                    with col_meta2:
                        st.caption(f"🧠 **Modelo Activo (Run ID):**\n{result['model_used']}")
                    with col_meta3:
                        st.caption(f"⏱️ **Latencia de Inferencia:**\n{result['processing_time_ms']} ms")
                        
                elif response.status_code == 503:
                    st.warning("⚠️ **Servicio Temporalmente No Disponible:** El modelo central aún no se ha entrenado o no está registrado con el alias 'champion' en MLflow. Verifique el estado de Airflow.")
                else:
                    st.error(f"❌ Error devuelto por la API ({response.status_code}): {response.text}")
                    
            except Exception as e:
                st.error(f"❌ Error crítico de conexión con el backend de FastAPI: {e}")

# =====================================================================
# SECCIÓN 2: HISTORIAL DE ENTRENAMIENTO Y DESPLIEGUE (AUDITORÍA)
# =====================================================================
with tab_historial:
    st.subheader("Bitácora de Decisiones Automáticas y Trazabilidad de Ciclo de Vida")
    st.markdown("Esta sección audita el comportamiento autónomo del orquestador. Muestra las decisiones tomadas por Airflow para cada lote analizado basándose en las métricas estadísticas calculadas.")

    if st.button("🔄 Actualizar Historial de Eventos"):
        st.rerun()

    try:
        # Consulta directa a la tabla de control alimentada por la tarea 18 del DAG
        query = """
            SELECT 
                batch_id as "Identificador del Lote",
                execution_date as "Fecha de Ejecución",
                status as "Resultado del Pipeline",
                reason as "Justificación Técnica",
                candidate_mae as "MAE Candidato",
                champion_mae as "MAE Champion"
            FROM pipeline_history
            ORDER BY execution_date DESC;
        """
        df_history = pd.read_sql(query, con=engine)
        
        if df_history.empty:
            st.info("No se registran eventos de orquestación en la base de datos todavía. Ejecute el DAG en Airflow para procesar los primeros lotes.")
        else:
            # Resumen analítico rápido para el evaluador
            total_batches = len(df_history)
            promoted_count = len(df_history[df_history["Resultado del Pipeline"] == "PROMOTED"])
            skipped_count = len(df_history[df_history["Resultado del Pipeline"] == "SKIPPED"])
            rejected_count = len(df_history[df_history["Resultado del Pipeline"] == "REJECTED"])
            
            col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
            with col_metric1:
                st.metric("Lotes Evaluados", total_batches)
            with col_metric2:
                st.metric("Modelos Promovidos", promoted_count)
            with col_metric3:
                st.metric("Modelos Rechazados", rejected_count)
            with col_metric4:
                st.metric("Entrenamientos Omitidos", skipped_count)
                
            st.divider()
            
            # Tabla interactiva con el historial exacto solicitado por el profesor
            st.dataframe(
                df_history, 
                use_container_width=True,
                column_config={
                    "Fecha de Ejecución": st.column_config.DatetimeColumn(format="DD/MM/YYYY, HH:mm"),
                    "MAE Candidato": st.column_config.NumberColumn(format="$%.2f"),
                    "MAE Champion": st.column_config.NumberColumn(format="$%.2f")
                }
            )
            
            # Notas explicativas de la lógica del sistema para la sustentación
            st.info("""
            💡 **Guía de interpretación de resultados:**
            * **PROMOTED:** El lote presentó alta variabilidad (Data Drift detectado por Evidently), se ejecutó el entrenamiento y el modelo candidato redujo el error (MAE) frente al modelo previo en al menos un 2%.
            * **REJECTED:** Se detectó variabilidad y se entrenó un candidato, pero sus métricas no superaron el rendimiento del modelo productivo actual. Se conservó en MLflow como experimento pero no se actualizó el alias.
            * **SKIPPED:** El lote analizado mantenía una distribución estadística estable respecto al histórico. El sistema omitió el gasto computacional de entrenamiento para optimizar recursos.
            """)
            
    except Exception as e:
        st.error(f"Error al leer la tabla de auditoría en PostgreSQL: {e}")
        st.caption("Asegúrese de que el script SQL de inicialización haya creado la tabla de forma correcta y que Airflow haya realizado al menos una ejecución completa.")