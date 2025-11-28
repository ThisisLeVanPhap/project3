.PHONY: dev train test


dev:
	uvicorn app.server:app --host 0.0.0.0 --port 8000


train:
	python training/train_lora.py


test:
	pytest -q