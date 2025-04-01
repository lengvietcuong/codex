import os
import sys
import json
from dotenv import load_dotenv
import requests
from time import sleep
import argparse

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from configs.fireworks_config import BASE_MODEL, FINE_TUNING_CONFIG, API_SETTINGS, DATA_PATHS

# Load environment variables
load_dotenv()

# Get API key
FIREWORKS_API_KEY = os.getenv(API_SETTINGS["api_key_env_var"])
FIREWORKS_ORG_ID = os.getenv(API_SETTINGS["organization_id_env_var"])

if not FIREWORKS_API_KEY:
    raise ValueError(f"API key not found. Please set {API_SETTINGS['api_key_env_var']} environment variable.")

# API endpoints
API_BASE_URL = "https://api.fireworks.ai/inference/v1"

def upload_file(file_path):
    """Upload a file to Fireworks AI."""
    print(f"Uploading file: {file_path}")
    
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{API_BASE_URL}/files/upload",
            headers={"Authorization": f"Bearer {FIREWORKS_API_KEY}"},
            files={"file": f}
        )
    
    if response.status_code != 200:
        print(f"Error uploading file: {response.status_code}")
        print(response.text)
        return None
    
    return response.json().get("id")

def create_fine_tuning_job(training_file_id, validation_file_id):
    """Create a fine-tuning job on Fireworks AI."""
    print("Creating fine-tuning job...")
    
    payload = {
        "model": BASE_MODEL,
        "training_file": training_file_id,
        "validation_file": validation_file_id,
        "hyperparameters": {
            "n_epochs": FINE_TUNING_CONFIG["num_train_epochs"],
            "batch_size": FINE_TUNING_CONFIG["train_batch_size"],
            "learning_rate": FINE_TUNING_CONFIG["learning_rate"]
        }
    }
    
    response = requests.post(
        f"{API_BASE_URL}/fine_tuning/jobs",
        headers={
            "Authorization": f"Bearer {FIREWORKS_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    
    if response.status_code != 200:
        print(f"Error creating fine-tuning job: {response.status_code}")
        print(response.text)
        return None
    
    return response.json().get("id")

def check_fine_tuning_status(job_id):
    """Check the status of a fine-tuning job."""
    response = requests.get(
        f"{API_BASE_URL}/fine_tuning/jobs/{job_id}",
        headers={"Authorization": f"Bearer {FIREWORKS_API_KEY}"}
    )
    
    if response.status_code != 200:
        print(f"Error checking fine-tuning status: {response.status_code}")
        print(response.text)
        return None
    
    return response.json()

def run_fine_tuning():
    """Run the fine-tuning process from start to finish."""
    # Get absolute paths to data files
    train_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATA_PATHS["train_file"])
    validation_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATA_PATHS["validation_file"])
    
    # Upload training data
    training_file_id = upload_file(train_file)
    if not training_file_id:
        print("Failed to upload training file. Aborting.")
        return
    
    print(f"Training file uploaded with ID: {training_file_id}")
    
    # Upload validation data
    validation_file_id = upload_file(validation_file)
    if not validation_file_id:
        print("Failed to upload validation file. Aborting.")
        return
    
    print(f"Validation file uploaded with ID: {validation_file_id}")
    
    # Create fine-tuning job
    job_id = create_fine_tuning_job(training_file_id, validation_file_id)
    if not job_id:
        print("Failed to create fine-tuning job. Aborting.")
        return
    
    print(f"Fine-tuning job created with ID: {job_id}")
    
    # Monitor job status
    print("Monitoring fine-tuning job status...")
    done_states = ["succeeded", "failed", "cancelled"]
    
    while True:
        status = check_fine_tuning_status(job_id)
        if not status:
            print("Failed to check job status.")
            break
        
        current_status = status.get("status")
        print(f"Current status: {current_status}")
        
        if current_status in done_states:
            print(f"Fine-tuning completed with status: {current_status}")
            if current_status == "succeeded":
                print(f"Fine-tuned model ID: {status.get('fine_tuned_model')}")
                # Save model info to a file
                with open("../models/model_info.json", 'w') as f:
                    json.dump({
                        "model_id": status.get('fine_tuned_model'),
                        "base_model": BASE_MODEL,
                        "training_info": status
                    }, f, indent=2)
            break
        
        # Wait before checking again
        sleep(60)  # Check every minute

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fine-tune a model on Fireworks AI')
    args = parser.parse_args()
    
    run_fine_tuning()
