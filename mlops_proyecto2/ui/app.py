import streamlit as st
import requests
import json

# URL interna del contenedor de FastAPI
API_URL = "http://fastapi:8000"

st.set_page_config(page_title="Predictor de Diabetes", layout="centered")
st.title("🏥 Predictor de Readmisión - Diabetes")
st.markdown("Ingresa los datos del paciente para predecir si será readmitido.")

# Formulario de entrada de datos
with st.form("patient_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        age = st.selectbox("Edad", ["[0-10)", "[10-20)", "[20-30)", "[30-40)", "[40-50)", "[50-60)", "[60-70)", "[70-80)", "[80-90)", "[90-100)"])
        time_in_hospital = st.number_input("Días en el hospital", min_value=1, max_value=14, value=3)
        num_lab_procedures = st.number_input("Procedimientos de laboratorio", min_value=1, value=40)
        num_procedures = st.number_input("Procedimientos médicos", min_value=0, value=1)
        num_medications = st.number_input("Número de medicamentos", min_value=1, value=15)
        
    with col2:
        number_outpatient = st.number_input("Visitas ambulatorias", min_value=0, value=0)
        number_emergency = st.number_input("Visitas de emergencia", min_value=0, value=0)
        number_inpatient = st.number_input("Visitas hospitalización previa", min_value=0, value=0)
        number_diagnoses = st.number_input("Número de diagnósticos", min_value=1, value=5)
        change = st.radio("¿Hubo cambio en medicación?", ["No", "Ch"])
        diabetesMed = st.radio("¿Se prescribió medicación para diabetes?", ["No", "Yes"])

    submit_button = st.form_submit_button("Realizar Predicción")

if submit_button:
    # Empaquetar los datos para la API
    payload = {
        "age": age,
        "time_in_hospital": time_in_hospital,
        "num_lab_procedures": num_lab_procedures,
        "num_procedures": num_procedures,
        "num_medications": num_medications,
        "number_outpatient": number_outpatient,
        "number_emergency": number_emergency,
        "number_inpatient": number_inpatient,
        "number_diagnoses": number_diagnoses,
        "change": change,
        "diabetesMed": diabetesMed
    }
    
    with st.spinner('Consultando al modelo Champion en MLflow...'):
        try:
            # Hacer petición POST a FastAPI
            response = requests.post(f"{API_URL}/predict", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                
                st.divider()
                st.subheader("📊 Resultado de la Predicción")
                
                if result["prediction"] == 1:
                    st.error("⚠️ Alto Riesgo: Es probable que el paciente sea readmitido.")
                else:
                    st.success("✅ Bajo Riesgo: Es poco probable que el paciente sea readmitido.")
                    
                st.caption(f"⏱️ Tiempo de procesamiento: {result['processing_time_ms']} ms")
                st.caption(f"🧠 Modelo utilizado (Run ID): {result['model_used']}")
                
            else:
                st.error(f"Error de la API: {response.text}")
                
        except Exception as e:
            st.error(f"Error de conexión con la API: {e}")