import joblib
import json
import os
import socket
import sys
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Configuration ---
MODEL_OUTPUT_DIR = os.environ.get("MODEL_OUTPUT_DIR", "/app/model_output")
MODEL_NAME = os.environ.get("MODEL_NAME", "tfidf-sklearn")
LOGSTASH_HOST = os.environ.get("LOGSTASH_HOST", "logstash")
LOGSTASH_PORT = int(os.environ.get("LOGSTASH_PORT", "5004"))
label_mapping = {1: "Social Media", 2: "Promotions", 3: "Forum", 4: "Spam", 5: "Verify Code", 6: "Updates"}
print(MODEL_NAME)
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