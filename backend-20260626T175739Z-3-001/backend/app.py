from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from sklearn.cluster import DBSCAN

from preprocess import load_and_preprocess_data
from rules import calculate_rule_boost, risk_level, safety_recommendations


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"

app = Flask(__name__)
CORS(app)

model_bundle = None


def load_model_bundle():
    """Load model once and reuse it for all prediction requests."""
    global model_bundle
    if model_bundle is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError("model.pkl not found. Run: python train.py")
        model_bundle = joblib.load(MODEL_PATH)
    return model_bundle


def clamp_score(score: float) -> float:
    """Keep score inside the 0 to 5 severity range."""
    return round(max(0.0, min(5.0, score)), 2)


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "message": "Road accident risk backend is running",
            "model_exists": MODEL_PATH.exists(),
        }
    )


@app.route("/predict", methods=["POST"])
def predict():
    """
    Expected JSON:
    {
      "lat": 18.5204,
      "lng": 73.8567,
      "traffic_speed": 65,
      "weather": "Rain",
      "road_type": "Highway",
      "accidents_count": 2,
      "hour": 22
    }
    """
    data = request.get_json(silent=True) or {}
    bundle = load_model_bundle()
    features = bundle["features"]

    try:
        input_row = {
            "lat": float(data["lat"]),
            "lng": float(data["lng"]),
            "traffic_speed": float(data["traffic_speed"]),
            "accidents_count": float(data.get("accidents_count", 0)),
            "hour": int(data["hour"]),
            "weather": str(data["weather"]),
            "road_type": str(data["road_type"]),
        }
    except KeyError as error:
        return jsonify({"error": f"Missing required field: {error.args[0]}"}), 400
    except ValueError:
        return jsonify({"error": "lat, lng, traffic_speed, accidents_count, and hour must be numeric"}), 400

    input_df = pd.DataFrame([input_row], columns=features)
    ml_score = float(bundle["pipeline"].predict(input_df)[0])
    rule_boost = calculate_rule_boost(input_row)
    final_score = clamp_score(ml_score + rule_boost)
    level = risk_level(final_score)

    return jsonify(
        {
            "risk_score": final_score,
            "risk_level": level,
            "ml_score": round(ml_score, 2),
            "rule_boost": round(rule_boost, 2),
            "recommendations": safety_recommendations(level, input_row),
        }
    )


@app.route("/blackspots", methods=["GET"])
def blackspots():
    """Return accident-prone clusters detected from latitude and longitude."""
    limit = request.args.get("limit", default=50, type=int)
    df = load_and_preprocess_data()

    coordinates = df[["lat", "lng"]].to_numpy()
    clustering = DBSCAN(eps=0.03, min_samples=2).fit(coordinates)
    df = df.copy()
    df["cluster"] = clustering.labels_

    clustered = df[df["cluster"] != -1]
    if clustered.empty:
        clustered = df
        clustered["cluster"] = range(len(clustered))

    summary = (
        clustered.groupby("cluster")
        .agg(
            lat=("lat", "mean"),
            lng=("lng", "mean"),
            location=("location", "first"),
            accident_count=("severity", "count"),
            avg_severity=("severity", "mean"),
        )
        .reset_index()
        .sort_values(["accident_count", "avg_severity"], ascending=False)
        .head(max(1, min(limit, 200)))
    )

    spots = []
    for _, row in summary.iterrows():
        score = clamp_score(float(row["avg_severity"]))
        spots.append(
            {
                "lat": round(float(row["lat"]), 6),
                "lng": round(float(row["lng"]), 6),
                "location": row["location"],
                "accident_count": int(row["accident_count"]),
                "avg_severity": round(float(row["avg_severity"]), 2),
                "risk_level": risk_level(score),
            }
        )

    return jsonify(spots)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)