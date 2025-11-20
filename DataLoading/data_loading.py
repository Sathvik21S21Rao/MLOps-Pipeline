import os
import sys
from datasets import load_dataset, DatasetDict
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from huggingface_hub import login


DATASET_ID = os.environ.get("DATASET_ID", "jason23322/high-accuracy-email-classifier")
MODEL_CHECKPOINT = os.environ.get("MODEL_CHECKPOINT", "bert-base-uncased")
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", 256))

# --- Data Loading and Preprocessing Class ---
class EmailDatasetPreparer:
    
    def __init__(self, dataset_id: str, model_checkpoint: str, max_length: int):
        self.dataset_id = dataset_id
       
        self.tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)
        self.max_length = max_length
        self.num_labels = 6
        print(f"Initialized preparer for dataset: {self.dataset_id} (Checkpoint: {model_checkpoint}, Max Length: {max_length})")

    def load_and_prepare_data(self) -> tuple[DatasetDict, int, AutoTokenizer]:
       
        try:
            raw_datasets = load_dataset(self.dataset_id, split=['train', 'test'])
            
            dataset_dict = DatasetDict({
                'train': raw_datasets[0],
                'test': raw_datasets[1]
            })

        except Exception as e:
            print(f"ERROR: Error loading dataset: {e}", file=sys.stderr)
            print("Action required: Check your DATASET_ID, HF_API_TOKEN, and access permissions.", file=sys.stderr)
            sys.exit(1)

        def tokenize_function(examples):
            return self.tokenizer(
                examples["text"],
                padding="max_length",
                truncation=True,
                max_length=self.max_length
            )

        tokenized_datasets = dataset_dict.map(
            tokenize_function,
            batched=True,
            remove_columns=['id', 'subject', 'body', 'text', 'category']
        )
        
        tokenized_datasets = tokenized_datasets.rename_column("category_id", "labels")

        print("Data tokenization complete.")
        print(f"Training set size: {len(tokenized_datasets['train'])}")
        print(f"Test set size: {len(tokenized_datasets['test'])}")
        
        return tokenized_datasets, self.num_labels, self.tokenizer


if __name__ == '__main__':
    hf_token = os.environ.get("HF_API_TOKEN")
    if hf_token:
        print("Found HF_API_TOKEN in environment. Logging in to Hugging Face Hub...")
        login(token=hf_token)
    else:
        print("CRITICAL WARNING: HF_API_TOKEN not found. Using anonymous access.", file=sys.stderr)
        
    preparer = EmailDatasetPreparer(DATASET_ID, MODEL_CHECKPOINT, MAX_LENGTH)
    
    tokenized_data, num_labels, tokenizer = preparer.load_and_prepare_data()

    if tokenized_data:
        print("\n--- Example Data Sample ---")
        sample = tokenized_data['train'][0]
        print(f"Features: {sample}")
        print(f"Input IDs (tokenized text snippet): {sample['input_ids'][:10]}...")
        print(f"Attention Mask snippet: {sample['attention_mask'][:10]}...")
        print(f"Label (category ID): {sample['labels']}")
        decoded_text = tokenizer.decode(sample['input_ids'], skip_special_tokens=True)
        print(f"Decoded Text: {decoded_text}")
        print("-" * 30)