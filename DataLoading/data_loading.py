import os
import sys
from datasets import load_dataset, DatasetDict
from huggingface_hub import login
from dotenv import load_dotenv

load_dotenv()

DATASET_ID = os.environ.get("DATASET_ID", "jason23322/high-accuracy-email-classifier")
OUTPUT_VOLUME_PATH = os.environ.get("PROCESSED_DATA_PATH", "/app/data")

class EmailDatasetPreparer:
    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        print(f"Initialized preparer for dataset: {self.dataset_id}")

    def download_raw_data(self) -> DatasetDict:
        print("Downloading dataset...")
        try:
            raw_train = load_dataset(self.dataset_id, split='train')
            raw_test = load_dataset(self.dataset_id, split='test')

            return DatasetDict({
                'train': raw_train,
                'test': raw_test
            })
        except Exception as e:
            print(f"ERROR: Error loading dataset: {e}", file=sys.stderr)
            sys.exit(1)

    def save_to_volume(self, dataset: DatasetDict, output_path: str):
        print(f"Saving RAW dataset to volume: {output_path}")
        dataset.save_to_disk(output_path)
        print("Save complete. Raw dataset is ready.")

if __name__ == '__main__':
    hf_token = os.environ.get("HF_API_TOKEN")
    if hf_token:
        login(token=hf_token)

    preparer = EmailDatasetPreparer(DATASET_ID)

    dataset = preparer.download_raw_data()
    preparer.save_to_volume(dataset, OUTPUT_VOLUME_PATH)
