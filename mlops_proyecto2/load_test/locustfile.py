from locust import HttpUser, task, between
import random

class DiabetesPredictorUser(HttpUser):
    # Simula un tiempo de espera entre 1 y 2 segundos entre cada acción del usuario
    wait_time = between(1, 2)

    @task(5)
    def predict_readmission(self):
        # Payload estructurado igual que el modelo PatientData de la API
        payload = {
            "age": random.choice(["[40-50)", "[50-60)", "[60-70)", "[70-80)", "[80-90)"]),
            "time_in_hospital": random.randint(1, 14),
            "num_lab_procedures": random.randint(1, 100),
            "num_procedures": random.randint(0, 6),
            "num_medications": random.randint(1, 50),
            "number_outpatient": random.randint(0, 5),
            "number_emergency": random.randint(0, 5),
            "number_inpatient": random.randint(0, 5),
            "number_diagnoses": random.randint(1, 16),
            "change": random.choice(["No", "Ch"]),
            "diabetesMed": random.choice(["No", "Yes"])
        }
        
        # Al usar el parámetro 'json', Locust añade automáticamente el header 
        # 'Content-Type: application/json' y serializa el dict
        with self.client.post("/predict", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Falló la predicción: {response.text}")

    @task(1)
    def health_check(self):
        self.client.get("/health")