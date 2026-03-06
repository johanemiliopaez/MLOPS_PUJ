-- Tabla data_raw: almacena los datos obtenidos de la API (api-data-p2)
-- 14 campos VARCHAR(255) + timestamp de inserción

CREATE TABLE IF NOT EXISTS data_raw (
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    group_number INT,
    elevation VARCHAR(255),
    aspect VARCHAR(255),
    slope VARCHAR(255),
    horizontal_distance_to_hydrology VARCHAR(255),
    vertical_distance_to_hydrology VARCHAR(255),
    horizontal_distance_to_roadways VARCHAR(255),
    hillshade_9am VARCHAR(255),
    hillshade_noon VARCHAR(255),
    hillshade_3pm VARCHAR(255),
    horizontal_distance_to_fire_points VARCHAR(255),
    wilderness_area VARCHAR(255),
    soil_type VARCHAR(255),
    cover_type VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS data_prepared (
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    group_number INT,
    elevation VARCHAR(255),
    aspect VARCHAR(255),
    slope VARCHAR(255),
    horizontal_distance_to_hydrology VARCHAR(255),
    vertical_distance_to_hydrology VARCHAR(255),
    horizontal_distance_to_roadways VARCHAR(255),
    hillshade_9am VARCHAR(255),
    hillshade_noon VARCHAR(255),
    hillshade_3pm VARCHAR(255),
    horizontal_distance_to_fire_points VARCHAR(255),
    wilderness_area VARCHAR(255),
    soil_type VARCHAR(255),
    cover_type VARCHAR(255),
    data_type VARCHAR(100)
);
