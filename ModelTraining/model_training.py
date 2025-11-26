import os
import json
import numpy as np
from datetime import datetime
from datasets import load_from_disk
import joblib
import socket
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier, LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score

# --- Configuration ---
DATA_PATH = os.environ.get("PROCESSED_DATA_PATH", "/app/data")
OUTPUT_DIR = os.environ.get("MODEL_OUTPUT_DIR", "/app/model_output")
MODEL_NAME = os.environ.get("MODEL_TYPE", "tfidf-sklearn")

LOGSTASH_HOST = os.environ.get("LOGSTASH_HOST", "logstash")
LOGSTASH_PORT = int(os.environ.get("LOGSTASH_PORT", "5004"))
def compute_metrics(y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="weighted")
    return {"accuracy": float(acc), "f1": float(f1)}


def emit_logstash_metrics(metrics: dict, model_name: str, data_path: str, output_dir: str):
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "log_type": "training_metrics",
        "model_name": model_name,
        "data_path": data_path,
        "output_dir": output_dir,
        "metrics": metrics,
    }
    send_to_logstash(record)


def send_to_logstash(data: dict):
    """Send a JSON event to Logstash over TCP."""
    try:
        # Add log_type so Logstash filter knows how to route it
        data["log_type"] = "training_metrics"
        
        message = json.dumps(data) + "\n"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((LOGSTASH_HOST, LOGSTASH_PORT))
        sock.sendall(message.encode("utf-8"))
        sock.close()

        print(f"Pushed to Logstash: {data}")

    except Exception as e:
        print(f"Failed to send log to Logstash: {e}")

class EmailModelTrainer:
    def __init__(self, output_dir=OUTPUT_DIR, max_features=20000, classifier_name=None):
        self.output_dir = output_dir
        # allow environment override, but constructor arg takes precedence
        self.classifier_name = classifier_name or os.environ.get("CLASSIFIER", "sgd")
        # if max_features is None, TfidfVectorizer will use all features
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=max_features, ngram_range=(1, 2))),
            ("clf", self._select_classifier(self.classifier_name)),
        ])

    def _select_classifier(self, name):
        n = (name or "").lower()
        if "log" in n or "logistic" in n:
            return LogisticRegression(max_iter=1000)
        if "rf" in n or "random" in n:
            return RandomForestClassifier(n_estimators=100)
        # default and 'sgd' -> linear model with log loss
        return SGDClassifier(loss="log_loss", max_iter=1000, tol=1e-3)

    def train(self, train_texts, train_labels, test_texts, test_labels):
        print("Fitting TF-IDF + classifier pipeline...")
        self.pipeline.fit(train_texts, train_labels)

        print("Evaluating on test set...")
        preds = self.pipeline.predict(test_texts)
        metrics = compute_metrics(test_labels, preds)

        os.makedirs(self.output_dir, exist_ok=True)
        model_path = os.path.join(self.output_dir, f"{MODEL_NAME}.joblib")
        print(model_path)
        joblib.dump(self.pipeline, model_path)
        print(f"Model saved to {model_path}")

        emit_logstash_metrics(metrics, MODEL_NAME, DATA_PATH, self.output_dir)
        return metrics


def _extract_texts_and_labels(ds_split):
    # Expect a 'text' column; try common fallbacks
    if "text" in ds_split.column_names:
        texts = [str(x) for x in ds_split["text"]]
    elif "sentence" in ds_split.column_names:
        texts = [str(x) for x in ds_split["sentence"]]
    elif "content" in ds_split.column_names:
        texts = [str(x) for x in ds_split["content"]]
    else:
        raise RuntimeError("No text column found in dataset. Expected 'text' or similar.")
    # Prefer common label column names used in datasets; fall back with clear error
    if "labels" in ds_split.column_names:
        labels_column = "labels"
    elif "label" in ds_split.column_names:
        labels_column = "label"
    elif "category_id" in ds_split.column_names:
        labels_column = "category_id"
    elif "category" in ds_split.column_names:
        # category may be string; try to map to integers if possible
        labels_column = "category"
    else:
        raise RuntimeError("No label column found in dataset. Expected 'labels', 'label', 'category_id' or 'category'.")

    labels_raw = ds_split[labels_column]
    # If category is string, try to map to numeric ids using category_id if available
    if labels_column == "category":
        try:
            labels = np.array([int(x) for x in labels_raw], dtype=int)
        except Exception:
            # fallback: create integer ids by factorizing strings
            uniques = {}
            lab_list = []
            for x in labels_raw:
                if x not in uniques:
                    uniques[x] = len(uniques)
                lab_list.append(uniques[x])
            labels = np.array(lab_list, dtype=int)
    else:
        labels = np.array(labels_raw, dtype=int)
    return texts, labels


if __name__ == "__main__":
    print(f"Looking for data at: {DATA_PATH}")

    if not os.path.exists(DATA_PATH):
        print(f"CRITICAL ERROR: Data path {DATA_PATH} does not exist.")
        exit(1)

    ds = load_from_disk(DATA_PATH)

    if "train" not in ds or "test" not in ds:
        print("CRITICAL ERROR: Dataset must contain 'train' and 'test' splits.")
        exit(1)

    train_texts, train_labels = _extract_texts_and_labels(ds["train"])
    test_texts, test_labels = _extract_texts_and_labels(ds["test"])

    trainer_engine = EmailModelTrainer(output_dir=OUTPUT_DIR)
    metrics = trainer_engine.train(train_texts, train_labels, test_texts, test_labels)

    emit_logstash_metrics({"status": "completed", "metrics": metrics}, MODEL_NAME, DATA_PATH, OUTPUT_DIR)