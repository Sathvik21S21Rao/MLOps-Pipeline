import os
import sys
from datasets import load_dataset, DatasetDict
from transformers import AutoTokenizer
from huggingface_hub import login
from dotenv import load_dotenv
load_dotenv()
# --- Configuration ---
# /app/data is a standard convention for mounting volumes in Docker
DATASET_ID = os.environ.get("DATASET_ID", "jason23322/high-accuracy-email-classifier")
MODEL_CHECKPOINT = os.environ.get("MODEL_CHECKPOINT", "bert-base-uncased")
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", 256))
OUTPUT_VOLUME_PATH = os.environ.get("PROCESSED_DATA_PATH", "../output_data")

class EmailDatasetPreparer:
    
    def __init__(self, dataset_id: str, model_checkpoint: str, max_length: int):
        self.dataset_id = dataset_id
        self.tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)
        self.max_length = max_length
        print(f"Initialized preparer for dataset: {self.dataset_id}")

    def load_and_prepare_data(self) -> DatasetDict:
        print("Downloading dataset...")
        try:
            raw_datasets = load_dataset(self.dataset_id, split=['train', 'test'])
            dataset_dict = DatasetDict({
                'train': raw_datasets[0],
                'test': raw_datasets[1]
            })
        except Exception as e:
            print(f"ERROR: Error loading dataset: {e}", file=sys.stderr)
            sys.exit(1)

        def tokenize_function(examples):
            return self.tokenizer(
                examples["text"],
                padding="max_length",
                truncation=True,
                max_length=self.max_length
            )

        print("Tokenizing data...")
        tokenized_datasets = dataset_dict.map(
            tokenize_function,
            batched=True,
            remove_columns=['id', 'subject', 'body', 'text', 'category']
        )
        
        tokenized_datasets = tokenized_datasets.rename_column("category_id", "labels")
        return tokenized_datasets

    def save_to_volume(self, dataset: DatasetDict, output_path: str):
        """Saves the dataset AND tokenizer to the shared volume"""
        print(f"Saving processed data to volume: {output_path}")
        
        dataset.save_to_disk(output_path)
        
        self.tokenizer.save_pretrained(output_path)
        
        print(" Save complete. Ready for training container.")

if __name__ == '__main__':
    hf_token = os.environ.get("HF_API_TOKEN")
    print(hf_token)
    if hf_token:
        login(token=hf_token)
        
    preparer = EmailDatasetPreparer(DATASET_ID, MODEL_CHECKPOINT, MAX_LENGTH)
    
    # 1. Process
    tokenized_data = preparer.load_and_prepare_data()

    # 2. Save to the shared Volume path
    preparer.save_to_volume(tokenized_data, OUTPUT_VOLUME_PATH)