import requests
import json
from pathlib import Path

# SEC requires a descriptive User-Agent
HEADERS = {
    "User-Agent": "skrupamaniya1234@gmail.com"
}

# Apple's SEC CIK
URL = "https://data.sec.gov/submissions/CIK0000320193.json"

# Send request to SEC
response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

# Stop if SEC returns an error
response.raise_for_status()

# Convert SEC response into Python data
data = response.json()

# Create data/raw folder if needed
raw_folder = Path("data/raw")
raw_folder.mkdir(parents=True, exist_ok=True)

# Save downloaded data
output_file = raw_folder / "apple_submissions.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2)

print("Data downloaded successfully!")
print(f"Saved to: {output_file}")