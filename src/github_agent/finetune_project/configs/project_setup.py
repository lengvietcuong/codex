import os

def create_project_structure():
    """Create the directory structure for the fine-tuning project."""
    directories = [
        'data/raw',
        'data/processed',
        'scripts',
        'models',
        'evaluation',
        'configs'
    ]
    
    for directory in directories:
        os.makedirs(os.path.join(os.getcwd(), directory), exist_ok=True)
        print(f"Created directory: {directory}")
    
    print("Project structure created successfully.")

if __name__ == "__main__":
    create_project_structure()
