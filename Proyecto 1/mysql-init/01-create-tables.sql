-- Scripts de inicialización MySQL - PROYECTO-1
-- Define el esquema antes de que el DAG de Airflow ejecute.
-- Garantiza tablas estables aunque el pipeline falle en las primeras ejecuciones.

USE ml_data;

-- tabla_raw: datos crudos de la API (strings)
CREATE TABLE IF NOT EXISTS tabla_raw (
    Elevation VARCHAR(255),
    Aspect VARCHAR(255),
    Slope VARCHAR(255),
    Horizontal_Distance_To_Hydrology VARCHAR(255),
    Vertical_Distance_To_Hydrology VARCHAR(255),
    Horizontal_Distance_To_Roadways VARCHAR(255),
    Hillshade_9am VARCHAR(255),
    Hillshade_Noon VARCHAR(255),
    Hillshade_3pm VARCHAR(255),
    Horizontal_Distance_To_Fire_Points VARCHAR(255),
    Wilderness_Area VARCHAR(255),
    Soil_Type VARCHAR(255),
    Cover_Type VARCHAR(255)
);

-- tabla_clean: datos limpios (tras limpiar_datos)
CREATE TABLE IF NOT EXISTS tabla_clean (
    Elevation VARCHAR(255),
    Aspect VARCHAR(255),
    Slope VARCHAR(255),
    Horizontal_Distance_To_Hydrology VARCHAR(255),
    Vertical_Distance_To_Hydrology VARCHAR(255),
    Horizontal_Distance_To_Roadways VARCHAR(255),
    Hillshade_9am VARCHAR(255),
    Hillshade_Noon VARCHAR(255),
    Hillshade_3pm VARCHAR(255),
    Horizontal_Distance_To_Fire_Points VARCHAR(255),
    Wilderness_Area VARCHAR(255),
    Soil_Type VARCHAR(255),
    Cover_Type VARCHAR(255)
);

-- tabla_procesada: datos codificados (tras procesar_y_codificar)
CREATE TABLE IF NOT EXISTS tabla_procesada (
    Elevation VARCHAR(255),
    Aspect VARCHAR(255),
    Slope VARCHAR(255),
    Horizontal_Distance_To_Hydrology VARCHAR(255),
    Vertical_Distance_To_Hydrology VARCHAR(255),
    Horizontal_Distance_To_Roadways VARCHAR(255),
    Hillshade_9am VARCHAR(255),
    Hillshade_Noon VARCHAR(255),
    Hillshade_3pm VARCHAR(255),
    Horizontal_Distance_To_Fire_Points VARCHAR(255),
    Wilderness_Area VARCHAR(255),
    Soil_Type VARCHAR(255),
    Cover_Type VARCHAR(255)
);

-- tabla_train: conjunto de entrenamiento (80%)
CREATE TABLE IF NOT EXISTS tabla_train (
    Elevation VARCHAR(255),
    Aspect VARCHAR(255),
    Slope VARCHAR(255),
    Horizontal_Distance_To_Hydrology VARCHAR(255),
    Vertical_Distance_To_Hydrology VARCHAR(255),
    Horizontal_Distance_To_Roadways VARCHAR(255),
    Hillshade_9am VARCHAR(255),
    Hillshade_Noon VARCHAR(255),
    Hillshade_3pm VARCHAR(255),
    Horizontal_Distance_To_Fire_Points VARCHAR(255),
    Wilderness_Area VARCHAR(255),
    Soil_Type VARCHAR(255),
    Cover_Type VARCHAR(255)
);

-- tabla_test: conjunto de prueba (20%)
CREATE TABLE IF NOT EXISTS tabla_test (
    Elevation VARCHAR(255),
    Aspect VARCHAR(255),
    Slope VARCHAR(255),
    Horizontal_Distance_To_Hydrology VARCHAR(255),
    Vertical_Distance_To_Hydrology VARCHAR(255),
    Horizontal_Distance_To_Roadways VARCHAR(255),
    Hillshade_9am VARCHAR(255),
    Hillshade_Noon VARCHAR(255),
    Hillshade_3pm VARCHAR(255),
    Horizontal_Distance_To_Fire_Points VARCHAR(255),
    Wilderness_Area VARCHAR(255),
    Soil_Type VARCHAR(255),
    Cover_Type VARCHAR(255)
);
