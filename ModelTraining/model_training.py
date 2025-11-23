import os
import numpy as np
import evaluate
import json
from datetime import datetime
from datasets import load_from_disk
from transformers import (
    AutoModelForSequenceClassification, 
    TrainingArguments, 
    Trainer, 
    DataCollatorWithPadding,
    AutoTokenizer
)

# --- Configuration ---
# Matches the path defined in the loader and docker-compose volume
# UPDATED: Default now matches Docker Compose
DATA_PATH = os.environ.get("PROCESSED_DATA_PATH", "../output_data")
MODEL_CHECKPOINT = os.environ.get("MODEL_CHECKPOINT", "bert-base-uncased")
OUTPUT_DIR = os.environ.get("MODEL_OUTPUT_DIR", "../model_output")

# --- Metrics ---
metric_accuracy = evaluate.load("accuracy")
metric_f1 = evaluate.load("f1")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    accuracy = metric_accuracy.compute(predictions=predictions, references=labels)
    f1 = metric_f1.compute(predictions=predictions, references=labels, average="weighted")
    return {"accuracy": accuracy["accuracy"], "f1": f1["f1"]}


def emit_logstash_metrics(metrics: dict, model_checkpoint: str, data_path: str, output_dir: str):
    """Emit a single-line JSON record suitable for Logstash ingestion (stdout/tcp/filebeat).

    The JSON includes some contextual fields so Logstash can index them.
    """
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "log_type": "training_metrics",
        "model_checkpoint": model_checkpoint,
        "data_path": data_path,
        "output_dir": output_dir,
        "metrics": metrics
    }
    print(json.dumps(record, ensure_ascii=False))

# --- Trainer Class ---
class EmailModelTrainer:
    def __init__(self, model_checkpoint, num_labels=6, output_dir=OUTPUT_DIR):
        self.model_checkpoint = model_checkpoint
        self.num_labels = num_labels
        self.output_dir = output_dir
        
    def train(self, tokenized_datasets, tokenizer):
        print(f"Loading model: {self.model_checkpoint}...")
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_checkpoint, 
            num_labels=self.num_labels
        )
        
        data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

        training_args = TrainingArguments(
            output_dir=self.output_dir,
            learning_rate=2e-5,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=16,
            num_train_epochs=3,
            weight_decay=0.01,
            eval_strategy="epoch",       # old name
            save_strategy="epoch",
            load_best_model_at_end=True,
            report_to="none"
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_datasets["train"],
            eval_dataset=tokenized_datasets["test"],
            tokenizer=tokenizer,
            data_collator=data_collator,
            compute_metrics=compute_metrics,
        )

        print("Starting training...")
        trainer.train()
        print(f"Training complete. Saving to {self.output_dir}")
        trainer.save_model(f"{self.output_dir}/best_model")
        # Collect evaluation metrics and emit structured JSON for Logstash
        eval_metrics = trainer.evaluate()
        emit_logstash_metrics(eval_metrics, self.model_checkpoint, os.environ.get("PROCESSED_DATA_PATH", "../output_data"), self.output_dir)
        return eval_metrics

if __name__ == '__main__':
    print(f"Looking for data at: {DATA_PATH}")
    
    if not os.path.exists(DATA_PATH):
        print(f"CRITICAL ERROR: Data path {DATA_PATH} does not exist.")
        exit(1)

    # Load dataset
    tokenized_datasets = load_from_disk(DATA_PATH)

    # DO NOT rename column again — it's already 'labels'
    # Compute num_labels from integer values
    num_labels = int(max(tokenized_datasets["train"]["labels"])) + 1

    # Load tokenizer from same folder
    tokenizer = AutoTokenizer.from_pretrained(DATA_PATH)

    trainer_engine = EmailModelTrainer(
        model_checkpoint=MODEL_CHECKPOINT,
        num_labels=num_labels
    )
    
    metrics = trainer_engine.train(tokenized_datasets, tokenizer)
    # Also emit a final message indicating completion (helps Logstash detect run boundaries)
    emit_logstash_metrics({"status": "completed", "metrics": metrics}, MODEL_CHECKPOINT, DATA_PATH, OUTPUT_DIR)