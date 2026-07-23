import pickle
import os

INPUT_DIR = "split_models"
OUTPUT_DIR = "split_models_no_lstm"

os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename in os.listdir(INPUT_DIR):
    if not filename.endswith(".pkl"):
        continue
    path = os.path.join(INPUT_DIR, filename)
    with open(path, "rb") as f:
        model_dict = pickle.load(f)

    if "lstm" in model_dict:
        del model_dict["lstm"]

    out_path = os.path.join(OUTPUT_DIR, filename)
    with open(out_path, "wb") as f:
        pickle.dump(model_dict, f)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"{filename} -> {out_path} ({size_mb:.1f} MB, keys: {list(model_dict.keys())})")

print("\nDone.")