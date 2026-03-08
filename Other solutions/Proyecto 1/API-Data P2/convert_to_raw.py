"""
Convierte covertype.csv (55 columnas one-hot) a formato crudo (13 columnas).
Basado en: https://github.com/GoogleCloudPlatform/mlops-on-gcp/blob/master/datasets/covertype/wrangle/prepare.ipynb
"""

import csv
import os

# Rutas
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
INPUT_CSV = os.path.join(DATA_DIR, "covertype.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "covertype_raw.csv")

# Mapeo Wilderness_Area (one-hot cols 10-13 -> Rawah, Neota, Commanche, Cache)
WILDERNESS_CODES = ["Rawah", "Neota", "Commanche", "Cache"]

# Mapeo Soil_Type (one-hot cols 14-53 -> códigos C2702, C2703, ...)
SOIL_CODES = [
    "C2702", "C2703", "C2704", "C2705", "C2706", "C2717", "C3501", "C3502",
    "C4201", "C4703", "C4704", "C4744", "C4758", "C5101", "C5151", "C6101",
    "C6102", "C6731", "C7101", "C7102", "C7103", "C7201", "C7202", "C7700",
    "C7701", "C7702", "C7709", "C7710", "C7745", "C7746", "C7755", "C7756",
    "C7757", "C7790", "C8703", "C8707", "C8708", "C8771", "C8772", "C8776",
]

NUMERIC_COLS = [
    "Elevation", "Aspect", "Slope",
    "Horizontal_Distance_To_Hydrology", "Vertical_Distance_To_Hydrology",
    "Horizontal_Distance_To_Roadways", "Hillshade_9am", "Hillshade_Noon",
    "Hillshade_3pm", "Horizontal_Distance_To_Fire_Points",
]
OUTPUT_HEADER = NUMERIC_COLS + ["Wilderness_Area", "Soil_Type", "Cover_Type"]


def onehot_to_wilderness(row: list) -> str:
    """Convierte columnas Wilderness_Area1-4 (one-hot) a valor categórico."""
    for i in range(4):
        if row[10 + i] in ("1", 1):
            return WILDERNESS_CODES[i]
    return WILDERNESS_CODES[0]


def onehot_to_soil(row: list) -> str:
    """Convierte columnas Soil_Type1-40 (one-hot) a código categórico."""
    for i in range(40):
        if row[14 + i] in ("1", 1):
            return SOIL_CODES[i]
    return SOIL_CODES[0]


def main():
    print(f"Leyendo {INPUT_CSV}...")
    count = 0

    with open(INPUT_CSV, newline="", encoding="utf-8") as fin:
        reader = csv.reader(fin)
        header = next(reader)
        if len(header) != 55:
            raise ValueError(f"Se esperaban 55 columnas, se encontraron {len(header)}")

        print("Convirtiendo one-hot a formato crudo...")

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fout:
            writer = csv.writer(fout)
            writer.writerow(OUTPUT_HEADER)

            for row in reader:
                numeric = row[:10]
                wilderness = onehot_to_wilderness(row)
                soil = onehot_to_soil(row)
                cover_type = row[54]
                writer.writerow(numeric + [wilderness, soil, cover_type])
                count += 1

                if count % 100000 == 0:
                    print(f"  Procesadas {count} filas...")

    print(f"Guardado: {OUTPUT_CSV}")
    print(f"Filas: {count}, Columnas: 13")


if __name__ == "__main__":
    main()
