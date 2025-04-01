"""
Configuration settings for fine-tuning with Fireworks AI.
"""

# Base model identifier (choose based on your needs)
BASE_MODEL = "fireworks/llama-v3-8b"

# Fine-tuning parameters
FINE_TUNING_CONFIG = {
    "learning_rate": 2e-5,
    "train_batch_size": 4,
    "eval_batch_size": 4,
    "num_train_epochs": 3,
    "weight_decay": 0.01,
    "optimizer": "adamw_torch",
    "warmup_steps": 100
}

# API connection settings
API_SETTINGS = {
    "api_key_env_var": "FIREWORKS_API_KEY",
    "organization_id_env_var": "FIREWORKS_ORG_ID"
}

# Training data paths
DATA_PATHS = {
    "train_file": "data/processed/training_data.jsonl",
    "validation_file": "data/processed/validation_data.jsonl"
}

# Output directory for the fine-tuned model
OUTPUT_DIR = "models/github_code_assistant"

# Evaluation settings
EVALUATION = {
    "evaluation_strategy": "epoch",
    "save_strategy": "epoch",
    "logging_steps": 100,
    "do_eval": True
}
