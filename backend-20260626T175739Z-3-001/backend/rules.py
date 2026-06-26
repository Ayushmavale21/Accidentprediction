def calculate_rule_boost(features: dict) -> float:
    """Return an extra risk boost based on easy-to-explain safety rules."""
    boost = 0.0

    hour = int(features.get("hour", 12))
    speed = float(features.get("traffic_speed", 0))
    weather = str(features.get("weather", "")).lower()
    road_type = str(features.get("road_type", "")).lower()
    accidents_count = float(features.get("accidents_count", 0))

    if hour >= 22 or hour <= 5:
        boost += 0.8

    if speed >= 70:
        boost += 0.7
    elif speed >= 55:
        boost += 0.4

    if weather in {"rain", "fog", "storm", "heavy rain"}:
        boost += 0.8

    if road_type in {"highway", "expressway"} and speed >= 60:
        boost += 0.4

    if accidents_count >= 3:
        boost += 0.8
    elif accidents_count >= 1:
        boost += 0.3

    return min(boost, 2.0)


def risk_level(score: float) -> str:
    """Convert a numeric risk score into a readable category."""
    if score >= 3.5:
        return "High"
    if score >= 2.0:
        return "Medium"
    return "Low"


def safety_recommendations(level: str, features: dict) -> list[str]:
    """Create simple recommendations to show in the frontend."""
    recommendations = []
    weather = str(features.get("weather", "")).lower()
    hour = int(features.get("hour", 12))
    speed = float(features.get("traffic_speed", 0))

    if level == "High":
        recommendations.append("Avoid this route if an alternate safer route is available.")
        recommendations.append("Reduce speed and increase distance from nearby vehicles.")
    elif level == "Medium":
        recommendations.append("Drive carefully and watch for sudden braking or crossings.")
    else:
        recommendations.append("Risk is low, but continue normal safe driving practices.")

    if weather in {"rain", "fog", "storm", "heavy rain"}:
        recommendations.append("Use headlights and avoid sudden lane changes in poor weather.")

    if hour >= 22 or hour <= 5:
        recommendations.append("Night-time travel increases risk, so stay alert and slow down.")

    if speed >= 70:
        recommendations.append("High speed is a major risk factor; reduce speed immediately.")

    return recommendations