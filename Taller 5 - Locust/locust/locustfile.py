"""
Pruebas de carga Locust contra la API Penguins (MLflow).
Prioriza POST /predict sobre GET /health.
"""
from locust import HttpUser, task, between

# Payload Penguins: bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g,
# island_encoded, sex_encoded, year
PENGUINS_FEATURES = [39.1, 18.7, 181, 3750, 0, 0, 2007]


class PenguinsInferenciaUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(10)
    def predict(self):
        self.client.post(
            "/predict",
            json={"features": PENGUINS_FEATURES},
            headers={"Content-Type": "application/json"},
            name="/predict",
        )

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")
