from datasets import load_dataset

# Login using e.g. `huggingface-cli login` to access this dataset
ds = load_dataset("jason23322/high-accuracy-email-classifier")
print(ds)