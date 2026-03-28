from locust import HttpUser, task, between

class PenguinsInferenceUser(HttpUser):
    wait_time = between(1, 2) # Espera entre 1 y 2 segundos

    @task
    def predict_rf(self):
        self.client.post("/predict", json={
            "features": [39.1, 18.7, 181, 3750, 0, 0, 2007]
        })
        