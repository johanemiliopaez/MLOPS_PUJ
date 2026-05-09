import json
import os

from locust import HttpUser, between, task


SAMPLE_PAYLOAD = {
    "features": {
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
}


class InferenceUser(HttpUser):
    wait_time = between(1, 3)
    host = os.getenv("LOCUST_HOST", "http://api:8000")

    @task(1)
    def predict(self):
        self.client.post("/predict", json=SAMPLE_PAYLOAD)

    @task(1)
    def health(self):
        self.client.get("/health")
