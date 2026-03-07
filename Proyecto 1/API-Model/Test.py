"""
Test: 100 requests al API /predict y consolidación de respuestas.
"""

import requests
import random
import time
from collections import Counter

API_URL = "http://localhost:8989/predict"
NUM_REQUESTS = 1000

WILDERNESS_AREAS = ["Rawah", "Neota", "Commanche", "Cache"]
SOIL_TYPES = ["C2702", "C2703", "C2704", "C2705", "C7744", "C7745", "C7746", "C7755"]

# Nombres de las clases Cover Type (0-6)
COVER_TYPE_NAMES = {
    0: "Spruce/Fir",
    1: "Lodgepole Pine",
    2: "Ponderosa Pine",
    3: "Cottonwood/Willow",
    4: "Aspen",
    5: "Douglas-fir",
    6: "Krummholz",
}


def get_random_instance():
    """Genera una instancia aleatoria válida para el modelo."""
    return {
        "elevation": random.randint(1800, 4000),
        "aspect": random.randint(0, 360),
        "slope": random.randint(0, 66),
        "horizontal_distance_to_hydrology": random.randint(0, 1500),
        "vertical_distance_to_hydrology": random.randint(-200, 200),
        "horizontal_distance_to_roadways": random.randint(0, 7000),
        "hillshade_9am": random.randint(0, 255),
        "hillshade_noon": random.randint(0, 255),
        "hillshade_3pm": random.randint(0, 255),
        "horizontal_distance_to_fire_points": random.randint(0, 7000),
        "wilderness_area": random.choice(WILDERNESS_AREAS),
        "soil_type": random.choice(SOIL_TYPES),
    }


def run_test():
    """Ejecuta 100 requests y consolida resultados."""
    results = []
    latencies = []
    errors = []

    print(f"Enviando {NUM_REQUESTS} requests a {API_URL}...")

    for i in range(NUM_REQUESTS):
        payload = {"instances": [get_random_instance()]}
        start = time.perf_counter()
        try:
            resp = requests.post(API_URL, json=payload, timeout=10)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

            if resp.status_code == 200:
                data = resp.json()
                preds = data.get("predictions", [])
                if preds:
                    results.append(preds[0])
            else:
                errors.append({"request": i + 1, "status": resp.status_code, "body": resp.text[:200]})
        except Exception as e:
            errors.append({"request": i + 1, "error": str(e)})

    # Consolidación
    print("\n" + "=" * 50)
    print("RESUMEN DE PRUEBAS")
    print("=" * 50)

    print(f"\nTotal requests: {NUM_REQUESTS}")
    print(f"Exitosos: {len(results)}")
    print(f"Errores: {len(errors)}")

    if results:
        pred_counts = Counter(results)
        print("\nDistribución de predicciones:")
        print("-" * 40)
        print(f"{'Nombre':<25} {'Cantidad':>10}")
        print("-" * 40)
        for cls in sorted(pred_counts.keys()):
            name = COVER_TYPE_NAMES.get(cls, f"Clase {cls}")
            count = pred_counts[cls]
            print(f"{name:<25} {count:>10}")
        print("-" * 40)

    if latencies:
        print(f"\nLatencia (ms): min={min(latencies):.1f}, max={max(latencies):.1f}, avg={sum(latencies)/len(latencies):.1f}")

    if errors:
        print(f"\nErrores ({len(errors)}):")
        for e in errors[:5]:
            print(f"  - {e}")
        if len(errors) > 5:
            print(f"  ... y {len(errors) - 5} más")

    return {"results": results, "latencies": latencies, "errors": errors}


if __name__ == "__main__":
    run_test()
