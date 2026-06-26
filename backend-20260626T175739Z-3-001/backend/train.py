from pathlib import Path

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from preprocess import load_and_preprocess_data


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"

FEATURE_COLUMNS = [
    "lat",
    "lng",
    "traffic_speed",
    "accidents_count",
    "hour",
    "weather",
    "road_type",
]
TARGET_COLUMN = "severity"


def train_model() -> None:
    df = load_and_preprocess_data()

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    numeric_features = ["lat", "lng", "traffic_speed", "accidents_count", "hour"]
    categorical_features = ["weather", "road_type"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ]
    )

    model = RandomForestRegressor(
        n_estimators=150,
        random_state=42,
        min_samples_leaf=1,
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    pipeline.fit(X_train, y_train)
    predictions = pipeline.predict(X_test)

    print("Model training completed")
    print(f"Rows used: {len(df)}")
    print(f"MAE: {mean_absolute_error(y_test, predictions):.3f}")
    print(f"MSE: {mean_squared_error(y_test, predictions):.3f}")
    print(f"R2 Score: {r2_score(y_test, predictions):.3f}")

    joblib.dump(
        {
            "pipeline": pipeline,
            "features": FEATURE_COLUMNS,
            "target": TARGET_COLUMN,
        },
        MODEL_PATH,
    )
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    train_model()