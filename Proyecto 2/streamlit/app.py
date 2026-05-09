import json
import os

import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://api:8000")
SAMPLE_PAYLOAD = {
    "race": "Caucasian",
    "gender": "Female",
    "age": "[60-70)",
    "admission_type_id": 1,
    "discharge_disposition_id": 1,
    "admission_source_id": 7,
    "time_in_hospital": 4,
    "num_lab_procedures": 44,
    "num_procedures": 1,
    "num_medications": 11,
    "number_outpatient": 0,
    "number_emergency": 0,
    "number_inpatient": 0,
    "diag_1": "250.83",
    "diag_2": "276",
    "diag_3": "414",
    "A1Cresult": ">7",
    "insulin": "Up",
    "change": "Ch",
    "diabetesMed": "Yes",
}


st.set_page_config(page_title="Proyecto 2 - Diabetes UI", page_icon=":bar_chart:", layout="wide")
st.title("Proyecto 2 - Interfaz de Inferencia")
st.caption("La interfaz consume exclusivamente la API desplegada en Kubernetes.")

if "payload_editor" not in st.session_state:
    st.session_state.payload_editor = json.dumps(SAMPLE_PAYLOAD, indent=2)

left, right = st.columns([2, 1])

with right:
    st.subheader("Acciones")
    if st.button("Cargar ejemplo"):
        st.session_state.payload_editor = json.dumps(SAMPLE_PAYLOAD, indent=2)
    if st.button("Consultar modelo"):
        try:
            model_info = requests.get(f"{API_URL}/model-info", timeout=30)
            model_info.raise_for_status()
            st.json(model_info.json())
        except Exception as exc:
            st.error(f"No se pudo consultar /model-info: {exc}")

with left:
    st.subheader("Payload JSON")
    payload_text = st.text_area(
        "Features",
        key="payload_editor",
        height=420,
        help="Edita el JSON antes de enviarlo a /predict",
    )

    if st.button("Enviar predicción", type="primary"):
        try:
            payload = json.loads(payload_text)
            response = requests.post(f"{API_URL}/predict", json={"features": payload}, timeout=60)
            response.raise_for_status()
            st.success("Predicción generada")
            st.json(response.json())
        except json.JSONDecodeError as exc:
            st.error(f"El JSON no es válido: {exc}")
        except requests.HTTPError:
            st.error(f"Error de la API: {response.text}")
        except Exception as exc:
            st.error(f"No se pudo completar la inferencia: {exc}")
