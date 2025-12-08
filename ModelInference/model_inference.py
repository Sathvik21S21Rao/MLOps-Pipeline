import joblib
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

def _fetch_best_model_from_elasticsearch(default_model: str) -> str:
    """Query Elasticsearch training_metrics to pick best model by f1 then accuracy."""
    if not ELASTICSEARCH_URL:
        return default_model

    query = {
        "size": 0,
        "query": {"term": {"log_type.keyword": "training_metrics"}},
        "aggs": {
            "by_model": {
                "terms": {"field": "model_name.keyword", "size": 50},
                "aggs": {
                    "latest": {
                        "top_hits": {
                            "sort": [{"timestamp": {"order": "desc"}}],
                            "size": 1,
                        }
                    }
                },
            }
        },
    }

    # Query all indices to avoid missing training_metrics if index pattern differs
    url = ELASTICSEARCH_URL.rstrip("/") + "/_search"
    data = json.dumps(query).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    password_mgr = None
    opener = None

    if ELASTICSEARCH_USER and ELASTICSEARCH_PASSWORD:
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, url, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD)
        handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
        opener = urllib.request.build_opener(handler)
    else:
        opener = urllib.request.build_opener()

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with opener.open(req, timeout=10) as resp:
            payload = json.load(resp)
            print(payload)
    except Exception as exc:  # noqa: BLE001 keep broad so we fall back
        print(f"Failed to query Elasticsearch for best model: {exc}")
        return default_model

    buckets = payload.get("aggregations", {}).get("by_model", {}).get("buckets", [])
    best = None
    for bucket in buckets:
        name = bucket.get("key")
        hits = bucket.get("latest", {}).get("hits", {}).get("hits", [])
        if not hits:
            continue
        src = hits[0].get("_source", {})
        metrics = src.get("metrics", {}) or {}
        # handle nested metrics.metrics and also nested under metrics.metrics again
        if isinstance(metrics, dict) and "metrics" in metrics:
            metrics = metrics.get("metrics", {}) or metrics
        if isinstance(metrics, dict) and "metrics" in metrics:
            metrics = metrics.get("metrics", {}) or metrics
        f1 = metrics.get("f1")
        acc = metrics.get("accuracy")
        score = (f1 or 0, acc or 0)
        if best is None or score > best[1]:
            best = (name, score)

    return best[0] if best else default_model

# --- Configuration ---
MODEL_OUTPUT_DIR = os.environ.get("MODEL_OUTPUT_DIR", "/app/model_output")
MODEL_NAME = os.environ.get("MODEL_NAME", "tfidf-sklearn")
LOGSTASH_HOST = os.environ.get("LOGSTASH_HOST", "logstash")
LOGSTASH_PORT = int(os.environ.get("LOGSTASH_PORT", "5004"))
ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200") 
ELASTICSEARCH_USER = os.environ.get("ELASTICSEARCH_USER", "")
ELASTICSEARCH_PASSWORD = os.environ.get("ELASTICSEARCH_PASSWORD", "")
label_mapping = {1: "Social Media", 2: "Promotions", 3: "Forum", 4: "Spam", 5: "Verify Code", 6: "Updates"}
MODEL_NAME = _fetch_best_model_from_elasticsearch(MODEL_NAME)
MODEL_PATH = os.path.join(MODEL_OUTPUT_DIR, f"{MODEL_NAME}.joblib")
print(MODEL_PATH)



# --- Logstash Helpers ---
def send_to_logstash(payload: dict, log_type: str = "inference_event"):
    """Send a JSON log to Logstash; fallback to stdout on failure."""
    try:
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "log_type": log_type,
            **payload,
        }
        message = json.dumps(event) + "\n"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((LOGSTASH_HOST, LOGSTASH_PORT))
        sock.sendall(message.encode("utf-8"))
        sock.close()
        print(f"Pushed to Logstash: {event}")
    except Exception as e:
        print(f"Failed to send log to Logstash: {e}")

# --- Pydantic Schema for Request Body ---
# Defines the expected JSON format for incoming requests
class PredictionRequest(BaseModel):
    """Schema for the email text input."""
    email_text: str

