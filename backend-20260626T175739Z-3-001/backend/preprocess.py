from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR.parent / "data" / "accidents.csv"

REQUIRED_COLUMNS = [
    "timestamp",
    "lat",
    "lng",
    "location",
    "traffic_speed",
    "weather",
    "road_type",
    "accidents_count",
    "severity",
]


def load_dataset(file_path: str | Path = DATA_PATH) -> pd.DataFrame:
    """Load the accident CSV and validate the columns needed by the project."""
    df = pd.read_csv(file_path)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing columns in dataset: {missing_columns}")

    return df


def preprocess_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Clean data and create ML-ready features."""
    cleaned = df.copy()

    cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"], errors="coerce")
    cleaned["hour"] = cleaned["timestamp"].dt.hour

    numeric_columns = ["lat", "lng", "traffic_speed", "accidents_count", "severity", "hour"]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    text_columns = ["location", "weather", "road_type"]
    for column in text_columns:
        cleaned[column] = cleaned[column].fillna("Unknown").astype(str).str.strip()

    cleaned = cleaned.dropna(subset=["lat", "lng", "traffic_speed", "accidents_count", "severity", "hour"])

    return cleaned


def load_and_preprocess_data(file_path: str | Path = DATA_PATH) -> pd.DataFrame:
    """Convenience function used by training and the API."""
    return preprocess_dataset(load_dataset(file_path))


if __name__ == "__main__":
    data = load_and_preprocess_data()
    print(data.head())
    print(f"Rows after preprocessing: {len(data)}")