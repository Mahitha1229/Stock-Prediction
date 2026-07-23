import pickle
import os

with open("stock_models.pkl", "rb") as f:
    all_models = pickle.load(f)

os.makedirs("split_models", exist_ok=True)

for ticker, model_dict in all_models.items():
    safe_name = ticker.replace("/", "_").replace("^", "IDX_").replace(".", "_")
    path = os.path.join("split_models", f"{safe_name}.pkl")
    with open(path, "wb") as f:
        pickle.dump(model_dict, f)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"{ticker} -> {path} ({size_mb:.1f} MB)")

print(f"\nDone. {len(all_models)} files written to ./split_models/")