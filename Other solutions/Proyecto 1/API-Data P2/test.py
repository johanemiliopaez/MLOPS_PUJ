"""
Script de prueba: consume la API Data P2 y realiza análisis exploratorio de datos.
"""

import requests
import pandas as pd
import numpy as np

BASE_URL = "http://localhost:8080"

# Columnas del dataset Forest Cover Type (55 campos)
COLUMNS = [
    "Elevation", "Aspect", "Slope",
    "Horizontal_Distance_To_Hydrology", "Vertical_Distance_To_Hydrology",
    "Horizontal_Distance_To_Roadways", "Hillshade_9am", "Hillshade_Noon", "Hillshade_3pm",
    "Horizontal_Distance_To_Fire_Points",
    "Wilderness_Area1", "Wilderness_Area2", "Wilderness_Area3", "Wilderness_Area4",
    *[f"Soil_Type{i}" for i in range(1, 41)],
    "Cover_Type",
]


def fetch_data_from_api(groups: list[int] | None = None) -> pd.DataFrame:
    """Obtiene datos de la API para los grupos indicados y los concatena en un DataFrame."""
    if groups is None:
        groups = list(range(1, 11))

    all_rows = []
    for g in groups:
        try:
            r = requests.get(f"{BASE_URL}/data", params={"group_number": g}, timeout=30)
            r.raise_for_status()
            resp = r.json()
            all_rows.extend(resp["data"])
        except requests.RequestException as e:
            print(f"Error obteniendo grupo {g}: {e}")

    if not all_rows:
        raise ValueError("No se obtuvieron datos de la API. Verifica que esté corriendo en :8080")

    df = pd.DataFrame(all_rows, columns=COLUMNS)
    return df


def analyze(df: pd.DataFrame) -> None:
    """Realiza análisis exploratorio sobre el DataFrame."""
    print("=" * 60)
    print("ANÁLISIS EXPLORATORIO - Forest Cover Type (API Data P2)")
    print("=" * 60)

    # Tipos y conversión numérica
    numeric_cols = COLUMNS[:-1]  # Todas menos Cover_Type (target)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    print("\n1. DIMENSIONES")
    print(f"   Filas: {len(df)}, Columnas: {len(df.columns)}")

    print("\n2. VALORES FALTANTES")
    missing = df.isnull().sum()
    if missing.sum() == 0:
        print("   No hay valores faltantes.")
    else:
        print(missing[missing > 0].to_string())

    print("\n3. ESTADÍSTICAS DESCRIPTIVAS (variables numéricas principales)")
    main_cols = [
        "Elevation", "Aspect", "Slope",
        "Horizontal_Distance_To_Hydrology", "Vertical_Distance_To_Hydrology",
        "Horizontal_Distance_To_Roadways", "Hillshade_9am", "Hillshade_Noon", "Hillshade_3pm",
        "Horizontal_Distance_To_Fire_Points", "Cover_Type",
    ]
    print(df[main_cols].describe().round(2).to_string())

    print("\n4. DISTRIBUCIÓN DEL TARGET (Cover_Type)")
    print(df["Cover_Type"].value_counts().sort_index().to_string())
    print(f"\n   Proporción: {df['Cover_Type'].value_counts(normalize=True).round(3).to_string()}")

    print("\n5. CORRELACIÓN (variables numéricas principales)")
    corr = df[main_cols].corr()
    # Mostrar solo correlaciones con Cover_Type
    cover_corr = corr["Cover_Type"].drop("Cover_Type").sort_values(key=abs, ascending=False)
    print(cover_corr.round(3).to_string())

    print("\n6. WILDERNESS AREA (one-hot)")
    wilderness_cols = [f"Wilderness_Area{i}" for i in range(1, 5)]
    wilderness_counts = df[wilderness_cols].sum()
    print(wilderness_counts.to_string())


def main():
    print("Consumiendo API en", BASE_URL, "...")
    df = fetch_data_from_api()
    print(f"Registros obtenidos: {len(df)}")
    analyze(df)
    print("\n" + "=" * 60)
    print("Análisis completado.")
    print("=" * 60)


if __name__ == "__main__":
    main()
