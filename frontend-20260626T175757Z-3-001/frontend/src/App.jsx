import React, { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const API = "http://127.0.0.1:5000";

const initialForm = {
  lat: "18.7475",
  lng: "73.6370",
  traffic_speed: "65",
  weather: "Rain",
  road_type: "Highway",
  accidents_count: "2",
  hour: "22",
};

const mapCenter = [18.7475, 73.637];

function FlyToPrediction({ result, form }) {
  const map = useMap();

  useEffect(() => {
    if (result) {
      map.flyTo([Number(form.lat), Number(form.lng)], 14, { duration: 0.8 });
    }
  }, [result, form.lat, form.lng, map]);

  return null;
}

function markerColor(level) {
  if (level === "High") return "#c53030";
  if (level === "Medium") return "#b7791f";
  return "#2f855a";
}

function App() {
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [blackspots, setBlackspots] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/blackspots`)
      .then((res) => res.json())
      .then((data) => setBlackspots(Array.isArray(data) ? data : []))
      .catch(() => setError("Backend not running. Start backend with: py app.py"));
  }, []);

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handlePredict(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: Number(form.lat),
          lng: Number(form.lng),
          traffic_speed: Number(form.traffic_speed),
          weather: form.weather,
          road_type: form.road_type,
          accidents_count: Number(form.accidents_count),
          hour: Number(form.hour),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Prediction failed");
      }

      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const riskClass = result ? result.risk_level.toLowerCase() : "";

  return (
    <div className="page">
      <header className="header">
        <div>
          <p className="tag">Road Safety AI</p>
          <h1>Road Accident Risk Prediction</h1>
          <p>
            Predict accident risk using location, speed, weather, road type,
            time, and previous accident count.
          </p>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <main className="grid">
        <section className="card">
          <h2>Enter Road Conditions</h2>

          <form onSubmit={handlePredict} className="form">
            <label>
              Latitude
              <input name="lat" value={form.lat} onChange={handleChange} />
            </label>

            <label>
              Longitude
              <input name="lng" value={form.lng} onChange={handleChange} />
            </label>

            <label>
              Traffic Speed
              <input
                name="traffic_speed"
                value={form.traffic_speed}
                onChange={handleChange}
              />
            </label>

            <label>
              Previous Accidents
              <input
                name="accidents_count"
                value={form.accidents_count}
                onChange={handleChange}
              />
            </label>

            <label>
              Weather
              <select name="weather" value={form.weather} onChange={handleChange}>
                <option>Clear</option>
                <option>Rain</option>
                <option>Fog</option>
                <option>Storm</option>
              </select>
            </label>

            <label>
              Road Type
              <select
                name="road_type"
                value={form.road_type}
                onChange={handleChange}
              >
                <option>Urban</option>
                <option>Highway</option>
                <option>Expressway</option>
              </select>
            </label>

            <label>
              Hour
              <input name="hour" value={form.hour} onChange={handleChange} />
            </label>

            <button disabled={loading}>
              {loading ? "Predicting..." : "Predict Risk"}
            </button>
          </form>
        </section>

        <section className="card">
          <h2>Prediction Result</h2>

          {!result && <p className="muted">Submit the form to see risk result.</p>}

          {result && (
            <>
              <div className={`risk-box ${riskClass}`}>
                <span>{result.risk_level} Risk</span>
                <strong>{result.risk_score}/5</strong>
              </div>

              <div className="mini-grid">
                <div>
                  <p>ML Score</p>
                  <b>{result.ml_score}</b>
                </div>
                <div>
                  <p>Rule Boost</p>
                  <b>{result.rule_boost}</b>
                </div>
              </div>

              <h3>Safety Recommendations</h3>
              <ul>
                {result.recommendations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      </main>

      <section className="card map-card">
        <div className="section-heading">
          <div>
            <h2>Vadgaon-Sate-Maval Risk Map</h2>
            <p>Blackspot clusters from the CSV are plotted on an interactive map.</p>
          </div>
        </div>

        <MapContainer center={mapCenter} zoom={13} scrollWheelZoom className="map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <FlyToPrediction result={result} form={form} />

          {blackspots.map((spot) => (
            <CircleMarker
              key={`${spot.location}-${spot.lat}-${spot.lng}`}
              center={[spot.lat, spot.lng]}
              radius={spot.risk_level === "High" ? 14 : spot.risk_level === "Medium" ? 11 : 8}
              pathOptions={{
                color: markerColor(spot.risk_level),
                fillColor: markerColor(spot.risk_level),
                fillOpacity: 0.68,
              }}
            >
              <Popup>
                <strong>{spot.location}</strong>
                <br />
                Risk: {spot.risk_level}
                <br />
                Accidents: {spot.accident_count}
                <br />
                Avg severity: {spot.avg_severity}
              </Popup>
            </CircleMarker>
          ))}

          {result && (
            <CircleMarker
              center={[Number(form.lat), Number(form.lng)]}
              radius={18}
              pathOptions={{
                color: "#172026",
                fillColor: markerColor(result.risk_level),
                fillOpacity: 0.9,
                weight: 3,
              }}
            >
              <Popup>
                <strong>Prediction Point</strong>
                <br />
                Risk: {result.risk_level}
                <br />
                Score: {result.risk_score}/5
              </Popup>
            </CircleMarker>
          )}
        </MapContainer>
      </section>

      <section className="card table-card">
        <h2>Detected Accident Blackspots</h2>

        <table>
          <thead>
            <tr>
              <th>Location</th>
              <th>Latitude</th>
              <th>Longitude</th>
              <th>Accidents</th>
              <th>Avg Severity</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {blackspots.map((spot) => (
              <tr key={`${spot.location}-${spot.lat}-${spot.lng}`}>
                <td>{spot.location}</td>
                <td>{spot.lat}</td>
                <td>{spot.lng}</td>
                <td>{spot.accident_count}</td>
                <td>{spot.avg_severity}</td>
                <td>
                  <span className={`badge ${spot.risk_level.toLowerCase()}`}>
                    {spot.risk_level}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default App;