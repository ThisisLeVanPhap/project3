from datasets import load_dataset

# Load dataset
ds = load_dataset("Quoc59/QA-wood-products")

# Giả sử dataset có split "train"
df = ds["train"].to_pandas()

# Xuất thành CSV
df.to_csv("QA-wood-products.csv", index=False)

print("Đã lưu file QA-wood-products.csv")

#Eval_QA_Wood