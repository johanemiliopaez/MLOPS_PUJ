from locust import HttpUser, task, between
import random

STATUSES = ["ready for sale", "ready to build"]
CITIES = ["Bogotá", "Tunja", "Sogamoso", "Pereira", "Medellín", "Cali"]
STATES = ["Cundinamarca", "Boyacá", "Risaralda", "Antioquia", "Valle del Cauca"]


class RealEstatePredictorUser(HttpUser):
    wait_time = between(1, 2)

    @task(5)
    def predict_price(self):
        payload = {
            "bed": random.randint(1, 6),
            "bath": random.randint(1, 5),
            "acre_lot": round(random.uniform(0.05, 2.5), 2),
            "house_size": random.randint(500, 4000),
            "status": random.choice(STATUSES),
            "city": random.choice(CITIES),
            "state": random.choice(STATES),
            "brokered_by": random.randint(1, 50),
            "street": f"Calle {random.randint(1, 120)} # {random.randint(1, 50)}-{random.randint(1, 50)}",
            "zip_code": str(random.randint(100000, 999999))
        }

        with self.client.post("/predict", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Falló la predicción: {response.text}")

    @task(1)
    def health_check(self):
        self.client.get("/health")