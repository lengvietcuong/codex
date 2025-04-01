import json

# Specify the input and output file names.
old_file = "old_data.jsonl"   # Replace with your old JSONL file path.
new_file = "new_data.jsonl"   # This file will be created with the new format.

# Define the system message (fixed content).
system_message = {
    "role": "system",
    "content": "You are an agent that can interact with a GitHub API to search for repositories, read files, and clone repositories."
}

# Open the old JSONL file for reading and the new JSONL file for writing.
with open(old_file, "r", encoding="utf-8") as fin, open(new_file, "w", encoding="utf-8") as fout:
    for line in fin:
        # Load each line as a JSON object.
        old_entry = json.loads(line)
        
        # Construct the new messages list.
        new_entry = {
            "messages": [
                system_message,
                {"role": "user", "content": old_entry["input"]},
                {"role": "assistant", "content": old_entry["output"]}
            ]
        }
        
        # Write the new entry as a JSON line.
        fout.write(json.dumps(new_entry, ensure_ascii=False) + "\n")

print(f"Conversion complete. New data saved to {new_file}.")