# --- Pydantic Schema for Response Body (Good Practice) ---
class PredictionResponse(BaseModel):
    """Schema for the prediction result output."""
    predicted_label: int
    input_length: int
    model_used: str
    label : str

# --- Model Loading and Prediction Logic ---
class EmailModelInferrer:
    def __init__(self):
        self.model = self._load_model()
        print("EmailModelInferrer initialized and model loaded.")
        send_to_logstash({
            "event": "model_loaded",
            "model_name": MODEL_NAME,
            "model_path": MODEL_PATH,
            "status": "success",
        })

    def _load_model(self):
        """Loads the trained scikit-learn pipeline from disk."""
        if not os.path.exists(MODEL_PATH):
            print(f"CRITICAL ERROR: Model file not found at {MODEL_PATH}", file=sys.stderr)
            # In an app context, we raise an error instead of sys.exit()
            send_to_logstash({
                "event": "model_loaded",
                "model_name": MODEL_NAME,
                "model_path": MODEL_PATH,
                "status": "not_found",
            }, log_type="inference_error")
            raise RuntimeError(f"Model file not found at {MODEL_PATH}")
        
        try:
            pipeline = joblib.load(MODEL_PATH)
            print(f"Successfully loaded model from {MODEL_PATH}")
            return pipeline
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to load model: {e}", file=sys.stderr)
            send_to_logstash({
                "event": "model_loaded",
                "model_name": MODEL_NAME,
                "model_path": MODEL_PATH,
                "status": "load_failed",
                "error": str(e),
            }, log_type="inference_error")
            raise RuntimeError(f"Failed to load model: {e}")

    def predict(self, text_input: str) -> int:
        """
        Takes a single text string and returns the predicted class label (int).
        """
        if not isinstance(text_input, str):
            raise TypeError("Input must be a single string of text.")
            
        # The pipeline expects an iterable of strings, so wrap the single input
        predictions = self.model.predict([text_input])
        return int(predictions[0])

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Email Classifier Inference Service",
    description="Serves predictions from the TFIDF + Sklearn Email Classifier Model."
)

# 1. Instantiate the Model Inferrer (runs only once at startup)
try:
    INFERRER = EmailModelInferrer()
except RuntimeError as e:
    # If model loading fails, the app should log and potentially exit or be unhealthy
    print(f"Application failed to start due to model loading error: {e}")
    # In production, a more robust solution might handle this, but for simplicity, we let it fail.
    # We define INFERRER outside the route so the model isn't reloaded on every request.
    sys.exit(1)


# 2. Define the POST prediction endpoint
@app.post("/predict", response_model=PredictionResponse, status_code=200)
def predict_endpoint(request: PredictionRequest):
    """
    Accepts an email text and returns the predicted category label (e.g., 0 or 1).
    """
    try:
        start = time.perf_counter()
        # Get the input text from the validated request body
        text_input = request.email_text
        
        # Get the prediction
        prediction = INFERRER.predict(text_input)
        latency_ms = (time.perf_counter() - start) * 1000
        predicted_label_name = label_mapping.get(prediction, "Unknown")

        send_to_logstash({
            "event": "prediction",
            "model_name": MODEL_NAME,
            "input_length": len(text_input),
            "predicted_label": prediction,
            "label": predicted_label_name,
            "latency_ms": round(latency_ms, 3),
        })
        
        # Return the structured response
        return PredictionResponse(
            predicted_label=prediction,
            input_length=len(text_input),
            model_used=MODEL_NAME,
            label=predicted_label_name

        )
    except Exception as e:
        send_to_logstash({
            "event": "prediction_error",
            "model_name": MODEL_NAME,
            "error": str(e),
        }, log_type="inference_error")
        # Catch prediction errors and return a 500 error response
        raise HTTPException(status_code=500, detail=f"Internal prediction error: {e}")

# 3. Optional: Define a health check endpoint
@app.get("/health")
def health_check():
    """Simple check to verify the service is running."""
    return {"status": "ok", "model_loaded": True}

if __name__ == '__main__':
    # This block is typically skipped when running via Uvicorn/Docker CMD,
    # but kept for local development or explicit run
    import uvicorn
    print("Running FastAPI server locally...")
    uvicorn.run(app, host="0.0.0.0", port=8000)